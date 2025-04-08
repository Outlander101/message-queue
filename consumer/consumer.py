from kafka import KafkaConsumer
import json
import grpc
import logs_pb2
import logs_pb2_grpc

# Set up gRPC channel and stub to invoke Rust service
channel = grpc.insecure_channel("rust-grpc:50051")
stub = logs_pb2_grpc.LogServiceStub(channel)

consumer = KafkaConsumer(
    'log-events',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    group_id='log-processors',
    value_deserializer= lambda m: json.loads(m.decode('utf-8'))
)

print("Listening for messages on 'log-events' topic... \n")

for message in consumer:
    print(f"Consumed log: {message.value}")
    
    # send message request to Rust gRPC service
    message_request = logs_pb2.LogMessage(
        log_id=message.value['log_id'],
        content=message.value['content']
    )
    response = stub.ProcessLog(message_request)
    print(f"Message sent to Rust gRPC service. Acknowledgement: {response.success}")
