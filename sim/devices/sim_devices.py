import json
import random
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883

device_states = {
    "door_lock_01": "NORMAL",
    "rfid_01": "NORMAL",
    "aq_sensor_01": "NORMAL",
    "meter_01": "NORMAL",
    "cctv_01": "NORMAL",
}

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[!] Failed to connect: {reason_code}")
    else:
        print("[*] Connected to isolated MQTT broker.")
        client.subscribe("campus/lab1/control/+", qos=1)
        print("[*] Listening for AI Agent control commands on campus/lab1/control/+")

def on_message(client, userdata, msg):
    try:
        device_id = msg.topic.split("/")[-1]
        cmd = json.loads(msg.payload.decode())
        action = cmd.get("action", "").upper()

        if device_id in device_states and action in ("QUARANTINED", "QUARANTINE", "DECOY", "RESTORE", "NORMAL"):
            new_state = "QUARANTINED" if action == "QUARANTINE" else ("NORMAL" if action == "RESTORE" else action)
            device_states[device_id] = new_state
            print(f"\n[AGENT ACTION] {device_id} switched to -> {new_state}\n")
    except Exception as e:
        print(f"[!] Control message error: {e}")

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="campus-sim-wing1"
)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

print("[*] Campus Lab Wing 1 Simulator Running... (Ctrl+C to stop)")

try:
    while True:
        ts = datetime.now(timezone.utc).isoformat()

        telemetry = [
            ("door_lock_01", "campus/lab1/door_lock", {
                "device_id": "door_lock_01", "status": "LOCKED", "last_rfid": "NONE", "timestamp": ts
            }),
            ("rfid_01", "campus/lab1/rfid_scanner", {
                "device_id": "rfid_01", "event": "IDLE", "badge_id": None, "timestamp": ts
            }),
            ("aq_sensor_01", "campus/lab1/air_quality", {
                "device_id": "aq_sensor_01", "co2_ppm": random.randint(410, 480),
                "temp_c": round(random.uniform(22.5, 24.0), 1), "status": "NORMAL", "timestamp": ts
            }),
            ("meter_01", "campus/lab1/smart_meter", {
                "device_id": "meter_01", "power_kw": round(random.uniform(1.8, 2.4), 2),
                "network_conns": random.randint(1, 3), "timestamp": ts
            }),
            ("cctv_01", "campus/lab1/cctv_cam", {
                "device_id": "cctv_01", "heartbeat": "ONLINE", "fps": 30, "timestamp": ts
            }),
        ]

        for dev_id, topic, payload in telemetry:
            state = device_states[dev_id]
            if state == "QUARANTINED":
                client.publish(topic, json.dumps({"device_id": dev_id, "state": "QUARANTINED", "timestamp": ts}), qos=1)
            elif state == "DECOY":
                payload["state"] = "DECOY_ACTIVE"
                client.publish(topic, json.dumps(payload), qos=1)
            else:
                payload["state"] = "NORMAL"
                client.publish(topic, json.dumps(payload), qos=1)

        time.sleep(2)

except KeyboardInterrupt:
    print("\n[*] Stopping simulator...")
    client.loop_stop()
    client.disconnect()
