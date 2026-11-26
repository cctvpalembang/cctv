"""Ambil berita jalan/jembatan/bencana Sumsel dari Google News RSS dan tulis news.json
untuk pita berita di halaman CCTV. Kata kunci & penyaring sama dengan aplikasi cctvpalembang/news.
Hanya pustaka standar Python."""
import json, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

JENIS = ["Jalan Rusak", "Jalan Lubang", "Jembatan Rusak", "Banjir", "Longsor", "Kecelakaan",
         "Kemacetan", "Lubang Jalan", "Jalan Bergelombang", "Jalan Amblas", "Jalan Hancur", "Tabrakan"]
LOKASI = ["Sumsel", "Sumatera Selatan", "Banyuasin", "Pangkalan Balai", "Empat Lawang", "Lahat",
          "Muara Enim", "Sekayu", "Musi Banyuasin", "Muara Beliti", "Musi Rawas", "Musi Rawas Utara", "Ogan Ilir",
          "Indralaya", "Ogan Komering Ilir", "Kayu Agung", "Ogan Komering Ulu", "OKU", "Baturaja",
          "Ogan Komering Ulu Selatan", "OKU Selatan", "Ogan Komering Ulu Timur", "OKU Timur", "Martapura",
          "Penukal Abab Lematang Ilir", "PALI", "Palembang", "Lubuklinggau", "Pagar Alam", "Prabumulih"]
KHUSUS = ["Jalan Tol Palembang Betung", "Jalan Tol Kayuagung Palembang", "Jalan Tol Indralaya Prabumulih",
          "Jalan Tol Palembang Indralaya", "BBPJN Sumsel", "Jembatan Ampera", "Jembatan Musi"]
LOKASI_SUMSEL = ["sumsel", "sumatera selatan", "sumatra selatan", "palembang", "banyuasin", "musi banyuasin", "muba",
                 "sekayu", "betung", "lubuklinggau", "lubuk linggau", "musi rawas", "muratara", "muara enim", "muaraenim",
                 "baturaja", "ogan komering ulu", "oku", "martapura", "muaradua", "prabumulih", "ogan ilir", "indralaya",
                 "inderalaya", "ogan komering ilir", "oki", "kayuagung", "kayu agung", "pagar alam", "pagaralam", "lahat",
                 "empat lawang", "pali", "penukal abab", "pendopo", "ampera", "bayung lencir", "pematang panggang",
                 "kertapati", "jakabaring", "plaju", "gandus", "sungai lilin", "tanjung api api", "bbpjn"]
MEDIA_SUMSEL = ["sumsel", "palembang", "sumeks", "sripoku", "palpres", "linggaupos", "beritamusi",
                "sumselupdate", "sumselterkini", "sumselpost", "detiksumbagsel"]
TOPIK = ["jalan", "jembatan", "banjir", "longsor", "kecelakaan", "laka", "tabrak", "ditabrak", "menabrak",
         "macet", "kemacetan", "tol", "lubang", "berlubang", "rusak", "genangan", "amblas", "ambles", "putus",
         "bbpjn", "balai besar", "preservasi", "aspal", "ruas", "terguling", "terbalik", "tergenang",
         "tabrakan", "bergelombang", "hancur", "longsoran", "kebanjiran"]
HARI, MAKS = 3, 40


def q(t):
    return '"%s"' % t if " " in t else t


def queries():
    jen = "(" + " OR ".join(q(j) for j in JENIS) + ")"
    for i in range(0, len(LOKASI), 8):
        yield jen + " (" + " OR ".join(q(l) for l in LOKASI[i:i + 8]) + ")"
    yield "(" + " OR ".join(q(k) for k in KHUSUS) + ")"


def ada(teks, kata):
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", teks) for k in kata)


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower())[:70]


def parse(xml_bytes):
    out = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3].strip()
        try:
            ts = parsedate_to_datetime(it.findtext("pubDate") or "").timestamp()
        except Exception:
            ts = 0
        out.append({"title": title, "link": (it.findtext("link") or "").strip(), "source": src, "ts": ts})
    return out


def relevan(b):
    t = b["title"].lower()
    return ada(t, TOPIK) and (ada(t, LOKASI_SUMSEL) or any(m in b["source"].lower().replace(" ", "") for m in MEDIA_SUMSEL))


def main(out_path):
    semua, gagal = [], 0
    for qs in queries():
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": qs + " when:%dd" % HARI, "hl": "id", "gl": "ID", "ceid": "ID:id"})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (pita-berita-cctv)"})
            semua += parse(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            gagal += 1
            print("gagal:", e, file=sys.stderr)
        time.sleep(1)
    batas = time.time() - HARI * 86400
    lihat, hasil = set(), []
    for b in sorted(semua, key=lambda b: -b["ts"]):
        k = norm(b["title"])
        if not b["title"] or k in lihat or b["ts"] < batas or not relevan(b):
            continue
        lihat.add(k)
        hasil.append({"title": b["title"], "link": b["link"], "source": b["source"],
                      "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(b["ts"]))})
    if not hasil and gagal:
        sys.exit("semua permintaan gagal; news.json tidak diubah")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": hasil[:MAKS]},
                  f, ensure_ascii=False, indent=1)
    print(len(hasil[:MAKS]), "berita ditulis")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "news.json")
