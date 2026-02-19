import paho.mqtt.client as mqtt
import json

client = mqtt.Client()
client.connect("broker.hivemq.com", 1883, 60)

message = {
    "url": "https://www.youtube.com/watch?v=Txja9tc1LNI"
}

client.publish("stadium/broadcast/replay", json.dumps(message))

