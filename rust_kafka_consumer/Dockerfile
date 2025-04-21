FROM rust:1.75

WORKDIR /app

RUN apt-get update && apt-get install -y netcat-openbsd librdkafka-dev protobuf-compiler

COPY wait_for_kafka_up.sh /usr/local/bin/wait_for_kafka_up
COPY . .

RUN chmod +x /usr/local/bin/wait_for_kafka_up
RUN cargo build --release

CMD ["wait_for_kafka_up", "kafka", "9092", "./target/release/rust_kafka_consumer"]