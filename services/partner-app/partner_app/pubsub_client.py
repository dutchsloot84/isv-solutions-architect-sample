from google.cloud import pubsub_v1
import os
import json

PROJECT_ID = os.getenv("GCP_PROJECT", "demo")
TOPIC = os.getenv("ORDERS_TOPIC", "orders")


def publish_order(order: dict):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC)
    publisher.publish(topic_path, json.dumps(order).encode("utf-8"))
