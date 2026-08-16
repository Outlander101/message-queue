import grpc

import consumer


class DummyMessage:
    topic = "log-events"
    partition = 0
    offset = 10
    value = b'{"log_id": 1}'


class DummyFuture:
    def get(self, timeout):  # pylint: disable=unused-argument
        return True


class DummyProducer:
    def __init__(self):
        self.sent = []
        self.flushed = False

    def send(self, topic, value):
        self.sent.append((topic, value))
        return DummyFuture()

    def flush(self):
        self.flushed = True


def test_classify_grpc_error_marks_retryable_codes():
    err = grpc.RpcError()
    err.code = lambda: grpc.StatusCode.UNAVAILABLE
    assert consumer.classify_grpc_error(err) is True

    err_non_retryable = grpc.RpcError()
    err_non_retryable.code = lambda: grpc.StatusCode.INVALID_ARGUMENT
    assert consumer.classify_grpc_error(err_non_retryable) is False


def test_send_to_dlq_serializes_context():
    producer = DummyProducer()
    msg = DummyMessage()
    before = consumer.metrics["dlq_messages_total"]
    consumer.send_to_dlq(producer, msg, "bad_payload")

    assert producer.flushed is True
    assert len(producer.sent) == 1
    topic, value = producer.sent[0]
    assert topic == consumer.DLQ_TOPIC
    assert value["error"] == "bad_payload"
    assert value["received_topic"] == "log-events"
    assert consumer.metrics["dlq_messages_total"] == before + 1


class DummyKafkaConsumer:
    def __init__(self):
        self.committed = None

    def commit(self, offsets):
        self.committed = offsets


def test_commit_message_explicit_offsets():
    mock_consumer = DummyKafkaConsumer()
    msg = DummyMessage()
    msg.topic = "test-topic"
    msg.partition = 2
    msg.offset = 42

    consumer.commit_message(mock_consumer, msg)

    assert mock_consumer.committed is not None
    # Verify we committed the exact topic/partition and offset+1
    committed_tp = list(mock_consumer.committed.keys())[0]
    committed_meta = mock_consumer.committed[committed_tp]
    
    assert committed_tp.topic == "test-topic"
    assert committed_tp.partition == 2
    assert committed_meta.offset == 43
