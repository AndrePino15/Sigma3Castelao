import app.mqtt_client as mqtt
from app.mqtt_topics import  control_topic, emergency_topic, led_topic, status_topic
import time 

s=True
if s:
    # creation of controller instance 
    section_id = 1
    IP_address = "172.20.10.4"

    client = mqtt.MqttClient(broker_host= IP_address,
                             broker_port= 1883,
                             client_id=f"section-{section_id}",
                             keepalive=120,
                             rx_maxsize=256)

    while not client.connect(timeout=5.0):
        print("Connect failed; retrying...")
        time.sleep(2)

    print("Connected to broker!")

    client.subscribe([("safegoals/section/A/led", 0),
                      ("safegoals/section/A/control", 0),
                      ("safegoals/emergency", 1)])
    print("Subscribed to safegoals/section/A/led")
    print("Subscribed to safegoals/section/A/control")
    print("Subscribed to safegoals/section/A/led")
    print("Subscribed to safegoals/emergency")

    # ---- MAIN LOOP ----
    while True:
        event = client.get_rx(timeout=1.0)
        if event:
            print(f"Received on {event.topic}: {event.payload}")

