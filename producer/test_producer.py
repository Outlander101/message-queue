import producer


def test_build_message_has_required_fields():
    message = producer.build_message(7)
    assert message["log_id"] == 7
    assert message["event_id"] == "log-7"
    assert message["schema_version"] == producer.SCHEMA_VERSION
    assert message["source"] == "producer"
    assert message["timestamp"]
