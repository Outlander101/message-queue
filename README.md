# Distributed Message Queue System

A containerized real-time message queue pipeline built with Python, Kafka, Rust, and gRPC.

## Architecture

```text
Python Producer -> Kafka topic: log-events -> Python Bridge Consumer -> Rust gRPC Service
                                            \
                                             -> Kafka topic: log-events-dlq (on repeated failures)
```

### Reliability model
- Consumer uses explicit offset commits (`enable_auto_commit=False`).
- Offsets are committed only after successful gRPC processing or after DLQ handoff.
- gRPC forwarding uses bounded retries with exponential backoff and timeout.
- Poison or malformed records are sent to DLQ (`log-events-dlq`).
- Rust gRPC service implements in-memory idempotency by `log_id`.

## Stack
- Python: `kafka-python`, `grpcio`, `grpcio-tools`
- Rust: `tonic`, `tokio`, `prost`, `rdkafka`
- Kafka + Zookeeper: `wurstmeister/kafka`, `wurstmeister/zookeeper`
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
   docker-compose logs -f producer consumer rust-grpc
   ```
3. Stop stack:
   ```bash
   docker-compose down
   ```

## Operational runbook

### Health checks
- Kafka health: port `9092`.
- Rust gRPC health: port `50051`.
- Compose uses health-based `depends_on` for startup ordering.

### Debugging quick checks
- Confirm service status:
  ```bash
  docker-compose ps
  ```
- Inspect consumer metrics emitted as JSON logs:
  - `messages_consumed_total`
  - `messages_forwarded_total`
  - `messages_failed_total`
  - `dlq_messages_total`
- Inspect DLQ flow:
  ```bash
  docker-compose logs -f consumer
  ```

### Failure behavior
- **gRPC unavailable**: consumer retries with backoff; after max retries, sends to DLQ and commits.
- **Invalid JSON or malformed payload**: consumer sends record to DLQ and commits.
- **Duplicate `log_id`**: Rust service returns `duplicate_ignored` and consumer commits.

## Testing

### Real-World Execution & Integration Testing
To test the End-to-End (E2E) flow in a production-like environment:

1. **Start the environment in the background:**
   ```bash
   docker-compose up --build -d
   ```
2. **Follow the logs to verify E2E flow:**
   ```bash
   docker-compose logs -f producer consumer rust-grpc
   ```
3. **Expected Results:**
   - The producer is configured to send 30 messages.
   - You should see `message_produced` logs from the producer.
   - You should see exactly 30 `message_forwarded` logs from the consumer.
   - You should see exactly 30 `log_processed` logs from the Rust gRPC service.
   - `dlq_messages_total` should remain at 0 in consumer metrics.

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
The unit tests use `pytest` and stub out network interactions.
```bash
python3 -m pip install -r producer/requirements.txt -r consumer/requirements.txt pytest
python3 -m pytest producer/test_producer.py consumer/test_consumer.py
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

Rust `fmt`/`clippy` checks are configured in CI and require the corresponding toolchain components.
