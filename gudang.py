"""GUDANG — menyimpan potret harga dan menghitung pergerakannya.

Nilai jual bot ini bukan "menampilkan harga hari ini" — situs pasarnya sendiri
sudah melakukan itu gratis. Yang dibayar klien adalah PERUBAHAN: apa yang naik
tajam sejak terakhir dilihat, karena di situlah keputusan beli-jual diambil.

Karena itu seluruh berkas ini berputar di satu hal: membandingkan dua potret
yang benar-benar layak dibandingkan.

    python3 -m gudang            # ringkasan isi gudang
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

AKAR = Path(__file__).resolve().parent
BERKAS = AKAR / "harga.db"

# Dua potret yang diambil berdekatan tidak mengandung informasi apa pun: harga
# pasar tidak bergerak dalam hitungan detik, tetapi pembaginya tetap kecil
# sehingga derau terlihat seperti lonjakan. Bot yang dijalankan dua kali sehari
# pernah membandingkan dua potret pada detik yang sama dan melaporkan "naik 0%"
# untuk semua barang. Jarak minimum ini yang mencegahnya.
JARAK_MINIMUM = timedelta(hours=4)


def buka() -> sqlite3.Connection:
    c = sqlite3.connect(BERKAS)
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE IF NOT EXISTS potret (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        waktu   TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS harga (
        potret  INTEGER NOT NULL REFERENCES potret(id) ON DELETE CASCADE,
        pasar   TEXT NOT NULL,
        nama    TEXT NOT NULL,
        harga   REAL NOT NULL,
        tautan  TEXT DEFAULT '',
        PRIMARY KEY (potret, pasar, nama)
      );
      CREATE INDEX IF NOT EXISTS i_harga_barang ON harga(pasar, nama);
    """)
    return c


def _waktu(s: str) -> datetime:
    return datetime.fromisoformat(s)


def sekarang() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def simpan(barang: list, paksa: bool = False) -> tuple[int, str]:
    """Simpan satu potret. Mengembalikan (id, catatan).

    Kalau potret terakhir masih terlalu baru, potret ini TIDAK dibuang — dia
    tetap disimpan supaya riwayat harganya utuh — tetapi penanda `terlalu_dekat`
    dikembalikan agar bagian yang menghitung lonjakan tahu harus melompat ke
    potret yang lebih tua.
    """
    c = buka()
    b = c.execute("SELECT id, waktu FROM potret ORDER BY id DESC LIMIT 1").fetchone()
    catatan = ""
    if b and not paksa:
        selisih = datetime.now(timezone.utc) - _waktu(b["waktu"])
        if selisih < JARAK_MINIMUM:
            catatan = (f"potret terakhir baru {int(selisih.total_seconds()//60)} "
                       f"menit lalu — pembanding diambil dari yang lebih tua")
    pid = c.execute("INSERT INTO potret(waktu) VALUES (?)", (sekarang(),)).lastrowid
    c.executemany(
        "INSERT OR REPLACE INTO harga(potret,pasar,nama,harga,tautan) VALUES (?,?,?,?,?)",
        [(pid, x.pasar, x.nama, x.harga, x.tautan) for x in barang])
    c.commit()
    c.close()
    return pid, catatan


def pembanding(pid: int) -> sqlite3.Row | None:
    """Potret terakhir yang jaraknya cukup jauh dari `pid` untuk dibandingkan."""
    c = buka()
    ini = c.execute("SELECT waktu FROM potret WHERE id=?", (pid,)).fetchone()
    if not ini:
        c.close()
        return None
    batas = (_waktu(ini["waktu"]) - JARAK_MINIMUM).isoformat()
    r = c.execute("SELECT id, waktu FROM potret WHERE id<? AND waktu<=? "
                  "ORDER BY id DESC LIMIT 1", (pid, batas)).fetchone()
    c.close()
    return r


def gerak(pid: int, minimal_persen: float = 3.0, lantai_dolar: float = 1.0,
          dolar_besar: float = 25.0) -> list[dict]:
    """Barang yang harganya bergerak berarti antara potret pembanding dan `pid`.

    Ambang persen SAJA salah di dua arah sekaligus, dan keduanya terbukti pada
    data nyata 15/8/2026:

    - Kartu $0,18 naik satu sen tercatat "+5,6%" dan masuk laporan. Benar secara
      hitungan, tidak berarti apa-apa bagi pedagang.
    - Stiker CS2 $82.000 bergerak $171,93 TIDAK masuk laporan, karena itu hanya
      0,2%. Padahal justru itu yang ingin diketahui pemiliknya.

    Jadi: ada lantai dolar untuk membuang derau receh, lalu barang dianggap
    bergerak kalau persennya besar ATAU nilai dolarnya besar. Bukan keduanya
    wajib — menuntut keduanya membuat laporan kosong sama sekali.

    Hasilnya diurutkan dari kenaikan terbesar. Penyaringan naik/turun TIDAK
    dilakukan di sini — itu tugas yang menampilkan, dan mencampurnya pernah
    membuat tabel "naik paling tajam" berisi barang yang justru turun.
    """
    lama = pembanding(pid)
    if not lama:
        return []
    c = buka()
    baris = c.execute("""
        SELECT b.pasar, b.nama, a.harga AS dulu, b.harga AS kini, b.tautan
        FROM harga b JOIN harga a
          ON a.pasar=b.pasar AND a.nama=b.nama AND a.potret=?
        WHERE b.potret=? AND a.harga > 0
    """, (lama["id"], pid)).fetchall()
    c.close()

    # Penyetelan serentak, BUKAN pergerakan pasar. Terukur 15/8/2026: 10 dari 11
    # "penurunan" Skinport punya rasio harga yang sama persis (0,99633) — itu
    # bursanya menghitung ulang kurs/biaya, bukan sebelas barang yang kebetulan
    # jatuh bersamaan. Harga pasar tidak pernah bergerak seseragam itu.
    #
    # Mengirimkannya sebagai temuan ke pedagang yang memantau harga tiap hari
    # akan ketahuan dalam satu balasan, dan sesudah itu tidak ada angka lain dari
    # kita yang dipercaya. Jadi rasio yang dipakai banyak barang sekaligus
    # dibuang — yang tersisa adalah barang yang bergerak sendiri.
    from collections import Counter
    rasio = Counter(round(r["kini"] / r["dulu"], 5) for r in baris
                    if r["kini"] != r["dulu"])
    seragam = {k for k, n in rasio.items() if n >= max(4, len(baris) // 12)}

    out, dibuang = [], 0
    for r in baris:
        selisih = r["kini"] - r["dulu"]
        ubah = selisih / r["dulu"] * 100
        if abs(selisih) < lantai_dolar:
            continue
        if abs(ubah) < minimal_persen and abs(selisih) < dolar_besar:
            continue
        if round(r["kini"] / r["dulu"], 5) in seragam:
            dibuang += 1
            continue
        out.append({"pasar": r["pasar"], "nama": r["nama"], "dulu": r["dulu"],
                    "kini": r["kini"], "ubah": round(ubah, 1),
                    "selisih": round(selisih, 2), "tautan": r["tautan"]})
    out.sort(key=lambda x: -x["ubah"])
    if dibuang:
        print(f"  ℹ️  {dibuang} barang dibuang: penyetelan serentak bursa, "
              f"bukan pergerakan pasar", flush=True)
    return out


def riwayat(pasar: str, nama: str, batas: int = 60) -> list[tuple[str, float]]:
    c = buka()
    r = c.execute("""SELECT p.waktu, h.harga FROM harga h JOIN potret p ON p.id=h.potret
                     WHERE h.pasar=? AND h.nama=? ORDER BY p.id DESC LIMIT ?""",
                  (pasar, nama, batas)).fetchall()
    c.close()
    return [(x["waktu"], x["harga"]) for x in reversed(r)]


def ringkas() -> dict:
    c = buka()
    p = c.execute("SELECT COUNT(*) n, MIN(waktu) a, MAX(waktu) b FROM potret").fetchone()
    h = c.execute("SELECT COUNT(DISTINCT pasar||nama) n FROM harga").fetchone()
    per = c.execute("SELECT pasar, COUNT(DISTINCT nama) n FROM harga "
                    "GROUP BY pasar ORDER BY n DESC").fetchall()
    c.close()
    return {"potret": p["n"], "pertama": p["a"], "terakhir": p["b"],
            "barang": h["n"], "per_pasar": {x["pasar"]: x["n"] for x in per}}


if __name__ == "__main__":
    r = ringkas()
    if not r["potret"]:
        print("Gudang masih kosong. Jalankan:  python3 run.py --sekali")
        sys.exit(0)
    print(f"  {r['potret']} potret · {r['barang']} barang berbeda")
    print(f"  pertama {r['pertama']}\n  terakhir {r['terakhir']}")
    for k, v in r["per_pasar"].items():
        print(f"    {k:<10} {v}")
