FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y netcat-openbsd

COPY wait_for_kafka_up.sh /usr/local/bin/wait_for_kafka_up
COPY ./proto ./proto
COPY consumer.py .

RUN chmod +x /usr/local/bin/wait_for_kafka_up
RUN pip install kafka-python grpcio grpcio-tools

CMD ["wait_for_kafka_up", "kafka", "9092", "python", "-u", "consumer.py"]