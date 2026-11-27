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


URUT = ["Lancar", "Ramai lancar", "Padat", "Macet", "Macet parah"]


def naikkan(kat, km):
    # antrean panjang menaikkan kategori walau total tundaan kecil
    minimal = "Macet" if km["parah"] >= 2 else "Padat" if km["parah"] + km["macet"] >= 1 else "Lancar"
    return URUT[max(URUT.index(kat), URUT.index(minimal))]


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
    T0 = max(1, T - s.get("trafficDelayInSeconds", 0))  # waktu tanpa hambatan = waktu sekarang dikurangi tundaan lalu lintas
    return {"jarak_km": round(L, 1), "waktu_menit": round(T / 60), "kecepatan": round(L / (T / 3600)) if T else 0,
            "tunda_menit": round(s.get("trafficDelayInSeconds", 0) / 60),
            "macet_parah_km": round(km["parah"], 1), "macet_km": round(km["macet"], 1), "padat_km": round(km["padat"], 1),
            "kategori": naikkan(kategori(T / T0), km)}


def rute(key, titik):
    loc = ":".join("%f,%f" % (a, b) for a, b in titik)
    q = urllib.parse.urlencode({"key": key, "traffic": "true", "travelMode": "car", "routeType": "fastest",
                                "sectionType": "traffic", "computeTravelTimeFor": "all", "language": "id-ID",
                                "avoid": "tollRoads"})  # jalan nasional, bukan tol sejajar
    url = "https://api.tomtom.com/routing/1/calculateRoute/%s/json?%s" % (urllib.parse.quote(loc, safe=",:"), q)
    return json.load(urllib.request.urlopen(url, timeout=60))["routes"][0]


# titik macet yang pernah teramati (sheet "Titik Macet" di analisa_lalu_lintas.xlsx aplikasi overlay)
TITIK = [("1.5", "Sukomoro – Talang Betutu (KM 15–20)", -2.913, 104.640),
         ("1.5", "Sisi barat Sukomoro (KM 18–20)", -2.912, 104.620),
         ("1.2", "Kota Betung (KM 69–71)", -2.836, 104.222),
         ("1.2", "Pasar Sungai Lilin (KM 112,6)", -2.6020, 104.1097),
         ("1.1", "Kota Bayung Lencir", -2.015, 103.699)]


def aliran(key, lat, lng):
    q = urllib.parse.urlencode({"key": key, "point": "%f,%f" % (lat, lng), "unit": "KMPH"})
    d = json.load(urllib.request.urlopen("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/12/json?" + q,
                                         timeout=30))["flowSegmentData"]
    cur, free = d.get("currentSpeed", 0), d.get("freeFlowSpeed", 0) or 1
    r = cur / free
    kat = "Lancar" if r >= .85 else "Ramai lancar" if r >= .65 else "Padat" if r >= .45 else "Macet" if r >= .25 else "Macet parah"
    return {"kecepatan": cur, "normal": free, "kategori": "Ditutup" if d.get("roadClosure") else kat,
            "keyakinan": round(d.get("confidence", 0), 2)}


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
    titik = []
    for ppk, nama, lat, lng in TITIK:
        try:
            titik.append(dict(ppk=ppk, nama=nama, **aliran(key, lat, lng)))
        except Exception as e:
            print("gagal titik", nama, e, file=sys.stderr)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sumber": "TomTom Traffic", "ruas": hasil, "titik": titik},
                  f, ensure_ascii=False, indent=1)
    print(len(hasil), "ruas ditulis,", gagal, "gagal")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ruas.json")
