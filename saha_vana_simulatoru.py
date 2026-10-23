import paho.mqtt.client as mqtt
import json
import time

# VDS Sunucunun IP Adresini buraya yaz
SUNUCU_IP = "91.229.239.198"
PORT = 1883

def on_connect(client, userdata, flags, rc):
    print("--------------------------------------------------")
    print(f"[SAHA DONANIMI] ESP32 Röle Modülü Sunucuya Bağlandı! Kod: {rc}")
    print("[SAHA DONANIMI] Sektör vanaları uydu emirlerini dinliyor...")
    print("--------------------------------------------------")
    # Tüm sektör vanalarını dinlemeye alıyoruz
    client.subscribe("aura/tarla/vana/#")

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    sektor = payload.get("sektor")
    komut = payload.get("komut")
    su_ton = payload.get("su_ton")
    kaynak = payload.get("kaynak")
    
    print("\n⚡ [FİZİKSEL TETİKLEME ALINDI] ⚡")
    print(f"Konu (Topic) : {msg.topic}")
    print(f"Hedef Bölge  : {sektor}")
    print(f"Vana Durumu  : {komut}")
    print(f"Planlanan Su : {su_ton} Ton")
    print(f"Karar Verici : {kaynak}")
    if komut == "ACIK":
        print(">>> [RÖLE ÇEKTİ] 12V Selenoid Vana Açıldı! Sulama başladı... <<<")
    else:
        print(">>> [RÖLE BIRAKTI] Vana Kapandı. <<<")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"ESP32 Vana Simülatörü {SUNUCU_IP}:{PORT} adresine bağlanıyor...")
client.connect(SUNUCU_IP, PORT, 60)
client.loop_forever()