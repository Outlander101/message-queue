from kafka import KafkaProducer
import json
import time

producer = KafkaProducer(
    bootstrap_servers='kafka:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

for i in range(30):
    message = {"log_id": i, "content": f"Event number {i}"}
    producer.send('log-events', value=message)
    print(f"Produced: {message}")
    time.sleep(1) # To similate log generation in real-time env.

producer.flush()
print("Finished sending all messages.")