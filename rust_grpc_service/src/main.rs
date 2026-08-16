use redis::AsyncCommands;
use std::sync::Arc;
use tonic::{transport::Server, Request, Response, Status};

use logs::log_service_server::{LogService, LogServiceServer};
use logs::{LogAck, LogMessage};

pub mod logs {
    tonic::include_proto!("logs");
}

#[derive(Clone)]
pub struct SystemLogService {
    redis_client: redis::Client,
}

impl SystemLogService {
    pub fn new(redis_url: &str) -> Result<Self, redis::RedisError> {
        let client = redis::Client::open(redis_url)?;
        Ok(Self {
            redis_client: client,
        })
    }
}

#[tonic::async_trait]
impl LogService for SystemLogService {
    async fn process_log(&self, request: Request<LogMessage>) -> Result<Response<LogAck>, Status> {
        let payload = request.into_inner();
        if payload.log_id <= 0 {
            return Err(Status::invalid_argument("log_id must be positive"));
        }

        if payload.content.trim().is_empty() {
            return Err(Status::invalid_argument("content cannot be empty"));
        }

        let mut con = self
            .redis_client
            .get_multiplexed_tokio_connection()
            .await
            .map_err(|e| Status::internal(format!("Redis connection error: {}", e)))?;

        let key = format!("log_id:{}", payload.log_id);
        
        // Use SET with NX (Only set if not exists) and EX (Expire in 24 hours)
        let is_new: bool = redis::cmd("SET")
            .arg(&key)
            .arg("1")
            .arg("EX")
            .arg(86400)
            .arg("NX")
            .query_async(&mut con)
            .await
            .map_err(|e| Status::internal(format!("Redis query error: {}", e)))?;

        if !is_new {
            println!(
                "{{\"event\":\"duplicate_log_ignored\",\"log_id\":{},\"level\":\"{}\"}}",
                payload.log_id, payload.level
            );
            return Ok(Response::new(LogAck {
                success: true,
                message: "duplicate_ignored".to_string(),
            }));
        }

        println!(
            "{{\"event\":\"log_processed\",\"log_id\":{},\"level\":\"{}\",\"content\":\"{}\",\"timestamp\":\"{}\"}}",
            payload.log_id, payload.level, payload.content, payload.timestamp
        );
        Ok(Response::new(LogAck {
            success: true,
            message: "processed".to_string(),
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr_str = std::env::var("GRPC_BIND_ADDRESS").unwrap_or_else(|_| "[::]:50051".to_string());
    let addr = addr_str.parse()?;
    
    let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://127.0.0.1:6379".to_string());
    
    let sls = SystemLogService::new(&redis_url)?;
    println!("{{\"event\":\"grpc_server_starting\",\"address\":\"{}\"}}", addr);

    let shutdown = async {
        tokio::signal::ctrl_c()
            .await
            .expect("Failed to listen for ctrl_c signal");
        println!("{{\"event\":\"grpc_server_shutting_down\"}}");
    };

    Server::builder()
        .add_service(LogServiceServer::new(sls))
        .serve_with_shutdown(addr, shutdown)
        .await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn rejects_invalid_log_id() {
        let service = SystemLogService::new("redis://127.0.0.1:6379").unwrap();
        let req = Request::new(LogMessage {
            log_id: 0,
            content: "test".to_string(),
            timestamp: "2026-01-01T00:00:00Z".to_string(),
            level: "INFO".to_string(),
            schema_version: "1.0.0".to_string(),
        });

        let result = service.process_log(req).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    #[ignore = "Requires local Redis instance"]
    async fn deduplicates_log_ids() {
        let service = SystemLogService::new("redis://127.0.0.1:6379").unwrap();
        let first = Request::new(LogMessage {
            log_id: 8,
            content: "first".to_string(),
            timestamp: "2026-01-01T00:00:00Z".to_string(),
            level: "INFO".to_string(),
            schema_version: "1.0.0".to_string(),
        });
        let second = Request::new(LogMessage {
            log_id: 8,
            content: "second".to_string(),
            timestamp: "2026-01-01T00:00:00Z".to_string(),
            level: "INFO".to_string(),
            schema_version: "1.0.0".to_string(),
        });

        let first_result = service.process_log(first).await.unwrap().into_inner();
        let second_result = service.process_log(second).await.unwrap().into_inner();
        assert_eq!(first_result.message, "processed");
        assert_eq!(second_result.message, "duplicate_ignored");
    }
}