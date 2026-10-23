import time
import requests

API_URL = "http://127.0.0.1:8000"

def bekleyen_emirleri_isle():
    print("==================================================")
    print("   AURA IOT: SAHA VANA DENETLEYİCİSİ DEVREDE      ")
    print("==================================================")
    
    try:
        yanit = requests.get(f"{API_URL}/api/v1/sulama-emirleri")
        if yanit.status_code != 200:
            print(f"[HATA] API ile bağlantı kurulamadı: {yanit.status_code}")
            return

        emirler = yanit.json().get("emirler", [])
        aktif_emirler = [e for e in emirler if e["durum"] == "ONAYLANDI_VANA_AC"]

        if not aktif_emirler:
            print("[BİLGİ] Bekleyen aktif vana emri yok. Bütün sektörler sulanmış.")
            return

        print(f"[BİLGİ] {len(aktif_emirler)} adet bekleyen sulama emri işleme alınıyor...\n")

        for emir in aktif_emirler:
            sektor = emir["sektor_id"]
            su_ton = emir["su_miktari_ton"]
            emir_id = emir["id"]

            print(f"▶ [RÖLE TETİKLENDİ] Sektör: {sektor} | Hedef: {su_ton} Ton")
            print(f"   -> {sektor} Solenoid Vana AÇILDI...")
            time.sleep(0.5)  # Simüle edilmiş su akışı
            print(f"   -> {sektor} Hedef su basıldı. Vana KAPATILDI.")

            # API'ye durum güncelleme gönder
            guncelleme = requests.patch(
                f"{API_URL}/api/v1/sulama-emirleri/{emir_id}/durum",
                json={"durum": "TAMAMLANDI_KAPATILDI"}
            )
            
            if guncelleme.status_code == 200:
                print(f"   -> [ONAY ALINDI] Emir ID {emir_id} veritabanında TAMAMLANDI yapıldı.\n")
            else:
                print(f"   -> [HATA] Emir ID {emir_id} güncellenemedi!\n")

        print("==================================================")
        print("Tüm vanalar kapatıldı ve sistem senkronize edildi.")
        print("==================================================")

    except requests.exceptions.ConnectionError:
        print("[HATA] FastAPI sunucusuna ulaşılamadı!")

if __name__ == "__main__":
    bekleyen_emirleri_isle()