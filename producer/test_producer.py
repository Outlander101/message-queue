import logging
import producer


def test_build_message_has_required_fields():
    message = producer.build_message(7)
    assert message["log_id"] == 7
    assert message["event_id"] == "log-7"
    assert message["schema_version"] == producer.SCHEMA_VERSION
    assert message["source"] == "producer"
    assert message["timestamp"]


def test_on_send_success(caplog):
    class DummyMetadata:
        topic = "test-topic"
        partition = 1
        offset = 123

    caplog.set_level(logging.INFO)
    producer.on_send_success(DummyMetadata(), 42)
    assert "message_produced" in caplog.text
    assert "test-topic" in caplog.text
    assert "123" in caplog.text


def test_on_send_error(caplog):
    caplog.set_level(logging.INFO)
    producer.on_send_error(Exception("kafka_down"), 42)
    assert "message_produce_failed" in caplog.text
    assert "kafka_down" in caplog.text
