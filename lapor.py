"""LAPOR — kirim hasil tiap putaran ke email, supaya bisa dibaca dari HP.

Bot berjalan di laptop; laporannya harus bisa menyusul ke mana pun pemiliknya
berada. Email dipilih karena sudah ada dan tidak perlu apa-apa lagi: tidak ada
aplikasi yang harus dipasang, tidak ada server yang harus dibayar, dan riwayatnya
tersimpan sendiri di kotak masuk.

Sandi memakai entri Keychain yang sama dengan mesin email Blue Ocean
(`ocklu-gmail`), jadi tidak ada rahasia baru yang perlu disimpan.
"""
from __future__ import annotations

import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage
from email.utils import formataddr, formatdate

AKUN = "hillkiacakep@gmail.com"

NAMA_PASAR = {"pokemon": "Pokémon", "cs2": "CS2", "mtg": "MTG", "arttoy": "Art Toy",
              "onepiece": "One Piece"}


def _sandi() -> str:
    """HANYA dari Keychain macOS — sengaja tidak ada jalan lewat environment.

    Sandi ini memberi akses baca DAN kirim ke seluruh kotak masuk. Kalau dia
    boleh datang dari environment, dia bisa ikut terpasang di GitHub Actions,
    dan sesudah itu keamanannya bergantung pada keamanan akun GitHub — bukan
    lagi pada laptop ini. Radar di GitHub menerbitkan halaman web; pengiriman
    email tetap di sini.
    """
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", "ocklu-gmail",
                            "-a", AKUN, "-w"], capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("bukan macOS — laporan email hanya dikirim dari laptop")
    if r.returncode != 0:
        raise RuntimeError("sandi ocklu-gmail belum ada di Keychain")
    return r.stdout.strip()


def susun(st: dict) -> tuple[str, str]:
    hidup = st.get("hidup", [])
    mati = st.get("mati", {})
    naik = st.get("naik_teratas", [])

    if st.get("hasil") != "berhasil":
        judul = "Radar — tidak ada pasar yang menjawab"
    elif naik:
        t = naik[0]
        judul = (f"Radar — {NAMA_PASAR.get(t['pasar'], t['pasar'])}: "
                 f"{t['nama'][:38]} {t['ubah']:+}%")
    else:
        judul = f"Radar — {st.get('barang', 0)} harga tercatat, belum ada lonjakan"

    b = [f"Potret #{st.get('potret','-')} · {st.get('barang',0)} harga · "
         f"{len(hidup)}/5 pasar hidup", ""]
    if naik:
        b.append("NAIK PALING TAJAM")
        for x in naik:
            d = x.get('selisih')
            uang = f"{'+' if d and d > 0 else '−'}${abs(d):,.2f}" if d else ""
            b.append(f"  {x['ubah']:+6.1f}% {uang:>11}  "
                     f"[{NAMA_PASAR.get(x['pasar'], x['pasar'])}] {x['nama'][:44]}")
    else:
        b.append("Belum ada barang yang bergerak di atas 3%.")
        if st.get("total_potret", 0) < 2:
            b.append("Wajar — pergerakan baru bisa dihitung setelah potret kedua "
                     "(minimal 4 jam setelah yang pertama).")
    if st.get("catatan"):
        b += ["", f"Catatan: {st['catatan']}"]
    if mati:
        b += ["", "PASAR YANG TIDAK MENJAWAB"]
        for k, v in mati.items():
            b.append(f"  {NAMA_PASAR.get(k, k)}: {v[:96]}")
    b += ["", "—", "Angka di atas adalah harga tercatat di pasar masing-masing pada",
          "waktu potret diambil. Bukan penilaian, bukan saran beli-jual.",
          "Dashboard lengkap ada di laptop: tcg-radar/papan.html"]
    return judul, "\n".join(b)


def kirim(st: dict) -> bool:
    judul, isi = susun(st)
    try:
        m = EmailMessage()
        m["From"] = formataddr(("Radar Harga Koleksi", AKUN))
        m["To"] = AKUN
        m["Subject"] = judul
        m["Date"] = formatdate(localtime=True)
        m.set_content(isi)
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465,
                             context=ssl.create_default_context(), timeout=40)
        s.login(AKUN, _sandi())
        s.send_message(m)
        s.quit()
        return True
    except Exception as e:
        # Laporan gagal terkirim tidak boleh menjatuhkan botnya — datanya sudah
        # aman di gudang, dan itu yang penting.
        print(f"  ⚠️  laporan tidak terkirim: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent / "status.json"
    if not p.exists():
        print("Belum ada status.json — jalankan run.py --sekali dulu.")
        raise SystemExit(1)
    st = json.loads(p.read_text(encoding="utf-8"))
    print(*susun(st), sep="\n\n")
    if "--kirim" in sys.argv:
        print("\n✅ terkirim" if kirim(st) else "\n❌ gagal")
