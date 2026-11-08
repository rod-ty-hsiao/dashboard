#!/usr/bin/env python3
"""抓投資分頁需要的價格，存成 prices.json（同一個網站底下，儀表板直接讀，不會被 CORS 擋住）。

只用 Python 內建套件。來源是 Yahoo Finance 的公開圖表資料（非官方介面，格式可能變動；抓不到的項目會略過，不會讓整個流程失敗）。
要追蹤別的產品，把代號加進 SYMBOLS；儀表板裡的對應名稱寫在 index.html 的產品 feed 欄位（例如 yf:0050.TW）。
"""
import json, sys, time, datetime, urllib.request, urllib.parse

SYMBOLS = [
    "LU0122379950-USD.LU",  # 貝萊德世界健康科學基金 A2（美元）淨值
    "00719B.TWO",           # 元大美債1-3（櫃買，瀏覽器無法直接取得）
    "0050.TW", "00646.TW", "00910.TW",
    "^GSPC",                # S&P 500
    "^TWII",                # 台灣加權指數
    "ACWI",                 # MSCI ACWI（以 ACWI ETF 代替）
    "TWD=X",                # 美元兌台幣
]
RANGE = "5y"

def fetch(symbol):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1d" % (urllib.parse.quote(symbol), RANGE)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; dashboard-price-fetch)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    res = data["chart"]["result"][0]
    off = res["meta"].get("gmtoffset", 0)
    closes = res["indicators"]["quote"][0]["close"]
    out = []
    for ts, c in zip(res["timestamp"], closes):
        if c is None:
            continue
        d = datetime.datetime.fromtimestamp(ts + off, datetime.timezone.utc).strftime("%Y-%m-%d")
        out.append([d, round(float(c), 4)])
    return out

def main():
    series, failed = {}, []
    for s in SYMBOLS:
        for attempt in range(3):
            try:
                series["yf:" + s] = fetch(s)
                break
            except Exception as e:  # 失敗就重試，還是不行就略過
                if attempt == 2:
                    failed.append("%s (%s)" % (s, e))
                time.sleep(2)
        time.sleep(0.6)
    doc = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "series": series}
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("ok:", ", ".join("%s=%d" % (k, len(v)) for k, v in series.items()))
    if failed:
        print("failed:", "; ".join(failed), file=sys.stderr)
    if not series:
        sys.exit(1)

if __name__ == "__main__":
    main()
