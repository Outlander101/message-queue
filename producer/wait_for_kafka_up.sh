#!/bin/sh

echo "Awaiting Kafka to be ready at $1:$2..."

while ! nc -z $1 $2; do
    sleep 1
done

echo "Kafka is up and running. Starting Producer"
shift 2
exec "$@"