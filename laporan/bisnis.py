"""Laporan bisnis dari CLOUD — jalan walau laptop mati.

Hanya memeriksa yang bisa dilihat dari luar: apakah halaman hidup, berapa
produk terjual, apakah gig tayang. Angka yang hanya ada di disk laptop
(ledger MYTHOS, hasil audit lokal) sengaja TIDAK diklaim di sini — laporan
cloud yang mengarang angka lokal lebih buruk daripada laporan yang mengaku
tidak tahu.
"""
import json, os, smtplib, ssl, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage

WIB = timezone(timedelta(hours=7))
U = os.environ["GMAIL_USER"]; P = os.environ["GMAIL_APP_PASSWORD"]

def kode(url, n=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return str(urllib.request.urlopen(r, timeout=n).status)
    except Exception as e:
        return str(getattr(e, "code", "mati"))

b = [f"LAPORAN BISNIS (cloud) — {datetime.now(WIB):%A %d %B %Y, %H:%M} WIB", "=" * 56, ""]

b.append("── OCKLU.COM " + "─" * 30)
for n, u in [("situs", "https://ocklu.com"), ("direktori", "https://ocklu.com/ai-readiness/"),
             ("artikel", "https://ocklu.com/artikel/"), ("sitemap", "https://ocklu.com/sitemap.xml")]:
    b.append(f"  {n:11} {kode(u)}")
try:
    sm = urllib.request.urlopen("https://ocklu.com/sitemap.xml", timeout=20).read().decode()
    b.append(f"  {sm.count('<loc>')} URL terdaftar")
except Exception:
    pass
b.append("")

b.append("── GUMROAD " + "─" * 32)
tok = os.environ.get("GUMROAD_TOKEN", "")
if tok:
    try:
        r = json.loads(urllib.request.urlopen(
            f"https://api.gumroad.com/v2/products?access_token={urllib.parse.quote(tok)}", timeout=25).read())
        for p in r.get("products", []):
            b.append(f"  ${p['price']/100:>6.2f} {p['name'][:30]:32} terjual {p['sales_count']}")
        s = json.loads(urllib.request.urlopen(
            f"https://api.gumroad.com/v2/sales?access_token={urllib.parse.quote(tok)}", timeout=25).read())
        b.append(f"  TOTAL PENJUALAN: {len(s.get('sales', []))}")
    except Exception as e:
        b.append(f"  gagal: {str(e)[:50]}")
else:
    b.append("  GUMROAD_TOKEN belum dipasang sebagai secret repo")
b.append("")

b.append("── FIVERR " + "─" * 33)
GIG = "https://www.fiverr.com/ockylockyl/audit-your-website-for-wcag-and-ada-accessibility-compliance"
k = kode(GIG)
# Fiverr menolak permintaan non-browser, jadi kode HTTP saja tidak bisa
# membedakan "gig dihapus" dari "gig hidup tapi menolak robot". Yang dibaca
# di sini apakah halamannya MEMUAT NAMA GIG-nya — itu satu-satunya bukti dari
# luar yang tidak bisa dipalsukan oleh penolakan bot.
try:
    rq = urllib.request.Request(GIG, headers={"User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0"})
    isi = urllib.request.urlopen(rq, timeout=20).read().decode("utf-8", "ignore")
    tayang = "wcag" in isi.lower() and "accessibility" in isi.lower()
    harga = "$35" in isi or "35" in isi
    b.append(f"  gig TAYANG: {'YA' if tayang else 'tidak terbaca'}  (HTTP {k})")
    if tayang:
        b.append("  Compliance Scan $35 · Full Site Audit $85 · Audit+Remediation $195")
except Exception as e:
    b.append(f"  gig HTTP {k} — halaman tidak terbaca dari server ({str(e)[:40]})")
    b.append("  Itu belum tentu mati: Fiverr sering menolak permintaan non-browser.")
b.append(f"  {GIG}")
b.append("  Pesanan & tayangan tidak dibuka Fiverr lewat API — lihat dasbor penjual.")
b.append("")

b.append("── COWORK GENZ " + "─" * 28)
b.append(f"  papan harga {kode('https://hillkia.github.io/tcg-radar/')}")
b.append("")

b.append("── KUNJUNGAN " + "─" * 30)
KUNCI = {"ocklu.com": "Halaman depan", "ocklu.com-direktori": "Direktori audit",
         "ocklu.com-merek": "Halaman per merek", "ocklu.com-artikel": "Daftar artikel",
         "ocklu.com-artikel-baca": "Artikel dibaca"}
import re as _re
tot = 0; tahu = False
for k, nama in KUNCI.items():
    try:
        # nocount=1 supaya pembacaan ini sendiri tidak menaikkan angkanya
        rq = urllib.request.Request("https://hits.sh/" + k + ".svg?nocount=1",
                                    headers={"User-Agent": "ocklu-lapor/1.0"})
        svg = urllib.request.urlopen(rq, timeout=15).read().decode()
        m = _re.findall(r">([\d,]+)<", svg)
        n = int(m[-1].replace(",", "")) if m else None
    except Exception:
        n = None
    if n is None:
        b.append(f"  {nama:22} tidak terbaca")
    else:
        b.append(f"  {nama:22} {n}")
        tot += n; tahu = True
b.append(f"  {'TOTAL ocklu.com':22} {tot}" if tahu else "  total tidak terbaca")
try:
    if tok:
        rr = json.loads(urllib.request.urlopen(
            f"https://api.gumroad.com/v2/products?access_token={urllib.parse.quote(tok)}", timeout=25).read())
        for pr in rr.get("products", []):
            b.append(f"  Gumroad ${pr['price']/100:.0f}{'':10} dilihat {pr.get('view_count','?')}")
except Exception:
    pass
b.append("  Fiverr & Upwork tidak membuka angka kunjungan lewat API —")
b.append("  lihat di dasbor masing-masing.")
b.append("")

b.append("── RPM " + "─" * 36)
b.append("  Belum tersambung — sumber angkanya belum ditentukan.")
b.append("  Kalau RPM = pendapatan per 1000 tayangan, dia baru punya arti")
b.append("  setelah ada tayangan iklan atau penjualan; keduanya masih nol.")
b.append("")

b.append("── CATATAN " + "─" * 32)
b.append("  Laporan ini jalan di GitHub Actions, BUKAN di laptop.")
b.append("  Kalau laptop mati, laporan ini tetap datang.")
b.append("  Angka yang hanya ada di disk laptop tidak diklaim di sini.")

teks = "\n".join(b)
m = EmailMessage()
m["From"] = U; m["To"] = U
m["Subject"] = f"Bisnis {datetime.now(WIB):%d %b %H:%M} — laporan cloud"
m.set_content(teks)
s = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=45)
s.login(U, P); s.send_message(m); s.quit()
print("terkirim")
