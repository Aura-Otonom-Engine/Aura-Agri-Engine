import requests

TELEGRAM_BOT_TOKEN = "8814180241:AAGBCok9ByxM8tNquAMasNVFVaXatDi_Z0M"
TELEGRAM_CHAT_ID = "1475873960"

def telegram_bildirim_gonder(mesaj: str) -> bool:
    """Telegram botu üzerinden kullanıcıya anlık bildirim atar."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML"
    }
    try:
        yanit = requests.post(url, json=payload, timeout=25)
        return yanit.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM HATA] Bildirim gönderilemedi: {e}")
        return False

def sulama_raporu_gonder(parsel_adi: str, genel_ndvi: float, emirler: list):
    """Sentinel-2 analiz sonuçlarını ve vana kararlarını biçimlendirip gönderir."""
    if not emirler:
        mesaj = (
            f"🌱 <b>AURA AGRI ENGINE | BİLGİLENDİRME</b>\n\n"
            f"📍 <b>Parsel:</b> {parsel_adi}\n"
            f"📊 <b>Genel NDVI:</b> {genel_ndvi}\n"
            f"✅ Tüm sektörlerin nem seviyesi dengeli. Aktif sulama emri bulunmuyor."
        )
    else:
        emir_metinleri = []
        toplam_su = 0.0
        for e in emirler:
            sektor = e.get("sektor", "Bilinmeyen")
            su = e.get("hedef_su_ton", 0.0)
            toplam_su += su
            emir_metinleri.append(f"  • <b>{sektor}</b> ➔ <b>{su} Ton</b> (Vana: AÇIK)")

        emirler_govde = "\n".join(emir_metinleri)
        mesaj = (
            f"🛰️ <b>AURA AGRI ENGINE | OTONOM SULAMA ALARMI</b>\n\n"
            f"📍 <b>Parsel:</b> {parsel_adi}\n"
            f"📊 <b>Ortalama NDVI:</b> {genel_ndvi}\n"
            f"🚨 <b>Müdahale Edilen Sektörler:</b>\n{emirler_govde}\n\n"
            f"💧 <b>Toplam Planlanan Su:</b> {round(toplam_su, 1)} Ton\n"
            f"⚡ <i>MQTT üzerinden saha rölelerine açılış sinyali iletildi.</i>"
        )

    return telegram_bildirim_gonder(mesaj)

if __name__ == "__main__":
    print("Telegram test bildirimi fırlatılıyor...")
    ornek_emirler = [
        {"sektor": "S-4.2", "hedef_su_ton": 78.1},
        {"sektor": "S-4.3", "hedef_su_ton": 78.1},
        {"sektor": "S-4.4", "hedef_su_ton": 78.1}
    ]
    basarili = sulama_raporu_gonder("Alpha-1 Mısır Sahası", 0.38, ornek_emirler)
    if basarili:
        print("✅ Bildirim Telegram hesabına başarıyla ulaştı!")
    else:
        print("❌ Bildirim gönderilemedi, botu başlattığından emin ol.")