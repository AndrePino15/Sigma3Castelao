import json
import time
import threading
import random
import os
from datetime import datetime

import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))

SEAT_ID = "section1,row1,col1"

TOPIC_TELE = f"stadium/seat/{SEAT_ID}/telemetry"
TOPIC_CMD  = f"stadium/seat/{SEAT_ID}/cmd"
TOPIC_ACK  = f"stadium/seat/{SEAT_ID}/ack"
TOPIC_SAFETY = "stadium/broadcast/safety"


def now_ts() -> float:
    return time.time()


def make_telemetry():
    return {
        "ts": now_ts(),
        "mode": random.choice(["IDLE", "RUN", "ERROR"]),
        "device_id": SEAT_ID,
        "rssi": random.randint(-80, -40),
        "metric": round(random.random(), 2),
        "msg": random.choice([
            "Match: TeamA vs TeamB",
            "Vote now: Best player?",
            "Order available: Drinks/Snacks",
            "All systems nominal",
        ])
    }


def make_ack(ref_cmd: str):
    return {
        "ts": now_ts(),
        "ok": True,
        "ref_cmd": ref_cmd,
        "msg": f"ACK for {ref_cmd}"
    }


def make_safety(level="CRITICAL", msg="Evacuate via Exit B"):
    return {
        "ts": now_ts(),
        "mode": "SAFETY",
        "level": level,
        "msg": msg
    }


def on_connect(client, userdata, flags, rc):
    print(f"[{datetime.now()}] Connected to MQTT broker, rc={rc}")
    client.subscribe(TOPIC_CMD, qos=1)
    print(f"Subscribed: {TOPIC_CMD}")


def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)
        cmd = data.get("cmd", "UNKNOWN")
        print(f"[{datetime.now()}] CMD received on {message.topic}: {data}")

        ack = make_ack(cmd)
        client.publish(TOPIC_ACK, json.dumps(ack), qos=1)
        print(f"[{datetime.now()}] ACK sent on {TOPIC_ACK}: {ack}")

    except Exception as e:
        print(f"Error handling message: {e}")


def telemetry_loop(client: mqtt.Client, stop_event: threading.Event):
    while not stop_event.is_set():
        tele = make_telemetry()
        client.publish(TOPIC_TELE, json.dumps(tele), qos=0)
        time.sleep(0.2)  # 5 Hz


def safety_input_loop(client: mqtt.Client, stop_event: threading.Event):
    print("\nType 's' + Enter to broadcast SAFETY, 'n' + Enter for NORMAL, 'q' to quit.\n")
    while not stop_event.is_set():
        cmd = input().strip().lower()
        if cmd == "s":
            safety = make_safety()
            client.publish(TOPIC_SAFETY, json.dumps(safety), qos=1, retain=True)
            print(f"[{datetime.now()}] SAFETY broadcast (retain) sent: {safety}")
        elif cmd == "n":
            normal = {"ts": now_ts(), "mode": "NORMAL", "level": "INFO", "msg": "Safety cleared"}
            client.publish(TOPIC_SAFETY, json.dumps(normal), qos=1, retain=True)
            print(f"[{datetime.now()}] Safety cleared broadcast (retain) sent: {normal}")
        elif cmd == "q":
            stop_event.set()
        else:
            print("Unknown input. Use: s / n / q")


def main():
    client = mqtt.Client(client_id=f"fake_server_{SEAT_ID}", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    stop_event = threading.Event()

    t1 = threading.Thread(target=telemetry_loop, args=(client, stop_event), daemon=True)
    t1.start()

    # Blocking input loop in main thread
    safety_input_loop(client, stop_event)

    print("Stopping...")
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
