FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y netcat-openbsd

COPY producer/producer.py .
COPY producer/wait_for_kafka_up.sh /usr/local/bin/wait_for_kafka_up
COPY producer/requirements.txt .

RUN chmod +x /usr/local/bin/wait_for_kafka_up
RUN pip install --no-cache-dir -r requirements.txt

CMD ["wait_for_kafka_up", "kafka", "9092", "python", "-u", "producer.py"]