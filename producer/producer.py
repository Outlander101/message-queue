from kafka import KafkaProducer
import json
import time
import logging
from datetime import datetime, timezone

import os

TOPIC = os.environ.get("KAFKA_TOPIC", "log-events")
SCHEMA_VERSION = os.environ.get("SCHEMA_VERSION", "1.0.0")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MESSAGE_COUNT = int(os.environ.get("MESSAGE_COUNT", "30"))
DELAY_SECONDS = float(os.environ.get("DELAY_SECONDS", "1.0"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("kafka-producer")


def build_message(i):
    return {
        "log_id": i,
        "event_id": f"log-{i}",
        "schema_version": SCHEMA_VERSION,
        "content": f"Event number {i}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "source": "producer",
    }


def on_send_success(metadata, log_id):
    record = {
        "event": "message_produced",
        "topic": metadata.topic,
        "log_id": log_id,
        "partition": metadata.partition,
        "offset": metadata.offset,
    }
    logger.info(json.dumps(record))


def on_send_error(err, log_id):
    record = {
        "event": "message_produce_failed",
        "topic": TOPIC,
        "log_id": log_id,
        "error": str(err),
    }
    logger.error(json.dumps(record))


import signal
import sys

running = True

def on_shutdown(signum, _frame):
    global running
    running = False
    logger.info(json.dumps({"event": "shutdown_signal_received", "signal": signum}))

def main():
    signal.signal(signal.SIGTERM, on_shutdown)
    signal.signal(signal.SIGINT, on_shutdown)

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        retries=5,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    for i in range(1, MESSAGE_COUNT + 1):
        if not running:
            logger.info(json.dumps({"event": "producer_interrupted", "messages_sent": i - 1}))
            break
            
        message = build_message(i)
        future = producer.send(TOPIC, key=message["event_id"].encode("utf-8"), value=message)
        future.add_callback(on_send_success, message["log_id"])
        future.add_errback(on_send_error, message["log_id"])
        
        # Sleep in small increments to respond to signals faster
        sleep_elapsed = 0
        while sleep_elapsed < DELAY_SECONDS and running:
            time.sleep(0.1)
            sleep_elapsed += 0.1

    producer.flush()
    logger.info(json.dumps({"event": "producer_complete", "total_messages": MESSAGE_COUNT}))


if __name__ == "__main__":
    main()