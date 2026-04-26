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
