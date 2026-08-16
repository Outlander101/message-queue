FROM rust:1.85 as builder
WORKDIR /app
RUN apt-get update && apt-get install -y protobuf-compiler
COPY Cargo.toml Cargo.toml
COPY rust_grpc_service rust_grpc_service
COPY rust_kafka_consumer rust_kafka_consumer
COPY proto proto
RUN cargo build --release -p rust-grpc_service

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/rust-grpc_service .
CMD ["./rust-grpc_service"]