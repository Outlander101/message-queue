FROM python:3.10-slim

WORKDIR /app
COPY consumer.py .
RUN pip install kafka-python grpcio grpcio-tools

CMD ["python", "consumer.py"]