# Distributed Message Queue System

A modular, containerized message queuing system built with **Python**, **Apache Kafka**, **Rust**, and **gRPC**. 
This system simulates a real-time logging architecture with producers generating messages, Kafka acting as a message broker, and consumers processing the messages via a Rust-powered gRPC microservice.

---

## Architecture

```plaintext
[Python Producer] ──> Kafka (log-events topic) ──> [Python Consumer] ──> [Rust gRPC Service]
```
**Python Producer**: Simulates log events and pushes them to Kafka.

**Kafka**: Acts as the central message broker using the log-events topic.

**Python Consumer**: Subscribes to Kafka topic and forwards messages to the gRPC service.

**Rust gRPC Server**: Receives and processes log messages via a typed interface using Protocol Buffers.

## Stack

* Python: kafka-python, grpcio

* Rust: tonic, tokio, prost

* Kafka & Zookeeper: wurstmeister/kafka and wurstmeister/zookeeper

* Docker & Docker Compose

Getting Started
1. Clone the Repo
  ```bash
  git clone https://github.com/Outlander101/message-queue.git
  cd message-queue
  ```
2. Build and Launch Services
  ```bash
  docker-compose build
  docker-compose up
  ```
  This will start Zookeeper, Kafka, the producer, consumer, and the Rust gRPC microservice.

## Components Explained

1. Python Producer
  * Generates JSON logs like:
  ```plaintext
  {"log_id": 1, "content": "Event number 1"}
  ```
  * Sends them to Kafka topic log-events.

2. Kafka (via Docker Compose)
  * Configured with 1 topic: log-events
  * Zookeeper used for broker coordination

3. Python Consumer
  * Listens to log-events topic.
  * Sends logs to Rust gRPC backend using logs_pb2 and logs_pb2_grpc.

4. Rust gRPC Service
  * Exposes ProcessLog(LogMessage) endpoint using tonic.
  * Prints or logs messages for further processing.

## Testing the Pipeline
1. Observe logs in real-time:
  ```bash
  docker-compose logs -f consumer
  docker-compose logs -f rust-grpc
  ```
  2. Modify producer.py to generate different messages or burst traffic.
  3. Extend consumer.py to batch, filter, or enrich log data before sending to gRPC.

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss your ideas.
