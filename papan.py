"""PAPAN — merakit dashboard HTML dari isi gudang.

Ini barang yang dilihat klien, jadi yang ditampilkan harus tahan diperiksa:
mereka menilai harga tiap hari dan akan tahu lebih dulu kalau angkanya keliru.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import gudang

AKAR = Path(__file__).resolve().parent
KELUAR = AKAR / "papan.html"

NAMA_PASAR = {"pokemon": "Pokémon TCG", "cs2": "CS2 Skins",
              "mtg": "Magic: The Gathering", "arttoy": "Art Toys", "onepiece": "One Piece TCG"}


def _baris(x: dict) -> str:
    naik = x["ubah"] > 0
    n = html.escape(x["nama"][:64])
    if x["tautan"]:
        n = f'<a href="{html.escape(x["tautan"])}" target="_blank" rel="noopener">{n}</a>'
    # Persen DAN dolar, berdampingan. Salah satunya sendirian menyesatkan:
    # "-0,4%" terbaca sepele padahal itu $62 pada satu skin, dan "+$0,01"
    # terbaca sepele padahal itu 5,6% pada kartu murah. Pedagang memutuskan
    # dari dua-duanya sekaligus.
    d = x.get("selisih", x["kini"] - x["dulu"])
    return (f'<tr><td class="p">{html.escape(NAMA_PASAR.get(x["pasar"], x["pasar"]))}</td>'
            f'<td>{n}</td><td class="a">${x["dulu"]:,.2f}</td>'
            f'<td class="a">${x["kini"]:,.2f}</td>'
            f'<td class="a {"n" if naik else "t"}">{"+" if naik else "−"}'
            f'${abs(d):,.2f}</td>'
            f'<td class="a {"n" if naik else "t"}">{"+" if naik else ""}{x["ubah"]}%</td></tr>')


def rakit(pid: int, catatan: str = "") -> Path:
    semua = gudang.gerak(pid)
    # Bug yang pernah lolos: tabel "naik paling tajam" hanya DIURUTKAN, tidak
    # disaring. Waktu tidak ada yang naik, isinya jadi barang-barang yang turun —
    # persis kebalikan judulnya. Penyaringan tanda harus di sini, bukan di query.
    naik = [x for x in semua if x["ubah"] > 0][:15]
    turun = sorted((x for x in semua if x["ubah"] < 0), key=lambda x: x["ubah"])[:15]
    r = gudang.ringkas()
    lama = gudang.pembanding(pid)

    if not semua:
        isi = ('<p class="kosong">Belum ada pembanding yang cukup jauh jaraknya. '
               'Potret kedua diambil minimal 4 jam setelah yang pertama — '
               'dua potret berdekatan hanya menghasilkan derau, bukan pergerakan.</p>')
    else:
        isi = ""
        for judul, data, kelas in (("Naik paling tajam", naik, "n"),
                                   ("Turun paling dalam", turun, "t")):
            if not data:
                isi += f'<h2>{judul}</h2><p class="kosong">Tidak ada.</p>'
                continue
            isi += (f'<h2>{judul} <span class="jml">{len(data)}</span></h2>'
                    '<div class="bungkus"><table><thead><tr><th>Pasar</th><th>Barang</th>'
                    '<th class="a">Sebelum</th><th class="a">Sekarang</th>'
                    f'<th class="a">Selisih</th><th class="a">%</th></tr></thead><tbody>'
                    + "".join(_baris(x) for x in data) + "</tbody></table></div>")

    banding = (f'dibandingkan dengan potret {html.escape(lama["waktu"][:16])} UTC'
               if lama else "belum ada pembanding")

    # Sumber hanya boleh menyebut yang BENAR-BENAR menyumbang angka di potret ini.
    # Mencantumkan eBay padahal kuncinya belum ada berarti mengaku memantau pasar
    # yang tidak dipantau — dan itu hal pertama yang dicek klien pasar koleksi.
    ASAL = {"pokemon": "pokemontcg.io (TCGplayer)", "mtg": "scryfall.com",
            "cs2": "api.skinport.com", "arttoy": "eBay Browse",
            "onepiece": "eBay Browse"}
    c = gudang.buka()
    aktif = [x["pasar"] for x in c.execute(
        "SELECT DISTINCT pasar FROM harga WHERE potret=?", (pid,)).fetchall()]
    c.close()
    sumber = " · ".join(dict.fromkeys(ASAL.get(p, p) for p in aktif)) or "—"
    KELUAR.write_text(f"""<!doctype html><html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Radar Harga Koleksi</title><style>
:root{{--bg:#fbfbfa;--kartu:#fff;--garis:#e6e4e0;--teks:#1c1b19;--redup:#6b6862;
--naik:#0a7d3f;--turun:#b4231f}}
@media(prefers-color-scheme:dark){{:root{{--bg:#191817;--kartu:#211f1e;--garis:#333130;
--teks:#eeecea;--redup:#9b9792;--naik:#4ec27f;--turun:#f0736e}}}}
*{{box-sizing:border-box}}body{{margin:0;padding:28px 18px 60px;background:var(--bg);
color:var(--teks);font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:940px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}}
.sub{{color:var(--redup);font-size:13px;margin:0 0 22px}}
.kartu{{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 26px}}
.k{{background:var(--kartu);border:1px solid var(--garis);border-radius:10px;
padding:10px 14px;min-width:104px}}
.k b{{display:block;font-size:19px}}.k span{{color:var(--redup);font-size:12px}}
h2{{font-size:15px;margin:26px 0 9px;display:flex;align-items:center;gap:8px}}
.jml{{background:var(--garis);color:var(--redup);border-radius:20px;padding:1px 8px;
font-size:11px;font-weight:400}}
.bungkus{{overflow-x:auto;border:1px solid var(--garis);border-radius:10px;
background:var(--kartu)}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid var(--garis);
white-space:nowrap}}
th{{font-weight:600;color:var(--redup);font-size:11.5px;text-transform:uppercase;
letter-spacing:.04em}}
tr:last-child td{{border-bottom:0}}
td.a,th.a{{text-align:right;font-variant-numeric:tabular-nums}}
td.p{{color:var(--redup);font-size:12px}}
.n{{color:var(--naik);font-weight:600}}.t{{color:var(--turun);font-weight:600}}
a{{color:inherit}}.kosong{{color:var(--redup);font-size:13.5px}}
.catatan{{background:var(--kartu);border:1px solid var(--garis);border-left:3px solid #d99a2b;
border-radius:8px;padding:9px 13px;font-size:12.5px;color:var(--redup);margin:0 0 20px}}
footer{{margin-top:34px;color:var(--redup);font-size:11.5px;line-height:1.7}}
</style></head><body><main>
<h1>Radar Harga Koleksi</h1>
<p class="sub">Potret {datetime.now():%d %b %Y · %H:%M} — {banding}</p>
{f'<p class="catatan">{html.escape(catatan)}</p>' if catatan else ''}
<div class="kartu">
 <div class="k"><b>{r['barang']:,}</b><span>barang dipantau</span></div>
 <div class="k"><b>{r['potret']}</b><span>potret harga</span></div>
 <div class="k"><b class="n">{len(naik)}</b><span>naik</span></div>
 <div class="k"><b class="t">{len(turun)}</b><span>turun</span></div>
</div>
{isi}
<footer>
Sumber harga: {sumber}.<br>
Angka adalah harga tercatat di pasar tersebut pada waktu potret diambil, bukan
penilaian atau saran beli-jual. Barang yang belum pernah muncul di potret
sebelumnya tidak dihitung sebagai kenaikan.
</footer></main></body></html>""", encoding="utf-8")
    return KELUAR


if __name__ == "__main__":
    c = gudang.buka()
    b = c.execute("SELECT id FROM potret ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not b:
        print("Gudang kosong. Jalankan:  python3 run.py --sekali")
    else:
        print("✅", rakit(b["id"]))
