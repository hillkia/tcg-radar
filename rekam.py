"""REKAM — membuat video demo dari dashboard, tanpa merekam layar.

Rekaman layar butuh izin Screen Recording macOS, dan izin itu memberi akses ke
SELURUH layar — termasuk apa pun yang kebetulan terbuka. Untuk sekadar
menunjukkan satu halaman, itu harga yang tidak perlu dibayar.

Jadi halamannya digambar langsung oleh Chrome tanpa jendela, lalu digulung
menjadi video oleh ffmpeg. Hasilnya lebih bersih daripada rekaman layar: tidak
ada kursor bergoyang, tidak ada bilah menu, tidak ada isi layar lain yang ikut.

    .venv/bin/python rekam.py              # video dari dashboard terbaru
    .venv/bin/python rekam.py --detik 30

Videonya HANYA dibuat kalau ada pergerakan harga yang nyata. Demo berisi tabel
kosong lebih buruk daripada tidak punya demo: klien menyimpulkan botnya tidak
menemukan apa-apa, bukan bahwa datanya belum cukup.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import gudang

AKAR = Path(__file__).resolve().parent
HALAMAN = AKAR / "papan.html"
KELUAR = AKAR / "demo.mp4"
GAMBAR = AKAR / "papan.png"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LEBAR = 1280
TINGGI_LAYAR = 720


def _tinggi_halaman(naik: int, turun: int) -> int:
    """Perkiraan tinggi halaman dari jumlah baris.

    Chrome tanpa jendela memotret seukuran jendela yang diminta, bukan seukuran
    isi. Karena HTML-nya kita sendiri yang merakit, tingginya bisa dihitung:
    kepala + kartu + dua tabel + kaki. Dilebihkan sedikit supaya tidak ada baris
    yang terpotong — ruang kosong di bawah lebih baik daripada angka terpenggal.
    """
    tinggi = 300                       # judul, sub, kartu ringkasan
    for n in (naik, turun):
        tinggi += 46 + (n * 34 if n else 34) + 30
    # Tidak boleh lebih pendek dari bingkai video: ffmpeg menolak memotong
    # 1280×720 dari gambar yang tingginya 710 dan berhenti dengan "Invalid
    # argument" — bukan menyusut sendiri. Halaman pendek terjadi persis waktu
    # tabelnya sedikit, jadi ini kasus yang wajar, bukan kasus aneh.
    return max(min(tinggi + 190, 4600), TINGGI_LAYAR)


def gambar(tinggi: int) -> Path:
    if not Path(CHROME).exists():
        raise SystemExit("❌ Google Chrome tidak ditemukan")
    p = subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-color-profile=srgb", f"--window-size={LEBAR},{tinggi}",
         f"--screenshot={GAMBAR}", HALAMAN.as_uri()],
        capture_output=True, text=True, timeout=120)
    if not GAMBAR.exists() or GAMBAR.stat().st_size < 5000:
        raise SystemExit(f"❌ Chrome gagal menggambar: {p.stderr[-200:]}")
    return GAMBAR


def video(tinggi: int, detik: int) -> Path:
    if not shutil.which("ffmpeg"):
        raise SystemExit("❌ ffmpeg tidak ada (brew install ffmpeg)")
    geser = max(tinggi - TINGGI_LAYAR, 0)
    diam = 3.0                                   # jeda diam di awal dan akhir
    jalan = max(detik - diam * 2, 4)

    if geser == 0:
        gerak = "0"
    else:
        # Gulung pelan setelah jeda awal, lalu berhenti di dasar. Dibungkus min()
        # supaya tidak pernah melewati tepi bawah gambar — kalau lewat, ffmpeg
        # berhenti dengan galat, bukan memotong.
        gerak = (f"min({geser}\\,max(0\\,(t-{diam})/{jalan}*{geser}))")

    p = subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(GAMBAR),
         "-vf", f"crop={LEBAR}:{TINGGI_LAYAR}:0:'{gerak}',format=yuv420p",
         "-t", str(detik), "-r", "30",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-movflags", "+faststart", str(KELUAR)],
        capture_output=True, text=True)
    if p.returncode != 0 or not KELUAR.exists():
        raise SystemExit(f"❌ ffmpeg gagal:\n{p.stderr[-500:]}")
    return KELUAR


def _cli(argv=None) -> int:
    a = argparse.ArgumentParser(prog="rekam.py")
    a.add_argument("--detik", type=int, default=26)
    a.add_argument("--paksa", action="store_true",
                   help="tetap buat walau tidak ada pergerakan")
    x = a.parse_args(argv)

    c = gudang.buka()
    b = c.execute("SELECT id FROM potret ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not b:
        print("❌ gudang kosong — jalankan run.py --sekali dulu")
        return 1

    semua = gudang.gerak(b["id"])
    naik = [g for g in semua if g["ubah"] > 0][:15]
    turun = [g for g in semua if g["ubah"] < 0][:15]

    if not naik and not x.paksa:
        lama = gudang.pembanding(b["id"])
        print("⏸  Belum ada barang yang naik, jadi videonya belum dibuat.")
        print("   Demo bertabel kosong membuat klien menyimpulkan botnya tidak")
        print("   menemukan apa-apa — bukan bahwa datanya yang belum cukup.\n")
        print("   " + ("Potret pembanding sudah ada, harga memang sedang datar — "
                       "coba lagi setelah putaran berikutnya."
                       if lama else
                       "Belum ada potret pembanding berjarak 4 jam. Putaran "
                       "berikutnya jam 19:00 akan menyediakannya."))
        return 2

    if not HALAMAN.exists():
        print("❌ papan.html belum ada — jalankan run.py --papan")
        return 1

    tinggi = _tinggi_halaman(len(naik), len(turun))
    print(f"🎬 menggambar halaman {LEBAR}×{tinggi}…")
    gambar(tinggi)
    print(f"🎞  merangkai video {x.detik} detik…")
    v = video(tinggi, x.detik)
    mb = v.stat().st_size / 1_048_576
    print(f"\n✅ {v}  ({mb:.1f} MB · {x.detik} detik)")
    print(f"   {len(naik)} barang naik · {len(turun)} turun")
    if naik:
        t = naik[0]
        print(f"   paling tajam: {t['nama'][:46]} {t['ubah']:+}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
