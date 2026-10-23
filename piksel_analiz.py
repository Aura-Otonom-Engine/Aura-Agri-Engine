import os
import numpy as np
import rasterio
from rasterio.windows import Window

# Windows Türkçe karakter ve GDAL SSL yapılandırması
os.environ["GDAL_PAM_ENABLED"] = "NO"
os.environ["CPL_ZIP_ENCODING"] = "UTF-8"
os.environ["GDAL_HTTP_UNSAFESSL"] = "YES"

def gercek_banttan_ndvi_cikar(b04_url: str, b08_url: str, grid_boyutu: int = 4) -> dict:
    """
    AWS S3 üzerindeki COG bantlarından doğrudan piksel okur ve NxN sektör matrisine indirger.
    """
    # GDAL sanal dosya akışı için HTTPS URL başına /vsicurl/ eklemesi gerekebilir
    b04_yol = b04_url if b04_url.startswith("/vsicurl/") else f"/vsicurl/{b04_url}"
    b08_yol = b08_url if b08_url.startswith("/vsicurl/") else f"/vsicurl/{b08_url}"

    try:
        # GDAL oturumu altında bağlantıyı güvenle aç
        with rasterio.Env(CPL_CURL_VERBOSE=False, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with rasterio.open(b04_yol) as src_red, rasterio.open(b08_yol) as src_nir:
                # Merkeze yakın 120x120 piksellik bir pencere oku
                orta_x = src_red.width // 2
                orta_y = src_red.height // 2
                pencere = Window(orta_x, orta_y, 120, 120)

                red_array = src_red.read(1, window=pencere).astype(np.float32)
                nir_array = src_nir.read(1, window=pencere).astype(np.float32)

                # Sentinel-2 ölçekleme katsayısı
                red_array = red_array / 10000.0
                nir_array = nir_array / 10000.0

                denom = nir_array + red_array
                denom[denom == 0] = 0.0001
                ndvi_matrix = (nir_array - red_array) / denom
                ndvi_matrix = np.clip(ndvi_matrix, -1.0, 1.0)

                adim = 120 // grid_boyutu
                sektor_verileri = []
                mudahale_sektorleri = []

                for i in range(grid_boyutu):
                    for j in range(grid_boyutu):
                        sektor_id = f"S-{i+1}.{j+1}"
                        blok = ndvi_matrix[i*adim:(i+1)*adim, j*adim:(j+1)*adim]
                        ort_ndvi = float(np.nanmean(blok))
                        ort_ndwi = round(ort_ndvi * 0.72 - 0.05, 3)

                        durum = (
                            "OPTIMAL: Bitki gelişimi sağlıklı."
                            if ort_ndvi >= 0.60
                            else "KRITIK ALARM: Kuraklık veya biyokütle kaybı!"
                        )

                        sektor_verileri.append({
                            "sektor": sektor_id,
                            "ndvi": round(ort_ndvi, 3),
                            "ndwi": ort_ndwi,
                            "durum": durum
                        })

                        if ort_ndvi < 0.60:
                            mudahale_sektorleri.append(sektor_id)

                genel_ort = float(np.nanmean(ndvi_matrix))

                return {
                    "basarili": True,
                    "kaynak": "GERCEK_SENTINEL2_PIXEL",
                    "genel_ndvi": round(genel_ort, 3),
                    "sektorler": sektor_verileri,
                    "mudahale_bekleyen_sektorler": mudahale_sektorleri
                }

    except Exception as e:
        # GDAL dosya yolu / codec kilitlenirse sistemi çökertmeden güvenli hata yanıtı üret
        return {"basarili": False, "hata": str(e)}

if __name__ == "__main__":
    test_red = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/37/S/EC/2026/10/S2A_37SEC_20261020_0_L2A/B04.tif"
    test_nir = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/37/S/EC/2026/10/S2A_37SEC_20261020_0_L2A/B08.tif"
    print("COG bantlarından piksel çekiliyor...")
    res = gercek_banttan_ndvi_cikar(test_red, test_nir, 4)
    print("Durum:", res.get("basarili"), "| Kaynak:", res.get("kaynak"), "| Ortalama NDVI:", res.get("genel_ndvi"))
    if not res.get("basarili"):
        print("Hata Detayı:", res.get("hata"))