#!/bin/sh
# wait_for_kafka_up.sh

host="$1"
port="$2"

echo "Awaiting Kafka status at $host:$port..."

while ! nc -z $host $port; do
    sleep 1
done

echo "Kafka is up and running..."
shift 2
exec "$@"
