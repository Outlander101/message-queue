from kafka import KafkaConsumer
import json
import grpc
import time
import logs_pb2
import logs_pb2_grpc

# Connect to Kafak topic
consumer = KafkaConsumer(
    'log-events',
    bootstrap_servers=['kafka:9092'],
    auto_offset_reset='earliest',
    group_id='log-processors',
    value_deserializer= lambda m: json.loads(m.decode('utf-8'))
)

# Set up gRPC channel and stub to invoke Rust service
channel = grpc.insecure_channel("rust-grpc:50051")
stub = logs_pb2_grpc.LogServiceStub(channel)

print("Listening for messages on 'log-events' topic... \n")

# Loop through messages in Kafka topic and forward to Rust gRPC service
for message in consumer:
    log = message.value

    try:
        gRPC_response = stub.ProcessLog(
            logs_pb2.LogMessage(
                log_id=log.get('log_id', 0),
                content=log.get('content', ""),
                timestamp=log.get('timestamp', ""),
                level=log.get('level', "INFO"),
            )
        )
        print(f"Forwarded log {log['log_id']} to Rust gRPC service. Acknowledgement: {gRPC_response.message}")
    except grpc.RpcError as e:
        print(f"Error forwarding log {log['log_id']} to Rust gRPC service: {e}")
