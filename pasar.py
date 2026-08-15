"""PASAR — penarik harga dari empat pasar koleksi.

Yang dijual ke klien bukan kodenya, melainkan angka yang benar. Karena itu tiap
adapter di sini WAJIB pernah menyentuh server aslinya; adapter yang hanya
"kodenya jadi" tidak dihitung ada. Versi sebelumnya dibangun di sandbox tanpa
jaringan, sehingga keempatnya belum pernah diuji — dan satu di antaranya
(Skinport) ternyata langsung menolak.

    python3 -m pasar            # tarik contoh dari tiap pasar, tampilkan apa adanya

Empat pasar:
  pokemon   pokemontcg.io          harga TCGplayer     tanpa kunci
  cs2       api.skinport.com       harga jual nyata    tanpa kunci  (WAJIB Brotli)
  arttoy    eBay Browse            Labubu / Pop Mart   butuh kunci gratis
  onepiece  eBay Browse            One Piece TCG       butuh kunci gratis
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


class PasarGagal(Exception):
    """Server menolak atau jawabannya tidak bisa dipakai. JANGAN diganti nilai
    palsu — harga karangan yang masuk riwayat akan mencemari semua perbandingan
    sesudahnya, dan klien pasar koleksi menilai barang tiap hari; mereka akan
    tahu lebih dulu dari kita."""


@dataclass
class Barang:
    pasar: str
    nama: str
    harga: float          # USD
    tautan: str = ""

    def kunci(self) -> str:
        return f"{self.pasar}:{self.nama}"


def _json(url: str, hdr: dict | None = None, timeout: int = 30):
    r = urllib.request.Request(url, headers={"User-Agent": UA,
                                             "Accept": "application/json",
                                             **(hdr or {})})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def _json_brotli(url: str, timeout: int = 60):
    """Skinport HANYA melayani Brotli; encoding lain dijawab 406 Not Acceptable.

    curl bawaan macOS dikompilasi tanpa brotli, jadi ia mengembalikan 200 dengan
    isi yang tidak bisa dibuka — status 200 di sini BUKAN tanda berhasil, dan
    memeriksa status saja sempat membuat adapter ini dikira jalan padahal tidak.
    Karena itu dekompresinya dilakukan sendiri lewat modul brotli di .venv.
    """
    try:
        import brotli
    except ImportError:
        raise PasarGagal("modul brotli belum ada — jalankan lewat .venv/bin/python "
                         "(pasang: python3 -m venv .venv && "
                         ".venv/bin/pip install -r requirements.txt)")
    r = urllib.request.Request(url, headers={"User-Agent": UA,
                                             "Accept": "application/json",
                                             "Accept-Encoding": "br"})
    mentah = urllib.request.urlopen(r, timeout=timeout).read()
    try:
        teks = brotli.decompress(mentah)
    except Exception:
        teks = mentah          # sebagian CDN sudah membuka paketnya lebih dulu
    try:
        return json.loads(teks)
    except json.JSONDecodeError:
        raise PasarGagal(f"jawaban bukan JSON: {teks[:120]!r}")


# ─────────────────────────────── POKEMON TCG ────────────────────────────────

def pokemon(set_id: str = "sv1", batas: int = 60) -> list[Barang]:
    # pageSize besar membuat pokemontcg.io menjawab 500/502 — bukan kesalahan
    # permintaan, servernya memang keselek. Ambil per 20 dan sambung sendiri.
    # Tanpa ini adapter tampak "kadang jalan kadang tidak", yang jauh lebih sulit
    # ditelusuri daripada gagal terus-terusan.
    # Tanpa kunci, pokemontcg.io sering menjawab 500/502 lalu berhasil di
    # percobaan berikutnya — diukur langsung: gagal, gagal, berhasil. Jadi
    # kegagalan sekali BUKAN tanda pasarnya mati, dan berhenti di percobaan
    # pertama akan membuat bot melaporkan "Pokemon mati" hampir setiap hari.
    # Kunci gratis di dev.pokemontcg.io menaikkan batasnya jauh; kalau ada,
    # dipakai otomatis.
    import time
    hdr = {}
    if os.environ.get("POKEMONTCG_API_KEY"):
        hdr["X-Api-Key"] = os.environ["POKEMONTCG_API_KEY"]

    d = {"data": []}
    galat = ""
    for hal in range(1, (batas + 19) // 20 + 1):
        u = ("https://api.pokemontcg.io/v2/cards?"
             + urllib.parse.urlencode({"q": f"set.id:{set_id}", "pageSize": 20,
                                       "page": hal}))
        for percobaan in range(5):
            try:
                d["data"] += _json(u, hdr=hdr, timeout=40).get("data", [])
                galat = ""
                break
            except Exception as e:
                galat = str(e)
                time.sleep(min(2 ** percobaan, 8))
        if galat and not d["data"]:
            raise PasarGagal(f"pokemontcg.io: {galat} (5 percobaan)")
        if galat or len(d["data"]) >= batas:
            break                      # sebagian data lebih berguna daripada nol
    out = []
    for c in d.get("data", []):
        harga = c.get("tcgplayer", {}).get("prices", {})
        # Satu kartu punya beberapa varian (normal, holofoil, reverse). Ambil yang
        # termahal: itu yang pergerakannya dipantau pedagang, bukan yang biasa.
        nilai = [v.get("market") or v.get("mid") for v in harga.values()
                 if isinstance(v, dict) and (v.get("market") or v.get("mid"))]
        if not nilai:
            continue
        out.append(Barang("pokemon", c["name"], float(max(nilai)),
                          c.get("tcgplayer", {}).get("url", "")))
    if not out:
        raise PasarGagal("pokemontcg.io menjawab tapi tidak ada satu pun harga")
    return out


# ──────────────────────────────── SKIN CS2 ──────────────────────────────────

def cs2(batas: int = 60) -> list[Barang]:
    d = _json_brotli("https://api.skinport.com/v1/items?app_id=730&currency=USD")
    if not isinstance(d, list):
        raise PasarGagal(f"bentuk jawaban tak terduga: {type(d).__name__}")
    out = []
    for x in d:
        h = x.get("min_price") or x.get("suggested_price")
        if not h:
            continue
        out.append(Barang("cs2", x.get("market_hash_name", "?"), float(h),
                          x.get("item_page", "")))
    # Barang paling mahal yang paling sering dipantau trader; yang $0,03 hanya
    # menambah derau ke daftar lonjakan.
    out.sort(key=lambda b: -b.harga)
    if not out:
        raise PasarGagal("Skinport menjawab tapi tidak ada harga")
    return out[:batas]


# ────────────────────────── eBAY (ART TOY & ONE PIECE) ──────────────────────

def _rahasia(nama: str) -> str:
    """Ambil kunci dari Keychain macOS, jatuh ke environment kalau tidak ada.

    Keychain didahulukan karena bot ini dijalankan launchd, dan launchd tidak
    mewarisi environment terminal — kunci yang di-export di .zshrc tidak akan
    terlihat olehnya. Menaruh kunci di dalam berkas plist bisa saja, tapi plist
    itu teks biasa yang ikut tersalin ke mana-mana; Keychain tidak.
    """
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", nama, "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip()
    except FileNotFoundError:
        # `security` hanya ada di macOS. Di GitHub Actions (Linux) tidak ada, dan
        # tanpa penjagaan ini seluruh adapter mati karena FileNotFoundError —
        # bukan karena kuncinya salah. Di sana kuncinya datang dari environment.
        pass
    return os.environ.get(nama, "")


_TOKEN: tuple[str, float] | None = None      # (token, kedaluwarsa)


def _ebay_token() -> str:
    """Token dipakai ulang selama masih berlaku.

    eBay membatasi laju permintaan token, dan dua pasar yang dilayani eBay
    (art toy dan One Piece) berjalan berurutan dalam satu putaran. Tanpa
    penyimpanan ini, yang kedua kena 401 — dan yang mana yang gagal berganti
    tiap kali dijalankan, sehingga terlihat seperti kunci yang rusak sesekali,
    bukan seperti pembatasan laju. Tokennya sendiri berlaku 2 jam.
    """
    import time
    global _TOKEN
    if _TOKEN and time.time() < _TOKEN[1]:
        return _TOKEN[0]
    t = _ebay_token_baru()
    # Dikurangi 60 detik supaya tidak dipakai tepat saat kedaluwarsa.
    _TOKEN = (t, time.time() + 7200 - 60)
    return t


def _ebay_token_baru() -> str:
    """Token OAuth eBay dari kunci Production di Keychain (atau environment).

    Tidak ada nilai bawaan dan tidak ada mode pura-pura: kalau kuncinya belum
    ada, adapter ini berkata belum ada. Dashboard yang menampilkan Labubu dengan
    harga karangan jauh lebih berbahaya daripada dashboard yang jujur kosong.
    """
    cid, sec = _rahasia("EBAY_CLIENT_ID"), _rahasia("EBAY_CLIENT_SECRET")
    if not (cid and sec):
        raise PasarGagal("kunci eBay belum dipasang — jalankan: "
                         "python3 pasang_ebay.py")
    import base64
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = urllib.request.Request(
        "https://api.ebay.com/identity/v1/oauth2/token",
        data=urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"}).encode(),
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=30).read())["access_token"]
    except Exception as e:
        raise PasarGagal(f"token eBay ditolak: {e}")


def _ebay_cari(pasar: str, kata: str, batas: int = 40) -> list[Barang]:
    t = _ebay_token()
    d = _json("https://api.ebay.com/buy/browse/v1/item_summary/search?"
              + urllib.parse.urlencode({"q": kata, "limit": batas,
                                        "filter": "buyingOptions:{FIXED_PRICE}"}),
              hdr={"Authorization": f"Bearer {t}",
                   "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
    out = []
    for x in d.get("itemSummaries", []):
        h = (x.get("price") or {}).get("value")
        if h:
            out.append(Barang(pasar, x.get("title", "?")[:90], float(h),
                              x.get("itemWebUrl", "")))
    if not out:
        raise PasarGagal(f"eBay tidak mengembalikan hasil untuk '{kata}'")
    return out


def arttoy(batas: int = 40) -> list[Barang]:
    return _ebay_cari("arttoy", "labubu pop mart figure", batas)


def onepiece(batas: int = 40) -> list[Barang]:
    return _ebay_cari("onepiece", "one piece tcg card", batas)


# ──────────────────────────── MAGIC: THE GATHERING ─────────────────────────

def mtg(batas: int = 60) -> list[Barang]:
    """Scryfall — tanpa kunci, tanpa batas berbayar, harga dari TCGplayer.

    Ditambahkan waktu akun eBay Hillkia masih ditinjau, jadi dua pasar eBay
    belum bisa dipakai. MTG bukan sekadar tambal: dari sisi nilai dia pasar
    kartu koleksi terbesar — satu kartu bisa $6.500, sementara kartu One Piece
    termahal jarang lewat $200. Pergerakan di sana lebih berarti bagi pedagang.

    Scryfall meminta jeda antar permintaan dan User-Agent yang jelas; keduanya
    dipenuhi supaya tidak diblokir.
    """
    import time
    out = []
    for hal in (1, 2):
        try:
            d = _json("https://api.scryfall.com/cards/search?"
                      + urllib.parse.urlencode({"q": "is:booster usd>20",
                                                "order": "usd", "dir": "desc",
                                                "page": hal}),
                      hdr={"User-Agent": "tcg-radar/1.0"}, timeout=35)
        except Exception as e:
            if out:
                break
            raise PasarGagal(f"scryfall: {e}")
        for c in d.get("data", []):
            h = (c.get("prices") or {}).get("usd")
            if not h:
                continue
            # Nama saja tidak unik: satu kartu dicetak ulang berkali-kali dengan
            # harga yang jauh berbeda. Set-nya harus ikut, kalau tidak dua cetakan
            # akan saling menimpa dan tampak "berubah harga" padahal barang lain.
            out.append(Barang("mtg", f"{c['name']} ({c.get('set', '?').upper()})",
                              float(h), c.get("scryfall_uri", "")))
        if len(out) >= batas or not d.get("has_more"):
            break
        time.sleep(0.12)
    if not out:
        raise PasarGagal("scryfall menjawab tapi tidak ada harga USD")
    out.sort(key=lambda b: -b.harga)
    return out[:batas]


SEMUA = {"pokemon": pokemon, "mtg": mtg, "cs2": cs2,
         "arttoy": arttoy, "onepiece": onepiece}


def periksa() -> dict[str, str]:
    """Tarik contoh dari tiap pasar dan laporkan apa adanya. Inilah satu-satunya
    bukti yang boleh dipakai untuk mengatakan sebuah adapter 'jalan'."""
    hasil = {}
    for nama, fn in SEMUA.items():
        try:
            b = fn()
            hasil[nama] = (f"✅ {len(b)} barang · contoh: {b[0].nama[:44]} "
                           f"${b[0].harga:,.2f}")
        except PasarGagal as e:
            hasil[nama] = f"❌ {e}"
        except Exception as e:
            hasil[nama] = f"❌ {type(e).__name__}: {e}"
    return hasil


if __name__ == "__main__":
    lebar = max(len(k) for k in SEMUA)
    gagal = 0
    for nama, pesan in periksa().items():
        print(f"  {nama:<{lebar}}  {pesan}")
        gagal += pesan.startswith("❌")
    print(f"\n  {len(SEMUA) - gagal}/{len(SEMUA)} pasar hidup")
    sys.exit(0 if gagal < len(SEMUA) else 1)
