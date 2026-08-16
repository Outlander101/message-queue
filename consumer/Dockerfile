FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y netcat-openbsd

COPY scripts/wait_for_kafka_up.sh /usr/local/bin/wait_for_kafka_up
COPY proto/logs.proto ./proto/logs.proto
COPY consumer/consumer.py .
COPY consumer/requirements.txt .

RUN chmod +x /usr/local/bin/wait_for_kafka_up
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. ./proto/logs.proto

CMD ["wait_for_kafka_up", "kafka", "9092", "python", "-u", "consumer.py"]