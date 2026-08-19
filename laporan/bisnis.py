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
b.append(f"  gig publik {kode('https://www.fiverr.com/ockylockyl/audit-your-website-for-wcag-and-ada-accessibility-compliance')}")
b.append("  (403 dari server itu normal — Fiverr menolak permintaan non-browser)")
b.append("")

b.append("── COWORK GENZ " + "─" * 28)
b.append(f"  papan harga {kode('https://hillkia.github.io/tcg-radar/')}")
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
