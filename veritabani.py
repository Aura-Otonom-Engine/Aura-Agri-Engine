import sqlite3
from datetime import datetime

DB_YOLU = "aura_agri.db"

def veritabani_baslat():
    """Gerekli tabloları SQLite üzerinde oluşturur."""
    conn = sqlite3.connect(DB_YOLU)
    cursor = conn.cursor()

    # Parsel telemetri geçmişi tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parsel_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parsel_adi TEXT NOT NULL,
            koordinat TEXT NOT NULL,
            alan_dekar REAL NOT NULL,
            genel_ndvi REAL NOT NULL,
            genel_ndwi REAL NOT NULL,
            riskli_sektorler TEXT NOT NULL,
            olusturulma_tarihi TEXT NOT NULL
        )
    """)

    # Otonom vana/sulama tetikleme log tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sulama_emirleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parsel_adi TEXT NOT NULL,
            sektor_id TEXT NOT NULL,
            emir_tipi TEXT NOT NULL,
            su_miktari_ton REAL NOT NULL,
            durum TEXT NOT NULL,
            zaman TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def analiz_ve_aksiyon_kaydet(rapor: dict) -> list:
    """Telemetriyi kaydeder ve riskli sektörler için sulama emri üretir."""
    conn = sqlite3.connect(DB_YOLU)
    cursor = conn.cursor()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    riskli_str = ",".join(rapor["mudahale_bekleyen_sektorler"])

    # 1. Parsel Analizini Kaydet
    cursor.execute("""
        INSERT INTO parsel_kayitlari (
            parsel_adi, koordinat, alan_dekar, genel_ndvi, genel_ndwi, riskli_sektorler, olusturulma_tarihi
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        rapor["parsel"],
        rapor["koordinat"],
        rapor["alan_dekar"],
        rapor["genel_ndvi"],
        rapor["genel_ndwi"],
        riskli_str,
        simdi
    ))

    uretilen_emirler = []

    # 2. Riskli Sektörler İçin Otonom Sulama Emri Oluştur
    # Her sektör için dekar başına düşen su ihtiyacı hesaplanır
    sektor_basi_alan = rapor["alan_dekar"] / len(rapor["sektorler"])
    for sektor_id in rapor["mudahale_bekleyen_sektorler"]:
        # Ton cinsinden hesaplanan ihtiyaç (Örn: dekar başına 5 ton hedefli su)
        ihtiyac_su = round(sektor_basi_alan * 5.0, 1)
        
        cursor.execute("""
            INSERT INTO sulama_emirleri (
                parsel_adi, sektor_id, emir_tipi, su_miktari_ton, durum, zaman
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            rapor["parsel"],
            sektor_id,
            "OTONOM_HEDEF_SULAMA",
            ihtiyac_su,
            "ONAYLANDI_VANA_AC",
            simdi
        ))
        
        uretilen_emirler.append({
            "sektor": sektor_id,
            "aksiyon": "VANA_AC",
            "hedef_su_ton": ihtiyac_su,
            "durum": "ONAYLANDI"
        })

    conn.commit()
    conn.close()
    return uretilen_emirler

if __name__ == "__main__":
    veritabani_baslat()
    print("Aura Agri veritabanı tabloları başarıyla oluşturuldu: aura_agri.db")