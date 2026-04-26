use log::{error, info};
use rdkafka::{
    config::ClientConfig,
    consumer::{Consumer, StreamConsumer},
    message::BorrowedMessage,
    Message,
};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct LogMessage {
    log_id: i32,
    content: String,
    timestamp: Option<String>,
    level: Option<String>,
    schema_version: Option<String>,
}

#[tokio::main]
async fn main() {
    env_logger::init();

    let consumer: StreamConsumer = ClientConfig::new()
        .set("bootstrap.servers", "kafka:9092")
        .set("group.id", "rust_log_consumer")
        .set("auto.offset.reset", "earliest")
        .create()
        .expect("Consumer creation failed with ClientConfig.");

    consumer
        .subscribe(&["log-events"])
        .expect("Failed to subscribe to log events.");

    info!("{{\"event\":\"rust_kafka_consumer_started\",\"topic\":\"log-events\"}}");

    loop {
        match consumer.recv().await {
            Err(e) => error!("Kafka error: {}", e),
            Ok(message) => handle_message(message),
        }
    }
}

fn handle_message(msg: BorrowedMessage) {
    if let Some(Ok(payload)) = msg.payload_view() {
        match serde_json::from_str::<LogMessage>(payload) {
            Ok(log_message) => info!(
                "{{\"event\":\"kafka_log_consumed\",\"log_id\":{},\"content\":\"{}\",\"timestamp\":\"{}\",\"level\":\"{}\",\"schema_version\":\"{}\"}}",
                log_message.log_id,
                log_message.content,
                log_message.timestamp.unwrap_or_default(),
                log_message.level.unwrap_or_else(|| "INFO".to_string()),
                log_message.schema_version.unwrap_or_else(|| "1.0.0".to_string())
            ),
            Err(e) => error!("{{\"event\":\"kafka_log_parse_failed\",\"error\":\"{}\"}}", e),
        }
    } else {
        error!("{{\"event\":\"kafka_log_empty_or_unreadable\"}}");
    }
}
