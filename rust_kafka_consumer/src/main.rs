use rdkafka::{
    config::ClientConfig, consumer::{Consumer, StreamConsumer}, message::{self, BorrowedMessage}, Message};
use serde::Deserialize;
use std::time::Duration;
use log::{info, error};

#[derive(Debug, Deserialize)]
struct LogMessage {
    log_id: i32,
    content: String,
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

    println!("Subscribed to log-events. Starting poll loop");
    info!("Rust Kafka Consumer service has been started and is listening...");

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
            Ok(log_message) => println!("Consumed log: {:?}", log_message),
            Err(e) => eprintln!("Failed to parse JSON: {}", e),
        }
    } else {
        eprintln!("Empty/Unreadable Kafka log message");
    }
}
