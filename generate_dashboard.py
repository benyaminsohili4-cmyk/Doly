import json, re, urllib.request
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
MARKET = DATA / "market.json"
HISTORY = DATA / "history.json"

# Public raw GitHub endpoints for the requested repository.
CANDIDATES = [
    "https://raw.githubusercontent.com/itsyebekhe/usd/main/market.json",
    "https://raw.githubusercontent.com/itsyebekhe/usd/master/market.json",
    "https://raw.githubusercontent.com/itsyebekhe/usd/main/api/market.json",
    "https://raw.githubusercontent.com/itsyebekhe/usd/master/api/market.json",
]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "usd-gold-dashboard/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def first_number(obj, keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in keys:
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    m = re.search(r"-?\d+(?:[.,]\d+)?", v.replace(",", ""))
                    if m:
                        return float(m.group())
            found = first_number(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = first_number(v, keys)
            if found is not None:
                return found
    return None

def extract_prices(data):
    usd = first_number(data, {"usd", "dollar", "dollar_price", "usdt", "usd_price"})
    gold = first_number(data, {"gold", "gold_price", "mesghal", "mithqal", "talagold"})
    # If nested objects have "price", try matching by context.
    if isinstance(data, dict):
        for k, v in data.items():
            name = str(k).lower()
            if usd is None and any(x in name for x in ("usd", "dollar")):
                usd = first_number(v, {"price", "value", "rate"})
            if gold is None and any(x in name for x in ("gold", "tala", "mesghal", "mithqal")):
                gold = first_number(v, {"price", "value", "rate"})
    return usd, gold

def load_history():
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:
        return {"usd": [], "gold": [], "updated_at": None}

def save_history(hist, usd, gold, stamp):
    for key, value in (("usd", usd), ("gold", gold)):
        if value is None:
            continue
        arr = hist.setdefault(key, [])
        arr.append({"time": stamp, "price": round(value, 4)})
        # Keep about 90 days at 30-minute intervals.
        hist[key] = arr[-4320:]
    hist["updated_at"] = stamp
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")

def fetch_market():
    last_error = None
    for url in CANDIDATES:
        try:
            data = fetch_json(url)
            usd, gold = extract_prices(data)
            if usd is not None or gold is not None:
                return data, usd, gold, url
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Could not fetch a usable API response: {last_error}")

def analyze(values):
    vals = [float(x["price"]) for x in values[-336:] if "price" in x]
    if len(vals) < 2:
        return "داده کافی برای تحلیل وجود ندارد.", None
    current = vals[-1]
    avg = sum(vals) / len(vals)
    change = ((current - vals[0]) / vals[0] * 100) if vals[0] else 0
    if current > avg * 1.02:
        text = "📈 روند صعودی؛ قیمت بالاتر از میانگین اخیر است."
    elif current < avg * 0.98:
        text = "📉 روند نزولی؛ قیمت پایین‌تر از میانگین اخیر است."
    else:
        text = "⚖️ روند خنثی؛ قیمت نزدیک میانگین اخیر است."
    return f"{text} تغییر این بازه: {change:+.2f}٪", change

def fmt(v):
    if v is None:
        return "نامشخص"
    return f"{v:,.0f}"

def html(hist, market, source, stamp):
    usd = market.get("usd")
    gold = market.get("gold")
    ua, uc = analyze(hist.get("usd", []))
    ga, gc = analyze(hist.get("gold", []))
    usd_points = hist.get("usd", [])[-96:]
    gold_points = hist.get("gold", [])[-96:]
    def js_points(points):
        return json.dumps([[x["time"], x["price"]] for x in points], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#111827">
<title>داشبورد دلار و طلا</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Tahoma,Arial,sans-serif;background:#0b1220;color:#eef2ff}}
.wrap{{max-width:980px;margin:auto;padding:22px}}.hero{{padding:25px 0;text-align:center}}
h1{{margin:0 0 8px;font-size:28px}}.muted{{color:#aab4c8;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}}
.card{{background:#111a2b;border:1px solid #26334a;border-radius:18px;padding:20px;box-shadow:0 10px 30px #0004}}
.label{{color:#aab4c8;font-size:14px}}.price{{font-size:30px;font-weight:800;margin:10px 0}}.unit{{font-size:12px;color:#94a3b8}}
.analysis{{margin-top:14px;padding:12px;border-radius:12px;background:#172338;font-size:14px;line-height:1.8}}
.chart{{margin-top:16px;background:#111a2b;border-radius:18px;padding:16px;overflow:hidden}}
canvas{{width:100%;height:220px;display:block}}footer{{text-align:center;padding:25px;color:#77839a;font-size:12px}}
.badge{{display:inline-block;padding:5px 9px;border-radius:99px;background:#172338;color:#cbd5e1;font-size:12px}}
</style></head><body><main class="wrap">
<section class="hero"><h1>📊 داشبورد دلار و طلا</h1>
<div class="muted">به‌روزرسانی خودکار با GitHub Actions</div></section>
<section class="grid">
<div class="card"><div class="label">💵 دلار</div><div class="price">{fmt(usd)}</div><div class="unit">تومان</div>
<div class="analysis">{ua}</div></div>
<div class="card"><div class="label">🪙 طلا</div><div class="price">{fmt(gold)}</div><div class="unit">تومان</div>
<div class="analysis">{ga}</div></div>
</section>
<section class="chart"><div class="badge">روند ۴۸ ساعت اخیر</div><canvas id="c"></canvas></section>
<footer>آخرین بروزرسانی: {stamp} · منبع: itsyebekhe/usd · داده‌ها صرفاً اطلاعاتی هستند.</footer>
</main>
<script>
const usd={js_points(usd_points)}, gold={js_points(gold_points)};
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
function draw(points){{
 const dpr=devicePixelRatio||1,w=canvas.clientWidth,h=220;canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 if(points.length<2){{ctx.fillText('داده نمودار کافی نیست',20,30);return}}
 const ys=points.map(p=>p[1]),min=Math.min(...ys),max=Math.max(...ys),pad=(max-min||1)*.1;
 ctx.beginPath();points.forEach((p,i)=>{{let x=i*(w-20)/(points.length-1)+10,y=h-20-(p[1]-(min-pad))/(max-min+2*pad)*(h-40);i?ctx.lineTo(x,y):ctx.moveTo(x,y)}});ctx.strokeStyle='#60a5fa';ctx.lineWidth=2;ctx.stroke();
}}
draw(usd.length?usd:gold);addEventListener('resize',()=>draw(usd.length?usd:gold));
</script></body></html>"""

def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hist = load_history()
    try:
        raw, usd, gold, source = fetch_market()
        market = {"usd": usd, "gold": gold, "updated_at": stamp, "source": source}
        MARKET.write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")
        save_history(hist, usd, gold, stamp)
        hist = load_history()
    except Exception as e:
        print("API fetch failed:", e)
        try:
            market = json.loads(MARKET.read_text(encoding="utf-8"))
        except Exception:
            market = {"usd": None, "gold": None, "updated_at": None, "source": "itsyebekhe/usd"}
        source = market.get("source", "itsyebekhe/usd")
    Path(BASE/"index.html").write_text(html(hist, market, source, stamp), encoding="utf-8")
    print("Dashboard generated successfully.")

if __name__ == "__main__":
    main()
