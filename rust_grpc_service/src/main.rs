use std::collections::HashSet;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};

use logs::log_service_server::{LogService, LogServiceServer};
use logs::{LogAck, LogMessage};

pub mod logs {
    tonic::include_proto!("logs");
}

#[derive(Debug, Default)]
pub struct SystemLogService {
    processed_ids: Arc<RwLock<HashSet<i32>>>,
}

impl SystemLogService {
    pub fn new() -> Self {
        Self {
            processed_ids: Arc::new(RwLock::new(HashSet::new())),
        }
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

        let mut processed_ids = self.processed_ids.write().await;
        if !processed_ids.insert(payload.log_id) {
            println!(
                "{{\"event\":\"duplicate_log_ignored\",\"log_id\":{},\"level\":\"{}\"}}",
                payload.log_id, payload.level
            );
            return Ok(Response::new(LogAck {
                success: true,
                message: "duplicate_ignored".to_string(),
            }));
        }
        drop(processed_ids);

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
    let addr = "[::]:50051".parse()?;
    let sls = SystemLogService::new();
    println!("{{\"event\":\"grpc_server_starting\",\"address\":\"{}\"}}", addr);

    Server::builder()
        .add_service(LogServiceServer::new(sls))
        .serve(addr)
        .await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn rejects_invalid_log_id() {
        let service = SystemLogService::new();
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
    async fn deduplicates_log_ids() {
        let service = SystemLogService::new();
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