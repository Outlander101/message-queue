FROM rust:1.75

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y librdkafka-dev protobuf-compiler
RUN cargo build --release

CMD ["./target/release/rust_kafka_consumer"]