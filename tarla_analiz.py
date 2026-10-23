import numpy as np
from ndvi_motoru import calculate_vegetation_indices, evaluate_crop_health

class TarlaParselMotoru:
    def __init__(self, parsel_adi: str, enlem: float, boylam: float, alan_dekar: float):
        self.parsel_adi = parsel_adi
        self.enlem = enlem
        self.boylam = boylam
        self.alan_dekar = alan_dekar

    def bolgesel_telemetri_tara(self, grid_boyutu: int = 4, sulama_tamamlandi_mi: bool = False) -> dict:
        """
        Tarlayı NxN sektörlere böler.
        sulama_tamamlandi_mi = True ise sulanan sektörlerin sağlığı düzelmiş olarak hesaplanır.
        """
        # Temel sağlıklı sektör yansımaları
        nir = np.full((grid_boyutu, grid_boyutu), 0.70)
        red = np.full((grid_boyutu, grid_boyutu), 0.12)
        swir = np.full((grid_boyutu, grid_boyutu), 0.20)

        if not sulama_tamamlandi_mi:
            # Sulama öncesi: Sağ alt köşe kuraklık stresi (S-3.3, S-3.4, S-4.3, S-4.4)
            nir[2:, 2:] = 0.35
            red[2:, 2:] = 0.25
            swir[2:, 2:] = 0.45
        else:
            # Sulama sonrası: İyileşme simülasyonu (Nem ve klorofil toparlanmış)
            nir[2:, 2:] = 0.75
            red[2:, 2:] = 0.10
            swir[2:, 2:] = 0.18

        sektor_raporlari = []
        acil_mudahale_sektorleri = []

        for i in range(grid_boyutu):
            for j in range(grid_boyutu):
                sektor_id = f"S-{i+1}.{j+1}"
                sektor_metrics = calculate_vegetation_indices(
                    np.array([nir[i, j]]),
                    np.array([red[i, j]]),
                    np.array([swir[i, j]])
                )
                ndvi = sektor_metrics["ndvi_mean"]
                ndwi = sektor_metrics["ndwi_mean"]
                durum = evaluate_crop_health(ndvi)

                sektor_raporlari.append({
                    "sektor": sektor_id,
                    "ndvi": round(ndvi, 3),
                    "ndwi": round(ndwi, 3),
                    "durum": durum
                })

                if ndvi < 0.60:
                    acil_mudahale_sektorleri.append(sektor_id)

        genel_ozet = calculate_vegetation_indices(nir, red, swir)

        return {
            "parsel": self.parsel_adi,
            "koordinat": f"{self.enlem}, {self.boylam}",
            "alan_dekar": self.alan_dekar,
            "genel_ndvi": round(genel_ozet["ndvi_mean"], 3),
            "genel_ndwi": round(genel_ozet["ndwi_mean"], 3),
            "sektorler": sektor_raporlari,
            "mudahale_bekleyen_sektorler": acil_mudahale_sektorleri,
            "sulama_sonrasi_mi": sulama_tamamlandi_mi
        }

if __name__ == "__main__":
    parsel = TarlaParselMotoru("Alpha-1 Mısır Sahası", 38.6748, 39.2225, 250.0)
    print("--- SULAMA SONRASI TEST ---")
    rapor = parsel.bolgesel_telemetri_tara(grid_boyutu=4, sulama_tamamlandi_mi=True)
    print(f"Genel NDVI: {rapor['genel_ndvi']} | Kalan Riskli Sektör Sayısı: {len(rapor['mudahale_bekleyen_sektorler'])}")