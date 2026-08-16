# Issues and Proposed Fixes

## 1. Python Consumer: Major Message Loss on Crash (Kafka Commit Bug)
**Issue:** The consumer uses `consumer.commit()` after processing each message. In `kafka-python`, calling `commit()` without arguments commits the highest offset of all messages returned in the last `poll()`. If `poll()` returns 10 messages, and processing the first one succeeds, the consumer commits offsets for all 10 messages. If it crashes while processing the second message, messages 2-10 are lost permanently.
**Fix / Improvement:** Commit explicit offsets for the exact message that was successfully processed.
**Sample Code Change (`consumer/consumer.py`):**
```python
from kafka import TopicPartition, OffsetAndMetadata

# Instead of consumer.commit(), use:
tp = TopicPartition(message.topic, message.partition)
consumer.commit({tp: OffsetAndMetadata(message.offset + 1, "")})
```

## 2. Python Consumer: Unhandled Tombstone Messages
**Issue:** If a tombstone message (a message with a key but a `null` value, used for Kafka log compaction) is consumed, `message.value` is `None`. Calling `message.value.decode("utf-8")` will raise an `AttributeError` and crash the consumer.
**Fix / Improvement:** Add a safeguard to ignore or explicitly handle empty payloads.
**Sample Code Change (`consumer/consumer.py`):**
```python
if message.value is None:
    logger.info("Skipping tombstone message")
    consumer.commit({TopicPartition(message.topic, message.partition): OffsetAndMetadata(message.offset + 1, "")})
    continue
```

## 3. Python Producer: Synchronous Blocking Delivery
**Issue:** The producer's `report_delivery` uses `metadata_future.get(timeout=10)`. This completely blocks the loop waiting for the broker to acknowledge the message. This defeats the purpose of the asynchronous `KafkaProducer` and severely impacts throughput.
**Fix / Improvement:** Use asynchronous callbacks (`add_callback` and `add_errback`) instead of blocking with `.get()`.
**Sample Code Change (`producer/producer.py`):**
```python
def on_success(metadata, message_log_id):
    logger.info(json.dumps({"event": "message_produced", "log_id": message_log_id, "offset": metadata.offset}))

def on_error(err, message_log_id):
    logger.error(json.dumps({"event": "message_produce_failed", "log_id": message_log_id, "error": str(err)}))

# When sending:
future = producer.send(TOPIC, key=message["event_id"].encode("utf-8"), value=message)
future.add_callback(on_success, message["log_id"]).add_errback(on_error, message["log_id"])
```

## 4. Rust gRPC Service: Concurrency Bottleneck on Deduplication Cache
**Issue:** The gRPC service uses an `LruCache` wrapped in a `tokio::sync::RwLock` inside an `Arc`. Because `LruCache::put` requires a mutable reference, every gRPC request must acquire an exclusive `write().await` lock. This serializes all incoming requests, eliminating concurrency.
**Fix / Improvement:** Replace `LruCache` with a concurrent cache crate like `moka` which supports high-concurrency insertions and deduplication without blocking all threads.
**Sample Code Change (`rust_grpc_service/Cargo.toml` and `src/main.rs`):**
```toml
# Add to Cargo.toml
moka = { version = "0.12", features = ["future"] }
```
```rust
use moka::future::Cache;

pub struct SystemLogService {
    processed_ids: Cache<i32, ()>,
}
// In new(): processed_ids: Cache::builder().max_capacity(100_000).build()
// In process_log(): if self.processed_ids.contains_key(&payload.log_id) { ... } else { self.processed_ids.insert(payload.log_id, ()).await; }
```

## 5. Architectural Improvement: Bypassing the Python Bridge
**Issue:** The Python Consumer acts as a bridge to forward Kafka messages to the Rust gRPC server. However, there is already a `rust_kafka_consumer` present in the repository. Consuming from Kafka in Python just to send it over gRPC to Rust adds latency, network overhead, and complexity (two apps to maintain, gRPC retry logic, etc.).
**Fix / Improvement:** Consolidate the workflow. Deprecate the Python Consumer and gRPC service in favor of the `rust_kafka_consumer` handling both ingestion and deduplication directly. If the gRPC interface is required by other non-Kafka clients, we can keep it, but Kafka messages should ideally be processed directly by the Rust Kafka consumer.
*(For this fix, we will focus on patching the existing components, but this is a structural recommendation to consider.)*
