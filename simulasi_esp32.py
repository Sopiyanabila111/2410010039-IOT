"""
Simulator ESP32 untuk IoT Dashboard.

- Publish data sensor ke topik iot/sensor tiap beberapa detik
- Subscribe iot/kontrol (perintah lampu) dan iot/alert (notifikasi batas suhu)

Contoh:
    python simulasi_esp32.py                 # normal, suhu acak 25-32 C
    python simulasi_esp32.py --mode panas    # suhu naik terus, memicu alert batas atas
    python simulasi_esp32.py --interval 1    # kirim tiap 1 detik
"""
import argparse
import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt

TOPIC_SENSOR = "iot/sensor"
TOPIC_KONTROL = "iot/kontrol"
TOPIC_ALERT = "iot/alert"

parser = argparse.ArgumentParser(description="Simulator ESP32")
parser.add_argument("--broker", default=os.getenv("MQTT_BROKER", "localhost"))
parser.add_argument("--port", type=int, default=1883)
parser.add_argument("--interval", type=float, default=3.0, help="detik antar pengiriman")
parser.add_argument("--mode", choices=["normal", "panas"], default="normal",
                    help="normal: acak 25-32 C | panas: naik bertahap sampai 38 C lalu turun")
args = parser.parse_args()

lampu = "off"


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Terhubung ke broker {args.broker}:{args.port} (rc={reason_code})")
    # subscribe di sini agar otomatis aktif lagi setelah reconnect
    client.subscribe([(TOPIC_KONTROL, 0), (TOPIC_ALERT, 0)])


def on_message(client, userdata, msg):
    global lampu
    try:
        data = json.loads(msg.payload.decode())
    except ValueError:
        print(f"<- {msg.topic}: payload bukan JSON")
        return

    if msg.topic == TOPIC_KONTROL and data.get("device") == "lamp":
        lampu = data.get("action", lampu)
        print(f"<- KONTROL: lampu {lampu.upper()}")
    elif msg.topic == TOPIC_ALERT:
        print(f"<- ALERT: {data.get('message')}")


def baca_sensor(state):
    """Hasilkan (suhu, kelembaban) sesuai mode."""
    if args.mode == "panas":
        state["suhu"] += state["arah"] * random.uniform(0.3, 0.9)
        if state["suhu"] >= 38:
            state["arah"] = -1
        elif state["suhu"] <= 26:
            state["arah"] = 1
        suhu = state["suhu"]
    else:
        suhu = random.uniform(25, 32)
    return round(suhu, 1), round(random.uniform(55, 80), 1)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ESP32-Simulator")
client.on_connect = on_connect
client.on_message = on_message
client.reconnect_delay_set(min_delay=1, max_delay=10)
client.connect(args.broker, args.port, 60)
client.loop_start()

print(f"ESP32 Simulator berjalan (mode={args.mode}, interval={args.interval}s)... Ctrl+C untuk stop")
state = {"suhu": 27.0, "arah": 1}
try:
    while True:
        suhu, kelembaban = baca_sensor(state)
        data = {
            "suhu": suhu,
            "kelembaban": kelembaban,
            "timestamp": datetime.now().isoformat()
        }
        client.publish(TOPIC_SENSOR, json.dumps(data))
        print(f"-> Publish: {data}")
        time.sleep(args.interval)
except KeyboardInterrupt:
    print("\nBerhenti.")
finally:
    client.loop_stop()
    client.disconnect()