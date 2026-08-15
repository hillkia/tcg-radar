# Radar Harga Koleksi

Memantau harga pasar koleksi dua kali sehari, lalu melaporkan apa yang **bergerak
berarti** — bukan sekadar menampilkan harga hari ini, karena situs pasarnya sudah
melakukan itu gratis. Yang dibayar orang adalah perubahannya.

**Dashboard hidup:** `https://hillkia.github.io/tcg-radar/`

## Pasar

| Pasar | Sumber | Kunci |
|---|---|---|
| Pokémon TCG | pokemontcg.io (harga TCGplayer) | tidak perlu |
| Magic: The Gathering | scryfall.com | tidak perlu |
| Skin CS2 | api.skinport.com | tidak perlu |
| Art Toy (Labubu, Pop Mart) | eBay Browse | perlu, gratis |
| One Piece TCG | eBay Browse | perlu, gratis |

## Jalan sendiri

GitHub Actions menjalankannya 00:00 dan 12:00 UTC (07:00 dan 19:00 WIB), lalu
menyimpan database dan menerbitkan ulang dashboard. Laptop tidak perlu menyala.

## Menjalankan di laptop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py --check     # periksa kelima pasar, tidak menyimpan
.venv/bin/python run.py --sekali    # tarik, simpan, rakit dashboard
.venv/bin/python rekam.py           # video demo 26 detik dari dashboard
```

Pakai `.venv/bin/python`, bukan `python3`: Skinport hanya melayani permintaan
ber-Brotli, dan modul `brotli` hanya terpasang di venv.

## Empat keputusan yang menentukan hasilnya

Semuanya lahir dari data nyata, bukan dari perkiraan. Kalau ada yang membongkarnya,
laporan ini berhenti bisa dipercaya.

**1. Pembanding wajib berjarak minimal 4 jam.** Dua potret berdekatan tidak
mengandung informasi; harga tidak bergerak dalam hitungan menit, tetapi
pembaginya tetap kecil sehingga derau terlihat seperti lonjakan.

**2. Ambang persen ATAU dolar, bukan persen saja.** Terukur 15/8/2026: kartu $0,18
naik satu sen tercatat "+5,6%" dan masuk laporan, sementara stiker CS2 $82.000
bergerak $171,93 **tidak** masuk karena itu hanya 0,2%. Yang kedua justru yang
ingin diketahui pedagang. Ada lantai $1 untuk membuang derau receh.

**3. Penyetelan serentak bursa dibuang.** Hari yang sama, 10 dari 11 "penurunan"
Skinport punya rasio harga identik (0,99633) — itu bursanya menghitung ulang
kurs/biaya, bukan sebelas barang jatuh bersamaan. Mengirimkannya sebagai temuan
ke orang yang memantau harga tiap hari akan ketahuan dalam satu balasan.

**4. Sumber yang mati dikatakan mati.** Tidak ada harga karangan, tidak ada nilai
kemarin yang dipakai diam-diam. Dashboard hanya menyebut sumber yang benar-benar
menyumbang angka pada potret itu.

## Yang sengaja TIDAK ada di sini

Sandi Gmail. Dia memberi akses baca dan kirim ke seluruh kotak masuk, dan
menaruhnya di GitHub berarti keamanannya bergantung pada keamanan akun GitHub.
Pengiriman email tetap dijalankan dari laptop, sandinya di Keychain macOS.

Kunci eBay boleh ada di Secrets: itu hanya izin baca katalog publik, bisa dicabut
kapan saja, dan tidak tersambung ke uang maupun email.
