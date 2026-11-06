import os
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler
import httpx

from tarla_analiz import TarlaParselMotoru
from veritabani import veritabani_baslat, analiz_ve_aksiyon_kaydet, DB_YOLU
from uydu_servisi import SentinelUyduServisi
from piksel_analiz import gercek_banttan_ndvi_cikar
from mqtt_vana import vana_emri_gonder
from telegram_servisi import sulama_raporu_gonder
from uydu_servisi import tarla_spektral_analiz_yap

veritabani_baslat()
uydu_servisi = SentinelUyduServisi()

# Arka Plan Hava Durumu ve Yağış Kontrolü
async def hava_durumu_ve_yagis_kontrol(enlem: float, boylam: float):
    """Open-Meteo API üzerinden son 48 saatlik yağış ve hava durumunu çeker."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={enlem}&longitude={boylam}&current=temperature_2m,relative_humidity_2m&past_days=2&hourly=precipitation"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                hourly_precip = data.get("hourly", {}).get("precipitation", [])
                toplam_yagis = sum(hourly_precip[-48:]) if hourly_precip else 0.0
                return {"basarili": True, "son_48s_yagis_mm": toplam_yagis}
    except Exception:
        pass
    return {"basarili": False, "son_48s_yagis_mm": 0.0}

# Otonom Tarama Fonksiyonu (Hem API hem Zamanlayıcı tarafından kullanılır)
def otonom_tarama_gorevi(parsel_adi: str = "Alpha-1 Mısır Sahası", enlem: float = 38.6748, boylam: float = 39.2225, alan_dekar: float = 250.0, grid_boyutu: int = 4):
    try:
        print(f"\n⏰ [OTONOM GÖREV TETİKLENDİ] {parsel_adi} için uydu analizi başlıyor...")
        uydu_raporu = uydu_servisi.canli_bant_verisi_cek(enlem, boylam)
        
        rapor = None
        b04_url = uydu_raporu.get("kirmizi_bant_url")
        b08_url = uydu_raporu.get("nir_bant_url")

        if b04_url and b08_url:
            piksel_sonuc = gercek_banttan_ndvi_cikar(b04_url, b08_url, grid_boyutu=grid_boyutu)
            if piksel_sonuc.get("basarili"):
                rapor = {
                    "parsel": parsel_adi,
                    "koordinat": f"{enlem}, {boylam}",
                    "alan_dekar": alan_dekar,
                    "genel_ndvi": piksel_sonuc["genel_ndvi"],
                    "genel_ndwi": round(piksel_sonuc["genel_ndvi"] * 0.72, 3),
                    "sektorler": piksel_sonuc["sektorler"],
                    "mudahale_bekleyen_sektorler": piksel_sonuc["mudahale_bekleyen_sektorler"],
                    "sulama_sonrasi_mi": False
                }

        if rapor is None:
            motor = TarlaParselMotoru(parsel_adi=parsel_adi, enlem=enlem, boylam=boylam, alan_dekar=alan_dekar)
            rapor = motor.bolgesel_telemetri_tara(grid_boyutu=grid_boyutu, sulama_tamamlandi_mi=False)

        rapor["uydu_meta"] = uydu_raporu

        sulama_emirleri = analiz_ve_aksiyon_kaydet(rapor)

        for emir in sulama_emirleri:
            sektor_adi = emir.get("sektor", "BILINMEYEN_SEKTOR")
            su_miktari = emir.get("hedef_su_ton", 0.0)
            vana_emri_gonder(sektor_id=sektor_adi, durum="ACIK", su_miktari_ton=su_miktari)

        sulama_raporu_gonder(
            parsel_adi=rapor["parsel"],
            genel_ndvi=rapor["genel_ndvi"],
            emirler=sulama_emirleri
        )
        print(f"✅ [OTONOM GÖREV TAMAMLANDI] {len(sulama_emirleri)} sektöre müdahale emri verildi.")
        return rapor, sulama_emirleri
    except Exception as e:
        print(f"❌ [OTONOM GÖREV HATASI]: {str(e)}")
        return None, []

# Arka Plan Zamanlayıcı Yapılandırması
scheduler = BackgroundScheduler(daemon=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(otonom_tarama_gorevi, 'cron', hour=6, minute=0, id="gunluk_tarama")
    scheduler.start()
    print("🚀 [APScheduler] Otonom tarama zamanlayıcısı arka planda başlatıldı.")
    yield
    scheduler.shutdown()
    print("🛑 [APScheduler] Zamanlayıcı durduruldu.")

app = FastAPI(
    title="Aura Agri-Engine API",
    description="Otonom Hassas Tarım, Telemetri ve Sulama Karar Motoru",
    version="2.0.0",
    lifespan=lifespan
)

MEVCUT_DIZIN = os.path.dirname(os.path.abspath(__file__))
SABLON_DIZINI = os.path.join(MEVCUT_DIZIN, "templates_agri")

# Kök Dizin Rotası (Tarayıcının doğrudan index.html açmasını sağlar)
@app.get("/", response_class=HTMLResponse)
async def ana_sayfa():
    dosya_yolu = os.path.join(SABLON_DIZINI, "index.html")
    if os.path.exists(dosya_yolu):
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Aura Agri-Engine Çalışıyor ancak index.html bulunamadı!</h3>"

class TarlaIstekModel(BaseModel):
    parsel_adi: str
    enlem: float
    boylam: float
    alan_dekar: float
    urun_tipi: str = "Bugday/Misir"
    grid_boyutu: int = 4
    sulama_sonrasi_mi: bool = False

@app.post("/api/v1/tarla/tara-ve-kaydet")
async def tarlayi_tara_ve_kaydet(istek: TarlaIstekModel):
    analiz = tarla_spektral_analiz_yap(istek.enlem, istek.boylam, istek.alan_dekar, istek.grid_boyutu)
    
    hava_bilgisi = await hava_durumu_ve_yagis_kontrol(istek.enlem, istek.boylam)
    son_yagis = hava_bilgisi.get("son_48s_yagis_mm", 0.0)
    
    ndvi = analiz["genel_ndvi"]
    ndwi = analiz["genel_ndwi"]
    
    onerilen_su = round(istek.alan_dekar * 0.5, 1)
    recete_mesaji = ""
    durum_tipi = "normal"
    
    if son_yagis > 3.0:
        onerilen_su = 0.0
        durum_tipi = "yagis"
        recete_mesaji = f"🌧️ Son 48 saatte {son_yagis} mm yağış alındı. Toprak neme doyduğu için sulama otomatik askıya alındı."
    elif ndvi < 0.40 and ndwi < 0.20:
        onerilen_su = round(istek.alan_dekar * 1.2, 1)
        durum_tipi = "kurak"
        recete_mesaji = f"🚨 Kritik Kuraklık: Bitki kök bölgesinde su stresi tespit edildi. Acil {onerilen_su} ton sulama önerilir."
    elif ndvi < 0.45 and ndwi >= 0.25:
        onerilen_su = round(istek.alan_dekar * 0.3, 1)
        durum_tipi = "gubre"
        recete_mesaji = f"🧪 Azot/Gübre İhtiyacı: Toprak nemi yeterli (%{ndwi*100:.0f}) ancak klorofil seviyesi düşük. Su yerine 1 dekar için taban gübresi (Azot) takviyesi önerilir."
    else:
        recete_mesaji = f"🌱 Bitki örtüsü ve toprak nemi dengeli seyrediyor. Ekstra müdahaleye gerek yok."

    return {
        "basarili": True,
        "analiz_raporu": analiz,
        "akilli_analiz": {
            "son_yagis_mm": son_yagis,
            "durum_tipi": durum_tipi,
            "onerilen_su_ton": onerilen_su,
            "recete_mesaji": recete_mesaji,
            "urun_tipi": istek.urun_tipi
        },
        "otonom_sulama_emirleri": [{"sektor": f"Ana Vana ({istek.urun_tipi})", "hedef_su_ton": onerilen_su}] if onerilen_su > 0 else []
    }

@app.get("/api/v1/sulama-emirleri")
def sulama_emirlerini_getir():
    try:
        conn = sqlite3.connect(DB_YOLU)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sulama_emirleri ORDER BY id DESC LIMIT 50")
        satirlar = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"toplam_emir": len(satirlar), "emirler": satirlar}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kayıtlar çekilemedi: {str(e)}")

class EmirDurumGuncelleme(BaseModel):
    durum: str = Field(default="TAMAMLANDI_KAPATILDI")

@app.patch("/api/v1/sulama-emirleri/{emir_id}/durum")
def vana_emri_guncelle(emir_id: int, istek: EmirDurumGuncelleme):
    try:
        conn = sqlite3.connect(DB_YOLU)
        cursor = conn.cursor()
        
        cursor.execute("SELECT sektor_id FROM sulama_emirleri WHERE id = ?", (emir_id,))
        kayit = cursor.fetchone()
        
        cursor.execute(
            "UPDATE sulama_emirleri SET durum = ? WHERE id = ?",
            (istek.durum, emir_id)
        )
        conn.commit()
        conn.close()

        if kayit:
            sektor_adi = kayit[0]
            vana_emri_gonder(sektor_id=sektor_adi, durum="KAPALI", su_miktari_ton=0.0)

        return {"basarili": True, "emir_id": emir_id, "yeni_durum": istek.durum}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Durum güncellenemedi: {str(e)}")

class SulamaOnayIstek(BaseModel):
    parsel_adi: str
    toplam_su_ton: float
    emirler: list
    genel_ndvi: float

@app.post("/api/v1/sulama/onayla-ve-baslat")
def sulama_onayla_ve_baslat(istek: SulamaOnayIstek):
    try:
        sektor_sayisi = max(len(istek.emirler), 1)
        sektor_basina_su = round(istek.toplam_su_ton / sektor_sayisi, 2)

        guncel_emirler = []
        for e in istek.emirler:
            sektor_adi = e.get("sektor", "Sektör")
            vana_emri_gonder(sektor_id=sektor_adi, durum="ACIK", su_miktari_ton=sektor_basina_su)
            guncel_emirler.append({"sektor": sektor_adi, "hedef_su_ton": sektor_basina_su})

        sulama_raporu_gonder(
            parsel_adi=istek.parsel_adi,
            genel_ndvi=istek.genel_ndvi,
            emirler=guncel_emirler
        )
        return {"basarili": True, "verilen_su_ton": istek.toplam_su_ton}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))