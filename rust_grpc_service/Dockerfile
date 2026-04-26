FROM rust:1.85

WORKDIR /app
COPY Cargo.toml Cargo.toml
COPY rust_grpc_service rust_grpc_service
COPY rust_kafka_consumer rust_kafka_consumer
COPY proto proto
RUN apt update && apt install -y protobuf-compiler netcat-openbsd
RUN cargo build --release -p rust-grpc_service

CMD ["./target/release/rust-grpc_service"]