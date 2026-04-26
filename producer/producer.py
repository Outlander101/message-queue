from kafka import KafkaProducer
import json
import time
import logging
from datetime import datetime, timezone

TOPIC = "log-events"
SCHEMA_VERSION = "1.0.0"

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


def report_delivery(metadata_future, message):
    record = {"event": "message_produced", "topic": TOPIC, "log_id": message["log_id"]}
    try:
        metadata = metadata_future.get(timeout=10)
        record.update(
            {
                "partition": metadata.partition,
                "offset": metadata.offset,
            }
        )
        logger.info(json.dumps(record))
    except Exception as err:  # pylint: disable=broad-except
        record.update({"event": "message_produce_failed", "error": str(err)})
        logger.error(json.dumps(record))


def main():
    producer = KafkaProducer(
        bootstrap_servers="kafka:9092",
        retries=5,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    for i in range(30):
        message = build_message(i)
        future = producer.send(TOPIC, key=message["event_id"].encode("utf-8"), value=message)
        report_delivery(future, message)
        time.sleep(1)  # Simulate log generation in a real-time environment.

    producer.flush()
    logger.info(json.dumps({"event": "producer_complete", "total_messages": 30}))


if __name__ == "__main__":
    main()