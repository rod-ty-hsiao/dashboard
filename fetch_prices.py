#!/usr/bin/env python3
"""抓投資分頁需要的價格，存成 prices.json（同一個網站底下，儀表板直接讀，不會被 CORS 擋住）。

只用 Python 內建套件。包含兩部分：
1. series：Yahoo Finance 的歷史收盤（基金淨值、指數、匯率，以及儀表板原本就有的幾檔 ETF）。非官方介面，格式可能變動；抓不到的項目會略過。
2. quotes：證交所＋櫃買「所有 ETF（代號 00 開頭）」的最新收盤。儀表板裡新增的 ETF 只要填了代號（例如 0056、00878、00679B），
   就會依代號從這裡查價格，不需要改這支程式。
   想追蹤 ETF 以外的股票（上櫃股票），在同一個資料夾放一個 extra_codes.txt，一行一個代號即可。
"""
import json, sys, time, datetime, re, os, ssl, urllib.request, urllib.parse

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
UA = {"User-Agent": "Mozilla/5.0 (compatible; dashboard-price-fetch)"}
# 證交所／櫃買的憑證缺少 Subject Key Identifier，Python 3.13 以上預設的嚴格檢查會拒絕；關掉「嚴格」旗標，其餘憑證驗證照常進行
CTX = ssl.create_default_context()
CTX.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)


def get_json(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return json.load(r)


def fetch(symbol):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1d" % (urllib.parse.quote(symbol), RANGE)
    data = get_json(url, 30)
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


def roc(d):  # 1151109 -> 2026-11-09
    d = str(d).strip()
    if not re.fullmatch(r"\d{6,7}", d):
        return None
    return "%04d-%s-%s" % (int(d[:-4]) + 1911, d[-4:-2], d[-2:])


def num(x):
    try:
        v = float(str(x).replace(",", ""))
        return v if v > 0 else None
    except Exception:
        return None


def extra_codes():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_codes.txt")
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as f:
        return {l.strip().upper() for l in f if l.strip() and not l.startswith("#")}


def quotes():
    """證交所（上市）＋櫃買（上櫃）的最新收盤；只留 ETF（代號 00 開頭）與 extra_codes.txt 指定的代號。"""
    extra = extra_codes()
    ok = lambda code: bool(re.fullmatch(r"00\d{2,4}[A-Z]?", code)) or code in extra
    out, notes = {}, []
    try:
        for r in get_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"):
            code, d, c = str(r.get("Code", "")).strip().upper(), roc(r.get("Date", "")), num(r.get("ClosingPrice"))
            if ok(code) and d and c:
                out[code] = [d, c]
        notes.append("twse=%d" % len(out))
    except Exception as e:
        notes.append("twse failed (%s)" % e)
    n0 = len(out)
    try:
        for r in get_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes", 60):
            code, d, c = str(r.get("SecuritiesCompanyCode", "")).strip().upper(), roc(r.get("Date", "")), num(r.get("Close"))
            if ok(code) and d and c and code not in out:
                out[code] = [d, c]
        notes.append("tpex=%d" % (len(out) - n0))
    except Exception as e:
        notes.append("tpex failed (%s)" % e)
    return out, notes


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
    q, notes = quotes()
    doc = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "series": series, "quotes": q}
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("ok:", ", ".join("%s=%d" % (k, len(v)) for k, v in series.items()))
    print("quotes:", len(q), "(" + ", ".join(notes) + ")")
    if failed:
        print("failed:", "; ".join(failed), file=sys.stderr)
    if not series and not q:
        sys.exit(1)


if __name__ == "__main__":
    main()
