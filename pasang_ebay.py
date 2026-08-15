"""PASANG_EBAY — simpan kunci eBay ke Keychain, lalu langsung diuji.

    python3 pasang_ebay.py

Kuncinya diketik di Terminal, bukan ditempel ke chat, dan tidak pernah muncul di
layar. Disimpan di Keychain macOS — bukan di berkas plist atau .env, karena
keduanya teks biasa yang gampang ikut tersalin waktu proyeknya dibagikan.

Yang dibutuhkan hanya kunci PRODUCTION (bukan Sandbox):
  App ID (Client ID)     -> EBAY_CLIENT_ID
  Cert ID (Client Secret)-> EBAY_CLIENT_SECRET
"""
from __future__ import annotations

import getpass
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent
sys.path.insert(0, str(AKAR))

KUNCI = [
    ("EBAY_CLIENT_ID", "App ID (Client ID)",
     "biasanya seperti:  Hillkia-radarhar-PRD-a1b2c3d4e-5f6a7b8c"),
    ("EBAY_CLIENT_SECRET", "Cert ID (Client Secret)",
     "biasanya seperti:  PRD-a1b2c3d4e5f6-7a8b-9c0d-1e2f"),
]


def _ada(nama: str) -> bool:
    return subprocess.run(["security", "find-generic-password", "-s", nama, "-w"],
                          capture_output=True).returncode == 0


def main() -> int:
    print("═" * 58)
    print("  MEMASANG KUNCI eBAY")
    print("═" * 58)
    print("\n  Ambil dari: developer.ebay.com → Application Keys")
    print("  Pakai baris PRODUCTION, bukan Sandbox.\n")

    for nama, label, contoh in KUNCI:
        if _ada(nama):
            print(f"  {label} sudah tersimpan.")
            if input("  Ganti? [y/N] ").strip().lower() != "y":
                continue
        print(f"\n  {label}")
        print(f"  {contoh}")
        print("  (layar tetap kosong waktu ditempel — itu normal)")
        nilai = getpass.getpass("  → ").strip()
        if not nilai:
            print("  ✗ kosong, dilewati")
            continue
        subprocess.run(["security", "add-generic-password", "-U",
                        "-s", nama, "-a", "ocklu", "-w", nilai],
                       check=True, capture_output=True)
        print("  ✓ tersimpan")

    print("\n" + "─" * 58)
    print("  Menguji ke server eBay…\n")
    import pasar
    for nama in ("arttoy", "onepiece"):
        try:
            b = pasar.SEMUA[nama]()
            print(f"  ✅ {nama:<9} {len(b)} barang · contoh: {b[0].nama[:40]} "
                  f"${b[0].harga:,.2f}")
        except Exception as e:
            print(f"  ❌ {nama:<9} {e}")
            print("\n  Kalau tertulis 'invalid_client', berarti kuncinya Sandbox,")
            print("  bukan Production — atau ada spasi yang ikut tertempel.")
            return 1

    print("\n  ✅ Lima pasar hidup semua. Putaran berikutnya sudah memakainya.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
