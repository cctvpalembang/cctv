"""Kondisi lalu lintas ruas jalan nasional per PPK dari TomTom Routing API (data resmi, perlu API key gratis).
Segmen & titik bantu (agar rute tetap di jalan nasional) ada di scripts/ruas_segmen.json,
diambil dari data ruas aplikasi karamullah-blip/overlay-ruas-jembatan. Menulis ruas.json untuk pita di halaman CCTV.
Hanya pustaka standar Python. Kunci dibaca dari variabel lingkungan TOMTOM_KEY."""
import json, math, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def hav(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def kategori(rasio):
    for batas, nama in [(1.1, "Lancar"), (1.25, "Ramai lancar"), (1.5, "Padat"), (2.0, "Macet")]:
        if rasio < batas:
            return nama
    return "Macet parah"


def olah(route):
    s = route["summary"]
    pts = [(p["latitude"], p["longitude"]) for leg in route["legs"] for p in leg["points"]]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + hav(pts[i - 1], pts[i]))
    km = {"padat": 0.0, "macet": 0.0, "parah": 0.0}
    for sec in route.get("sections", []):
        if sec.get("sectionType") != "TRAFFIC":
            continue
        a, b = sec["startPointIndex"], min(sec["endPointIndex"], len(cum) - 1)
        panjang = (cum[b] - cum[a]) / 1000
        m = sec.get("magnitudeOfDelay", 0)
        if m in (3, 4):
            km["parah"] += panjang
        elif m == 2:
            km["macet"] += panjang
        elif m == 1:
            km["padat"] += panjang
    L, T = s["lengthInMeters"] / 1000, s["travelTimeInSeconds"]
    T0 = s.get("noTrafficTravelTimeInSeconds") or T
    return {"jarak_km": round(L, 1), "waktu_menit": round(T / 60), "kecepatan": round(L / (T / 3600)) if T else 0,
            "tunda_menit": round(s.get("trafficDelayInSeconds", 0) / 60),
            "macet_parah_km": round(km["parah"], 1), "macet_km": round(km["macet"], 1), "padat_km": round(km["padat"], 1),
            "kategori": kategori(T / T0 if T0 else 1)}


def rute(key, titik):
    loc = ":".join("%f,%f" % (a, b) for a, b in titik)
    q = urllib.parse.urlencode({"key": key, "traffic": "true", "travelMode": "car", "routeType": "fastest",
                                "sectionType": "traffic", "computeTravelTimeFor": "all", "language": "id-ID"})
    url = "https://api.tomtom.com/routing/1/calculateRoute/%s/json?%s" % (urllib.parse.quote(loc, safe=",:"), q)
    return json.load(urllib.request.urlopen(url, timeout=60))["routes"][0]


def main(out_path):
    key = os.environ.get("TOMTOM_KEY", "").strip()
    if not key:
        print("TOMTOM_KEY belum diisi; ruas.json dilewati")
        return
    segs = json.load(open(os.path.join(HERE, "ruas_segmen.json"), encoding="utf-8"))
    hasil, gagal = [], 0
    for s in segs:
        arah = []
        for nama, titik in [(s["naik"], s["titik"]), (s["turun"], s["titik"][::-1])]:
            try:
                arah.append(dict(arah=nama, **olah(rute(key, titik))))
            except Exception as e:
                gagal += 1
                print("gagal", s["ppk"], nama, e, file=sys.stderr)
            time.sleep(0.5)
        if arah:
            hasil.append({"ppk": s["ppk"], "nama": s["nama"], "arah": arah})
    if not hasil:
        sys.exit("semua permintaan TomTom gagal; ruas.json tidak diubah")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sumber": "TomTom Traffic", "ruas": hasil},
                  f, ensure_ascii=False, indent=1)
    print(len(hasil), "ruas ditulis,", gagal, "gagal")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ruas.json")
