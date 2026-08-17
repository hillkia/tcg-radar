"""RUN — satu pintu untuk seluruh bot.

    python3 run.py --check      periksa keempat pasar, tidak menyimpan apa pun
    python3 run.py --sekali     tarik harga, simpan, rakit dashboard
    python3 run.py --papan      rakit ulang dashboard dari data yang sudah ada
    python3 run.py --status     ringkasan singkat untuk dibaca cepat

Dijalankan otomatis dua kali sehari oleh launchd (com.ocklu.radar). Semua
keluarannya masuk ke jalan.log, dan `status.json` selalu berisi keadaan terakhir
supaya bisa dibaca tanpa menjalankan apa pun.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR))

import gudang        # noqa: E402
import papan         # noqa: E402
import pasar         # noqa: E402

STATUS = AKAR / "status.json"


def _tulis_status(**k) -> None:
    """Keadaan terakhir, selalu ditimpa. Berkas ini sengaja kecil dan datar
    supaya bisa dibaca sekilas tanpa membuka database atau menjalankan bot."""
    STATUS.write_text(json.dumps(
        {"waktu": datetime.now(timezone.utc).isoformat(timespec="seconds"), **k},
        ensure_ascii=False, indent=1), encoding="utf-8")


def sekali() -> int:
    barang, hidup, mati = [], [], {}
    for nama, fn in pasar.SEMUA.items():
        try:
            b = fn()
            barang += b
            hidup.append(nama)
            print(f"  ✅ {nama:<9} {len(b)} barang")
        except pasar.PasarGagal as e:
            mati[nama] = str(e)
            print(f"  ❌ {nama:<9} {e}")
        except Exception as e:
            mati[nama] = f"{type(e).__name__}: {e}"
            print(f"  ❌ {nama:<9} {type(e).__name__}: {e}")

    if not barang:
        # Potret kosong tidak boleh masuk gudang: dia akan menjadi pembanding
        # berikutnya, dan semua barang akan terlihat "baru muncul" esok hari.
        print("\n  ⛔ tidak ada satu pun pasar yang menjawab — potret TIDAK disimpan")
        _tulis_status(hasil="gagal", hidup=[], mati=mati, barang=0)
        return 1

    pid, catatan = gudang.simpan(barang)
    naik = [x for x in gudang.gerak(pid) if x["ubah"] > 0]
    p = papan.rakit(pid, catatan)
    r = gudang.ringkas()

    print(f"\n  potret #{pid} · {len(barang)} harga · {len(hidup)}/{len(pasar.SEMUA)} pasar")
    if catatan:
        print(f"  ⚠️  {catatan}")
    if naik:
        t = naik[0]
        print(f"  naik terbesar: {t['nama'][:44]} {t['ubah']:+}%")
    print(f"  → {p}")

    _tulis_status(hasil="berhasil", potret=pid, barang=len(barang),
                  hidup=hidup, mati=mati, total_potret=r["potret"],
                  naik=len(naik), catatan=catatan,
                  naik_teratas=[{k: x[k] for k in ("pasar", "nama", "ubah",
                                                   "selisih")} for x in naik[:5]])
    return 0


def _terbitkan() -> Path:
    """Salin dashboard ke docs/index.html — itu yang disajikan GitHub Pages.

    Halaman ini merangkap dua peran: laporan harian untuk Hillkia yang bisa
    dibuka dari HP, dan tautan demo hidup untuk calon klien Upwork. Yang kedua
    lebih meyakinkan daripada rekaman layar, karena mereka bisa membukanya
    sendiri besok dan melihat angkanya sudah berubah.
    """
    import shutil
    d = AKAR / "docs"
    d.mkdir(exist_ok=True)
    # .nojekyll: tanpa ini GitHub Pages menjalankan Jekyll, yang mengabaikan
    # berkas/berkas berawalan garis bawah dan bisa merusak halaman diam-diam.
    (d / ".nojekyll").write_text("")
    shutil.copy2(AKAR / "papan.html", d / "index.html")
    return d / "index.html"


def _laporkan() -> None:
    import lapor
    if STATUS.exists():
        print("  📧 laporan terkirim" if lapor.kirim(json.loads(
            STATUS.read_text(encoding="utf-8"))) else "  ⚠️  laporan gagal")


def _cli(argv=None) -> int:
    a = argparse.ArgumentParser(prog="run.py")
    a.add_argument("--check", action="store_true")
    a.add_argument("--sekali", action="store_true")
    a.add_argument("--papan", action="store_true")
    a.add_argument("--status", action="store_true")
    a.add_argument("--lapor", action="store_true",
                   help="kirim ringkasan ke email (dipakai penjadwal)")
    a.add_argument("--rekam", action="store_true",
                   help="buat video demo kalau ada pergerakan (dipakai penjadwal)")
    a.add_argument("--terbit", action="store_true",
                   help="salin dashboard ke docs/index.html untuk GitHub Pages")
    x = a.parse_args(argv)

    if x.check:
        gagal = 0
        for nama, pesan in pasar.periksa().items():
            print(f"  {nama:<9} {pesan}")
            gagal += pesan.startswith("❌")
        print(f"\n  {len(pasar.SEMUA)-gagal}/{len(pasar.SEMUA)} pasar hidup")
        return 0 if gagal < len(pasar.SEMUA) else 1

    if x.status:
        if not STATUS.exists():
            print("Belum pernah dijalankan.")
            return 0
        print(STATUS.read_text(encoding="utf-8"))
        return 0

    if x.papan:
        c = gudang.buka()
        b = c.execute("SELECT id FROM potret ORDER BY id DESC LIMIT 1").fetchone()
        c.close()
        if not b:
            print("Gudang kosong.")
            return 1
        print("✅", papan.rakit(b["id"]))
        return 0

    if x.sekali:
        print(f"🔎 {datetime.now():%d/%m %H:%M} — menarik harga…")
        try:
            kode = sekali()
        except Exception:
            # Dijalankan tanpa ditonton, jadi galat tak terduga harus mendarat di
            # log DAN di status.json — bukan hilang begitu saja.
            traceback.print_exc()
            _tulis_status(hasil="galat", jejak=traceback.format_exc()[-800:])
            kode = 1
        if x.terbit:
            print("  🌐 " + str(_terbitkan()))
        if x.lapor:
            _laporkan()
        # Panel MYTHOS hanya jujur kalau ledger-nya menyerap kerja yang terjadi di
        # luar MYTHOS. Dijalankan di sini karena putaran ini memang sudah rutin;
        # membuat jadwal terpisah hanya menambah satu hal lagi yang bisa mati
        # diam-diam. Kegagalannya tidak menjatuhkan putaran — data harga sudah
        # aman, dan panel yang telat sehari jauh lebih ringan akibatnya.
        try:
            import subprocess
            M = str(Path.home() / "neuralink-mythos-worker")
            for modul in ("mesin.serap", "mesin.panel"):
                subprocess.run(["python3", "-m", modul], cwd=M,
                               capture_output=True, timeout=180)
            print("  📊 panel MYTHOS disegarkan")
        except Exception as e:
            print(f"  ⚠️  panel MYTHOS tidak tersegarkan: {e}")

        if x.rekam:
            # rekam.py menolak sendiri kalau tidak ada yang naik, jadi tidak perlu
            # dijaga dua kali di sini. Kegagalannya juga tidak boleh menjatuhkan
            # putaran: datanya sudah aman, video hanya bahan jualan.
            import subprocess
            r = subprocess.run([sys.executable, str(AKAR / "rekam.py")],
                               capture_output=True, text=True)
            # Galat rekam.py mendarat di stderr, bukan stdout. Menampilkan baris
            # stdout terakhir saja pernah menyembunyikan kegagalan ffmpeg total:
            # log berhenti di "merangkai video…" dan tidak ada yang tahu videonya
            # tidak pernah jadi. Jadi stderr ikut dicetak kalau ada.
            if r.returncode not in (0, 2) and r.stderr.strip():
                print("  🎬 ❌ " + r.stderr.strip()[-300:])
            else:
                print("  🎬 " + (r.stdout.strip().splitlines() or ["-"])[-1])
        return kode

    a.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
