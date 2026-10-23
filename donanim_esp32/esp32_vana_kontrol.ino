#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// --- Ağ ve MQTT Sunucu Yapılandırması ---
const char* ssid = "TARLA_WIFI_ADI";             // Sahadaki Wi-Fi veya Mobil Erişim Noktası
const char* password = "TARLA_WIFI_SIFRESI";
const char* mqtt_server = "91.229.239.198";      // AlexHost VDS IP Adresimiz
const int mqtt_port = 1883;

// --- Vana Röle Pin Tanımları ---
const int VANA_S42_PIN = 23; // GPIO 23 -> Röle 1 (S-4.2)
const int VANA_S43_PIN = 22; // GPIO 22 -> Röle 2 (S-4.3)
const int VANA_S44_PIN = 21; // GPIO 21 -> Röle 3 (S-4.4)

WiFiClient espClient;
PubSubClient client(espClient);

void baglantilariKur() {
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[WIFI] Sahada internet bağlantısı sağlandı.");

  while (!client.connected()) {
    Serial.print("[MQTT] Bulut sunucuya bağlanıyor...");
    // Benzersiz Client ID ile bağlan
    String clientId = "ESP32_AuraTarla_" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      Serial.println(" Bağlandı!");
      // Tarladaki tüm sektörlerin emir konusunu dinlemeye al
      client.subscribe("aura/tarla/vana/#");
    } else {
      Serial.print(" Başarısız, rc=");
      Serial.print(client.state());
      Serial.println(" 5 saniye sonra tekrar denenecek.");
      delay(5000);
    }
  }
}

// Buluttan sulama emri geldiğinde tetiklenen fonksiyon
void callback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  deserializeJson(doc, payload, length);

  const char* sektor = doc["sektor"];
  const char* komut = doc["komut"];
  float su_ton = doc["su_ton"];

  Serial.println("=================================");
  Serial.printf("[EMİR ALINDI] Sektör: %s | Komut: %s | Su: %.1f Ton\n", sektor, komut, su_ton);

  int hedefPin = -1;
  if (strcmp(sektor, "S-4.2") == 0) hedefPin = VANA_S42_PIN;
  else if (strcmp(sektor, "S-4.3") == 0) hedefPin = VANA_S43_PIN;
  else if (strcmp(sektor, "S-4.4") == 0) hedefPin = VANA_S44_PIN;

  if (hedefPin != -1) {
    if (strcmp(komut, "ACIK") == 0) {
      digitalWrite(hedefPin, LOW); // Röle kartları LOW sinyali ile çeker
      Serial.printf("[RÖLE AKTİF] %s vanası açıldı, su akışı başladı.\n", sektor);
    } else {
      digitalWrite(hedefPin, HIGH); // HIGH sinyali ile röle bırakır
      Serial.printf("[RÖLE PASİF] %s vanası kapatıldı.\n", sektor);
    }
  }
  Serial.println("=================================");
}

void setup() {
  Serial.begin(115200);

  // Röle pinlerini çıkış yap ve varsayılan olarak kapalı tut (HIGH = Kapalı)
  pinMode(VANA_S42_PIN, OUTPUT);
  pinMode(VANA_S43_PIN, OUTPUT);
  pinMode(VANA_S44_PIN, OUTPUT);
  digitalWrite(VANA_S42_PIN, HIGH);
  digitalWrite(VANA_S43_PIN, HIGH);
  digitalWrite(VANA_S44_PIN, HIGH);

  WiFi.begin(ssid, password);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  baglantilariKur();
}

void loop() {
  if (!client.connected()) {
    baglantilariKur();
  }
  client.loop(); // MQTT dinleme döngüsü
}