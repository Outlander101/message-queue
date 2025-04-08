FROM rust:1.72

WORKDIR /app
COPY . .
RUN apt update && apt install -y protobuf-compiler
RUN cargo build --release

CMD ["./target/debug/rust-grpc_service"]