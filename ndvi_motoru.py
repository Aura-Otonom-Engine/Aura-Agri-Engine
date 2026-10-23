import numpy as np

def calculate_vegetation_indices(nir_band: np.ndarray, red_band: np.ndarray, swir_band: np.ndarray = None) -> dict:
    """Hassas tarım için spektral bantlardan NDVI ve NDWI (Nem İndeksi) hesaplar."""
    epsilon = 1e-8
    
    # NDVI: Normalleştirilmiş Fark Bitki İndeksi (Bitki Sağlığı)
    ndvi = (nir_band - red_band) / (nir_band + red_band + epsilon)
    results = {
        "ndvi_mean": float(np.mean(ndvi)),
        "ndvi_min": float(np.min(ndvi)),
        "ndvi_max": float(np.max(ndvi))
    }
    
    # NDWI: Normalleştirilmiş Fark Su İndeksi (Bitki Su Stresi)
    if swir_band is not None:
        ndwi = (nir_band - swir_band) / (nir_band + swir_band + epsilon)
        results["ndwi_mean"] = float(np.mean(ndwi))
        
    return results

def evaluate_crop_health(ndvi_val: float) -> str:
    """NDVI değerine göre otonom aksiyon kararı verir."""
    if ndvi_val >= 0.65:
        return "OPTIMAL: Bitki gelişimi kusursuz. Rutin sulama/gübreleme devam."
    elif 0.40 <= ndvi_val < 0.65:
        return "UYARI: Hafif nem stresi veya klorofil düşüşü. Hedefli sulama önerilir."
    else:
        return "KRITIK ALARM: Şiddetli kuraklık, hastalık veya toprak verimsizliği. Acil müdahale!"

if __name__ == "__main__":
    np.random.seed(42)
    # Sentinel-2 simüle bantları (B8=NIR, B4=Red, B11=SWIR)
    nir_sample = np.random.uniform(0.3, 0.8, (100, 100))
    red_sample = np.random.uniform(0.05, 0.2, (100, 100))
    swir_sample = np.random.uniform(0.1, 0.4, (100, 100))

    metrics = calculate_vegetation_indices(nir_sample, red_sample, swir_sample)
    decision = evaluate_crop_health(metrics["ndvi_mean"])

    print("========================================")
    print("   AURA AGRI-ENGINE TELEMETRI PANELİ    ")
    print("========================================")
    print(f"Ortalama NDVI (Sağlık): {metrics['ndvi_mean']:.3f}")
    print(f"Ortalama NDWI (Su Durumu): {metrics['ndwi_mean']:.3f}")
    print(f"Sistem Kararı: {decision}")
    print("========================================")