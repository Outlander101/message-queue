import json
import logging
import random
import signal
import time
from datetime import datetime, timezone

import grpc
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

try:
    import logs_pb2
    import logs_pb2_grpc
except ModuleNotFoundError:  # Allows unit tests without generated stubs.
    logs_pb2 = None
    logs_pb2_grpc = None

KAFKA_BOOTSTRAP_SERVERS = ["kafka:9092"]
KAFKA_TOPIC = "log-events"
DLQ_TOPIC = "log-events-dlq"
KAFKA_GROUP_ID = "log-processors"
GRPC_TARGET = "rust-grpc:50051"
GRPC_TIMEOUT_SEC = 3
MAX_RETRIES = 5
BASE_BACKOFF_SEC = 0.5
MAX_BACKOFF_SEC = 8

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("kafka-grpc-consumer")

metrics = {
    "messages_consumed_total": 0,
    "messages_forwarded_total": 0,
    "messages_failed_total": 0,
    "dlq_messages_total": 0,
}

running = True


def on_shutdown(signum, _frame):
    global running
    running = False
    logger.info(json.dumps({"event": "shutdown_signal_received", "signal": signum}))


def log_event(event_name, **fields):
    payload = {"event": event_name, "timestamp": datetime.now(timezone.utc).isoformat()}
    payload.update(fields)
    logger.info(json.dumps(payload))


def classify_grpc_error(err):
    return err.code() in (
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        grpc.StatusCode.INTERNAL,
    )


def send_to_dlq(producer, message, error_message):
    dlq_payload = {
        "error": error_message,
        "received_topic": message.topic,
        "partition": message.partition,
        "offset": message.offset,
        "payload": message.value.decode("utf-8", errors="replace"),
    }
    producer.send(DLQ_TOPIC, value=dlq_payload).get(timeout=10)
    producer.flush()
    metrics["dlq_messages_total"] += 1
    log_event(
        "message_sent_to_dlq",
        topic=DLQ_TOPIC,
        original_topic=message.topic,
        partition=message.partition,
        offset=message.offset,
    )


def main():
    if logs_pb2 is None or logs_pb2_grpc is None:
        raise RuntimeError("gRPC protobuf stubs are missing. Regenerate with grpc_tools.protoc.")

    signal.signal(signal.SIGTERM, on_shutdown)
    signal.signal(signal.SIGINT, on_shutdown)

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        group_id=KAFKA_GROUP_ID,
        value_deserializer=lambda m: m,
    )
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    channel = grpc.insecure_channel(GRPC_TARGET)
    stub = logs_pb2_grpc.LogServiceStub(channel)

    log_event("consumer_started", topic=KAFKA_TOPIC, group_id=KAFKA_GROUP_ID, grpc_target=GRPC_TARGET)

    try:
        while running:
            records = consumer.poll(timeout_ms=1000, max_records=10)
            if not records:
                continue

            for _, messages in records.items():
                for message in messages:
                    if not running:
                        break

                    metrics["messages_consumed_total"] += 1
                    log_id = 0

                    try:
                        log = json.loads(message.value.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as err:
                        metrics["messages_failed_total"] += 1
                        send_to_dlq(producer, message, f"invalid_json:{err}")
                        consumer.commit()
                        continue

                    if not isinstance(log, dict):
                        metrics["messages_failed_total"] += 1
                        send_to_dlq(producer, message, "invalid_payload_type")
                        consumer.commit()
                        continue

                    log_id = int(log.get("log_id", 0))
                    grpc_payload = logs_pb2.LogMessage(
                        log_id=log_id,
                        content=str(log.get("content", "")),
                        timestamp=str(log.get("timestamp", "")),
                        level=str(log.get("level", "INFO")),
                        schema_version=str(log.get("schema_version", "1.0.0")),
                    )

                    last_error = None
                    for attempt in range(1, MAX_RETRIES + 1):
                        started = time.time()
                        try:
                            response = stub.ProcessLog(grpc_payload, timeout=GRPC_TIMEOUT_SEC)
                            latency_ms = int((time.time() - started) * 1000)

                            if not response.success:
                                raise RuntimeError(response.message or "grpc_ack_failed")

                            consumer.commit()
                            metrics["messages_forwarded_total"] += 1
                            log_event(
                                "message_forwarded",
                                log_id=log_id,
                                topic=message.topic,
                                partition=message.partition,
                                offset=message.offset,
                                attempt=attempt,
                                grpc_latency_ms=latency_ms,
                            )
                            last_error = None
                            break
                        except grpc.RpcError as err:
                            last_error = f"grpc:{err.code().name}:{err.details()}"
                            metrics["messages_failed_total"] += 1
                            log_event(
                                "grpc_call_failed",
                                log_id=log_id,
                                topic=message.topic,
                                partition=message.partition,
                                offset=message.offset,
                                attempt=attempt,
                                retriable=classify_grpc_error(err),
                                error=last_error,
                            )
                            if attempt < MAX_RETRIES and classify_grpc_error(err):
                                sleep_time = min(MAX_BACKOFF_SEC, BASE_BACKOFF_SEC * (2 ** (attempt - 1)))
                                sleep_time += random.uniform(0, 0.2)
                                time.sleep(sleep_time)
                                continue
                            break
                        except Exception as err:  # pylint: disable=broad-except
                            metrics["messages_failed_total"] += 1
                            last_error = f"processing:{err}"
                            log_event(
                                "processing_failed",
                                log_id=log_id,
                                topic=message.topic,
                                partition=message.partition,
                                offset=message.offset,
                                attempt=attempt,
                                error=last_error,
                            )
                            break

                    if last_error is not None:
                        send_to_dlq(producer, message, last_error)
                        consumer.commit()
    finally:
        log_event("consumer_stopping", **metrics)
        consumer.close()
        producer.close()
        channel.close()


if __name__ == "__main__":
    try:
        main()
    except KafkaError as err:
        log_event("consumer_fatal_error", error=str(err), **metrics)
        raise
