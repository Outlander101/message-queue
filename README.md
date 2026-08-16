# Distributed Message Queue System

A containerized real-time message queue pipeline built with Python, Kafka, Redis, Rust, and gRPC.

## Architecture

```text
Python Producer -> Kafka topic: log-events -> Rust Kafka Consumer
                                             \
                                              -> Kafka topic: log-events-dlq (on parse/processing failures)
```

### Reliability model
- Consumer uses explicit offset commits (`enable.auto.commit=false`).
- Offsets are committed only after successful processing or after DLQ handoff.
- Poison or malformed records are sent to DLQ (`log-events-dlq`).
- Rust Kafka Consumer and Rust gRPC service implement distributed idempotency by `log_id` using Redis (`SETNX` with TTL).

## Stack
- Python: `kafka-python`
- Rust: `tonic`, `tokio`, `prost`, `rdkafka`, `redis-rs`
- Backing Stores: `wurstmeister/kafka`, `wurstmeister/zookeeper`, `redis:7-alpine`
- Container orchestration: Docker Compose

## Event schema
Canonical protobuf is defined in `proto/logs.proto`.

`LogMessage` fields:
- `log_id`
- `content`
- `timestamp`
- `level`
- `schema_version`

## Getting started
1. Build and start:
   ```bash
   docker-compose up --build
   ```
2. Follow service logs:
   ```bash
   docker-compose logs -f producer rust_kafka_consumer rust-grpc
   ```
3. Stop stack:
   ```bash
   docker-compose down
   ```

## Operational runbook

### Health checks
- Kafka health: port `9092`.
- Rust gRPC health: port `50051`.
- Redis health: port `6379`.
- Compose uses health-based `depends_on` for startup ordering.

### Debugging quick checks
- Confirm service status:
  ```bash
  docker-compose ps
  ```
- Inspect consumer logic:
  ```bash
  docker-compose logs -f rust_kafka_consumer
  ```

### Failure behavior
- **Invalid JSON or malformed payload**: consumer sends record to DLQ and commits.
- **Duplicate `log_id`**: Rust service returns `duplicate_ignored` or logs ignored event, and consumer commits.

## Testing

### Real-World Execution & Integration Testing
To test the End-to-End (E2E) flow in a production-like environment:

1. **Start the environment in the background:**
   ```bash
   docker-compose up --build -d
   ```
2. **Follow the logs to verify E2E flow:**
   ```bash
   docker-compose logs -f producer rust_kafka_consumer rust-grpc
   ```
3. **Expected Results:**
   - The producer is configured to send 30 messages.
   - You should see `message_produced` logs from the producer.
   - You should see exactly 30 `log_processed` logs from the Rust Kafka Consumer.

4. **Tear down and Clean up:**
   To stop the stack, remove containers, and delete the associated volumes and images:
   ```bash
   docker-compose down -v --rmi all
   ```
   If you want to forcefully prune all unused dangling images on your system:
   ```bash
   docker image prune -f
   ```

### Python Unit Tests
```bash
python3 -m pip install -r producer/requirements.txt pytest
python3 -m pytest producer/test_producer.py
```

### Rust Tests
```bash
cargo test --workspace
```

### Compose validation
```bash
docker-compose config
```

## CI quality gates
The CI workflow runs:
- Python unit tests
- Rust tests
- Docker Compose config validation
