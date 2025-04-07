from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'log-events',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    group_id='log-processors',
    value_deserializer= lambda m: json.loads(m.decode('utf-8'))
)

print("Listening for messages on 'log-events' topic... \n")
for message in consumer:
    print(f"Consumed log: {message.value}")