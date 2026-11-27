#!/usr/bin/env python3
"""Hitung titik api (hotspot) NASA FIRMS 24 jam terakhir di Sumatera Selatan -> hotspot.json.
Memakai berkas CSV publik FIRMS (tanpa kunci API): VIIRS S-NPP, NOAA-20, NOAA-21 dan MODIS, wilayah Asia Tenggara.
Batas Sumsel memakai poligon perkiraan (kasar), jadi angka adalah perkiraan."""
import csv, io, json, sys, time, urllib.request

BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
SUMBER = [
    ("VIIRS S-NPP", "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_SouthEast_Asia_24h.csv"),
    ("VIIRS NOAA-20", "noaa-20-viirs-c2/csv/J1_VIIRS_C2_SouthEast_Asia_24h.csv"),
    ("VIIRS NOAA-21", "noaa-21-viirs-c2/csv/J2_VIIRS_C2_SouthEast_Asia_24h.csv"),
    ("MODIS", "modis-c6.1/csv/MODIS_C6_1_SouthEast_Asia_24h.csv"),
]
# Poligon perkiraan batas Provinsi Sumatera Selatan (lon, lat)
SUMSEL = [(102.07, -2.75), (102.55, -2.35), (103.20, -2.25), (103.75, -1.95), (104.25, -1.62), (104.55, -1.70),
          (104.90, -2.05), (105.35, -2.10), (105.80, -2.60), (106.05, -3.05), (106.10, -3.40), (105.85, -3.75),
          (105.20, -4.05), (104.75, -4.20), (104.40, -4.60), (104.10, -4.95), (103.75, -4.85), (103.40, -4.55),
          (103.10, -4.25), (102.85, -3.95), (102.55, -3.55), (102.30, -3.25)]
# Titik acuan untuk menyebut daerah terdekat
KOTA = [("Palembang", -2.976, 104.775), ("Banyuasin", -2.60, 104.60), ("Musi Banyuasin", -2.45, 103.85),
        ("Ogan Komering Ilir", -3.40, 105.40), ("Ogan Ilir", -3.25, 104.65), ("Muara Enim", -3.65, 103.77),
        ("PALI", -3.20, 104.10), ("Musi Rawas", -3.10, 102.90), ("Muratara", -2.60, 102.80), ("Lahat", -3.80, 103.50),
        ("OKU", -4.13, 104.17), ("OKU Timur", -3.85, 104.75), ("OKU Selatan", -4.55, 104.05), ("Empat Lawang", -3.75, 102.95),
        ("Prabumulih", -3.43, 104.23), ("Pagar Alam", -4.02, 103.25), ("Lubuklinggau", -3.30, 102.86)]


def di_dalam(x, y, poli=SUMSEL):
    ok, j = False, len(poli) - 1
    for i in range(len(poli)):
        xi, yi = poli[i]; xj, yj = poli[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ok = not ok
        j = i
    return ok


def terdekat(lat, lon):
    return min(KOTA, key=lambda k: (k[1] - lat) ** 2 + (k[2] - lon) ** 2)[0]


def main(out):
    titik, dipakai = [], []
    for nama, path in SUMBER:
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": "cctv-sumsel/1.0"})
            teks = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        except Exception as e:
            print("gagal", nama, e, file=sys.stderr); continue
        n = 0
        for r in csv.DictReader(io.StringIO(teks)):
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except Exception:
                continue
            if not (101.9 <= lon <= 106.3 and -5.1 <= lat <= -1.5) or not di_dalam(lon, lat):
                continue
            conf = (r.get("confidence") or "").strip().lower()
            # VIIRS: l/n/h ; MODIS: 0-100. Buang yang keyakinan rendah.
            if conf in ("l", "low") or (conf.isdigit() and int(conf) < 30):
                continue
            tinggi = conf in ("h", "high") or (conf.isdigit() and int(conf) >= 80)
            titik.append({"lat": round(lat, 3), "lon": round(lon, 3), "tinggi": tinggi, "satelit": nama,
                          "waktu": (r.get("acq_date") or "") + " " + (r.get("acq_time") or "")})
            n += 1
        dipakai.append(nama); print(nama, n, "titik")
    if not dipakai:
        sys.exit("semua sumber FIRMS gagal; hotspot.json tidak diubah")
    # Satu lokasi bisa terdeteksi beberapa satelit: gabungkan yang berjarak < ~1 km
    unik = []
    for t in sorted(titik, key=lambda t: not t["tinggi"]):
        if not any(abs(t["lat"] - u["lat"]) < 0.01 and abs(t["lon"] - u["lon"]) < 0.01 for u in unik):
            unik.append(t)
    per = {}
    for t in unik:
        k = terdekat(t["lat"], t["lon"]); per[k] = per.get(k, 0) + 1
    teratas = sorted(per.items(), key=lambda kv: -kv[1])[:3]
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sumber": "NASA FIRMS (" + ", ".join(dipakai) + ")",
                   "jumlah": len(unik), "tinggi": sum(t["tinggi"] for t in unik),
                   "teratas": [{"daerah": k, "jumlah": v} for k, v in teratas]}, f, ensure_ascii=False, indent=1)
    print("hotspot Sumsel:", len(unik), "teratas:", teratas)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "hotspot.json")
