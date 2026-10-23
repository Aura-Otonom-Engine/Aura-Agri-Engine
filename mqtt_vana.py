import paho.mqtt.client as mqtt
import json
import os

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

def vana_emri_gonder(sektor_id: str, durum: str, su_miktari_ton: float):
    client = mqtt.Client()
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        payload = {
            "sektor": sektor_id,
            "komut": durum,
            "su_ton": su_miktari_ton,
            "kaynak": "Sentinel-2 Otonom Spektral Karar Motoru"
        }
        topic = f"aura/tarla/vana/{sektor_id}"
        client.publish(topic, json.dumps(payload))
        client.disconnect()
        print(f"[MQTT] {topic} konusuna emir iletildi: {durum} ({su_miktari_ton} ton)")
        return True
    except Exception as e:
        print(f"[MQTT HATA] Vana sinyali iletilemedi: {e}")
        return False

if __name__ == "__main__":
    vana_emri_gonder("SEKTOR_1_1", "ACIK", 78.5)