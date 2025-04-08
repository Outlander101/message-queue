use tonic::{transport::Server, Request, Response, Status};
use logs::log_service_server::{LogService, LogServiceServer};
use logs::{LogMessage, LogAck};

pub mod logs {
    tonic::include_proto!("logs");
}

#[derive(Debug, Default)]
pub struct SystemLogService;

#[tonic::async_trait]
impl LogService for SystemLogService {
    async fn process_log(&self, request: Request<LogMessage>) -> Result<Response<LogAck>, Status> {
        println!("Recived log: {:?}", request.into_inner());
        Ok(Response::new(LogAck { success: true}))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "[::]:50051".parse()?;
    let sls = SystemLogService::default();

    Server::builder()
        .add_service(LogServiceServer::new(sls))
        .serve(addr)
        .await?;

    Ok(())
}