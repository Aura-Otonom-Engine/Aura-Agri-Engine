import os
import sqlite3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from tarla_analiz import TarlaParselMotoru
from veritabani import veritabani_baslat, analiz_ve_aksiyon_kaydet, DB_YOLU
from uydu_servisi import SentinelUyduServisi
from piksel_analiz import gercek_banttan_ndvi_cikar
from mqtt_vana import vana_emri_gonder
from telegram_servisi import sulama_raporu_gonder

veritabani_baslat()
uydu_servisi = SentinelUyduServisi()

app = FastAPI(
    title="Aura Agri-Engine API",
    description="Otonom Hassas Tarım, Telemetri ve Sulama Karar Motoru",
    version="2.0.0"
)

MEVCUT_DIZIN = os.path.dirname(os.path.abspath(__file__))
SABLON_DIZINI = os.path.join(MEVCUT_DIZIN, "templates_agri")
templates = Jinja2Templates(directory=SABLON_DIZINI)

class TarlaIstek(BaseModel):
    parsel_adi: str = Field(..., json_schema_extra={"example": "Alpha-1 Mısır Sahası"})
    enlem: float = Field(..., ge=-90.0, le=90.0, json_schema_extra={"example": 38.6748})
    boylam: float = Field(..., ge=-180.0, le=180.0, json_schema_extra={"example": 39.2225})
    alan_dekar: float = Field(..., gt=0, json_schema_extra={"example": 250.0})
    grid_boyutu: int = Field(default=4, ge=2, le=10, json_schema_extra={"example": 4})
    sulama_sonrasi_mi: bool = Field(default=False, json_schema_extra={"example": False})

@app.get("/", response_class=HTMLResponse)
def dashboard_arayuzu(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/v1/tarla/tara-ve-kaydet")
def tarla_analiz_ve_kaydet(istek: TarlaIstek):
    try:
        # 1. Sentinel-2 Canlı Uydu Meta Verisini Sorgula
        uydu_raporu = uydu_servisi.canli_bant_verisi_cek(istek.enlem, istek.boylam)
        
        rapor = None
        b04_url = uydu_raporu.get("kirmizi_bant_url")
        b08_url = uydu_raporu.get("nir_bant_url")

        # 2. Gerçek COG Piksel Taraması
        if not istek.sulama_sonrasi_mi and b04_url and b08_url:
            piksel_sonuc = gercek_banttan_ndvi_cikar(b04_url, b08_url, grid_boyutu=istek.grid_boyutu)
            if piksel_sonuc.get("basarili"):
                rapor = {
                    "parsel": istek.parsel_adi,
                    "koordinat": f"{istek.enlem}, {istek.boylam}",
                    "alan_dekar": istek.alan_dekar,
                    "genel_ndvi": piksel_sonuc["genel_ndvi"],
                    "genel_ndwi": round(piksel_sonuc["genel_ndvi"] * 0.72 - 0.05, 3),
                    "sektorler": piksel_sonuc["sektorler"],
                    "mudahale_bekleyen_sektorler": piksel_sonuc["mudahale_bekleyen_sektorler"],
                    "sulama_sonrasi_mi": False
                }

        # Fallback veya Sulama Sonrası İyileşme Modeli
        if rapor is None:
            motor = TarlaParselMotoru(
                parsel_adi=istek.parsel_adi,
                enlem=istek.enlem,
                boylam=istek.boylam,
                alan_dekar=istek.alan_dekar
            )
            rapor = motor.bolgesel_telemetri_tara(
                grid_boyutu=istek.grid_boyutu,
                sulama_tamamlandi_mi=istek.sulama_sonrasi_mi
            )

        rapor["uydu_meta"] = uydu_raporu

        # 3. Veritabanı ve Karar Motoru
        sulama_emirleri = analiz_ve_aksiyon_kaydet(rapor)

        # 4. Sahadaki Fiziksel Vanalara Otonom MQTT Emri Fırlat
        for emir in sulama_emirleri:
            sektor_adi = emir.get("sektor", "BILINMEYEN_SEKTOR")
            su_miktari = emir.get("hedef_su_ton", 0.0)
            vana_emri_gonder(sektor_id=sektor_adi, durum="ACIK", su_miktari_ton=su_miktari)

        # 5. Telegram Bildirimini Fırlat
        sulama_raporu_gonder(
            parsel_adi=rapor["parsel"],
            genel_ndvi=rapor["genel_ndvi"],
            emirler=sulama_emirleri
        )

        return {
            "basarili": True,
            "analiz_raporu": rapor,
            "otonom_sulama_emirleri": sulama_emirleri
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İşlem sırasında hata: {str(e)}")

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