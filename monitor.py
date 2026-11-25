import json
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883

def on_connect(client, userdata, flags, reason_code, properties):
    print("[*] Live Security Monitor Active on campus/lab1/# ...\n")
    client.subscribe("campus/lab1/#", qos=1)

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode())
    except Exception:
        return

    # Option 1: Coordinated Intrusion
    if data.get("heartbeat") == "OFFLINE":
        print(f"🚨 [ATTACK ATTEMPT - OPTION 1] CCTV Tampering on {topic}: {data}")
    elif data.get("last_rfid") == "UNAUTHORIZED_BYPASS":
        print(f"🚨 [ATTACK ATTEMPT - OPTION 1] Forced Door Unlock on {topic}: {data}")

    # Option 2: Sensor Spoofing + Prompt Injection
    elif "IGNORE ALL PREVIOUS INSTRUCTIONS" in str(data.get("status", "")).upper():
        print(f"🚨 [ATTACK ATTEMPT - OPTION 2] Prompt Injection + Spoofing on {topic}: {data}")

    # Option 3: Lateral Movement / Port Scan
    elif data.get("anomaly_flag") or data.get("network_conns", 0) > 50:
        print(f"🚨 [ATTACK ATTEMPT - OPTION 3] Lateral Movement / Port Scan on {topic}: {data}")

    # Control Commands (Option 4)
    elif "/control/" in topic:
        print(f"🛡️ [AGENT CONTROL] Command sent to {topic}: {data}")

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="live-attack-monitor"
)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()
