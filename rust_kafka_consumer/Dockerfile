FROM rust:1.85 as builder
WORKDIR /app
RUN apt-get update && apt-get install -y librdkafka-dev protobuf-compiler
COPY scripts/wait_for_kafka_up.sh /usr/local/bin/wait_for_kafka_up
RUN chmod +x /usr/local/bin/wait_for_kafka_up
COPY Cargo.toml Cargo.toml
COPY rust_kafka_consumer rust_kafka_consumer
COPY rust_grpc_service rust_grpc_service
COPY proto proto
RUN cargo build --release -p rust_kafka_consumer

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y netcat-openbsd librdkafka1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /usr/local/bin/wait_for_kafka_up /usr/local/bin/wait_for_kafka_up
COPY --from=builder /app/target/release/rust_kafka_consumer .
CMD ["wait_for_kafka_up", "kafka", "9092", "./rust_kafka_consumer"]