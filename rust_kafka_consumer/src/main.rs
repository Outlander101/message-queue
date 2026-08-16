use log::{error, info};
use rdkafka::{
    config::ClientConfig,
    consumer::{CommitMode, Consumer, StreamConsumer},
    message::BorrowedMessage,
    producer::{FutureProducer, FutureRecord},
    Message,
};
use redis::AsyncCommands;
use serde::Deserialize;
use std::time::Duration;
use tokio::time::timeout;

#[derive(Debug, Deserialize)]
struct LogMessage {
    log_id: i32,
    content: String,
    timestamp: Option<String>,
    level: Option<String>,
}

#[tokio::main]
async fn main() {
    env_logger::init();

    let bootstrap_servers = std::env::var("KAFKA_BOOTSTRAP_SERVERS").unwrap_or_else(|_| "kafka:9092".to_string());
    let group_id = std::env::var("KAFKA_GROUP_ID").unwrap_or_else(|_| "rust_log_consumer".to_string());
    let topic = std::env::var("KAFKA_TOPIC").unwrap_or_else(|_| "log-events".to_string());
    let dlq_topic = std::env::var("DLQ_TOPIC").unwrap_or_else(|_| "log-events-dlq".to_string());
    let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://127.0.0.1:6379".to_string());

    let redis_client = redis::Client::open(redis_url).expect("Failed to create Redis client");
    let mut redis_con = redis_client
        .get_multiplexed_tokio_connection()
        .await
        .expect("Failed to connect to Redis");

    let consumer: StreamConsumer = ClientConfig::new()
        .set("bootstrap.servers", &bootstrap_servers)
        .set("group.id", &group_id)
        .set("auto.offset.reset", "earliest")
        .set("enable.auto.commit", "false")
        .create()
        .expect("Consumer creation failed");

    consumer.subscribe(&[&topic]).expect("Failed to subscribe");

    let producer: FutureProducer = ClientConfig::new()
        .set("bootstrap.servers", &bootstrap_servers)
        .set("message.timeout.ms", "5000")
        .create()
        .expect("Producer creation failed");

    info!("{{\"event\":\"rust_kafka_consumer_started\",\"topic\":\"{}\"}}", topic);

    let mut shutdown_signal = std::pin::pin!(tokio::signal::ctrl_c());

    loop {
        tokio::select! {
            _ = &mut shutdown_signal => {
                info!("{{\"event\":\"rust_kafka_consumer_shutting_down\"}}");
                break;
            }
            msg_result = consumer.recv() => {
                match msg_result {
                    Err(e) => error!("Kafka error: {}", e),
                    Ok(message) => {
                        handle_message(&message, &producer, &dlq_topic, &mut redis_con).await;
                        if let Err(e) = consumer.commit_message(&message, CommitMode::Async) {
                            error!("Failed to commit message: {}", e);
                        }
                    }
                }
            }
        }
    }
}

async fn handle_message(
    msg: &BorrowedMessage<'_>,
    producer: &FutureProducer,
    dlq_topic: &str,
    redis_con: &mut redis::aio::MultiplexedConnection,
) {
    let payload = match msg.payload_view::<str>() {
        Some(Ok(p)) => p,
        Some(Err(_)) | None => {
            info!("{{\"event\":\"kafka_log_ignored_tombstone\"}}");
            return;
        }
    };

    let log_message: LogMessage = match serde_json::from_str(payload) {
        Ok(m) => m,
        Err(e) => {
            error!("{{\"event\":\"kafka_log_parse_failed\",\"error\":\"{}\"}}", e);
            send_to_dlq(producer, dlq_topic, payload, &e.to_string()).await;
            return;
        }
    };

    let key = format!("log_id:{}", log_message.log_id);
    let is_new: Result<bool, _> = redis::cmd("SET")
        .arg(&key)
        .arg("1")
        .arg("EX")
        .arg(86400)
        .arg("NX")
        .query_async(redis_con)
        .await;

    match is_new {
        Ok(true) => {
            info!(
                "{{\"event\":\"log_processed\",\"log_id\":{},\"level\":\"{}\",\"content\":\"{}\",\"timestamp\":\"{}\"}}",
                log_message.log_id,
                log_message.level.unwrap_or_else(|| "INFO".to_string()),
                log_message.content,
                log_message.timestamp.unwrap_or_default()
            );
        }
        Ok(false) => {
            info!(
                "{{\"event\":\"duplicate_log_ignored\",\"log_id\":{}}}",
                log_message.log_id
            );
        }
        Err(e) => {
            error!("{{\"event\":\"redis_error\",\"error\":\"{}\"}}", e);
        }
    }
}

async fn send_to_dlq(producer: &FutureProducer, dlq_topic: &str, payload: &str, error_msg: &str) {
    let dlq_payload = format!(
        "{{\"original_payload\":{},\"error\":\"{}\"}}",
        serde_json::to_string(payload).unwrap_or_else(|_| "\"unserializable\"".to_string()),
        error_msg
    );
    let record = FutureRecord::to(dlq_topic).payload(&dlq_payload).key("dlq");
    let _ = timeout(Duration::from_secs(3), producer.send(record, Duration::from_secs(0))).await;
}
