import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

FRED_API_KEY = os.getenv("FRED_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_fred_latest(series_id):
    """從 FRED API 抓取最近的數值"""
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        obs = [o for o in data.get("observations", []) if o["value"] != "."]
        if len(obs) >= 2:
            current_val = float(obs[0]["value"])
            prev_val = float(obs[1]["value"])
            date = obs[0]["date"]
            return current_val, prev_val, date
    except Exception as e:
        print(f"Error fetching FRED {series_id}: {e}")
    return None, None, None

def get_yf_metrics(ticker_symbol):
    """從 Yahoo Finance 抓取近一個月收盤價，包含最新、前一日與10個交易日前"""
    try:
        t = yf.Ticker(ticker_symbol)
        df = t.history(period="1mo")
        if len(df) >= 2:
            current_val = float(df["Close"].iloc[-1])
            prev_val = float(df["Close"].iloc[-2])
            # 若資料足夠，抓取 10 個交易日前的價格
            val_10d_ago = float(df["Close"].iloc[-10]) if len(df) >= 10 else None
            return current_val, prev_val, val_10d_ago
    except Exception as e:
        print(f"Error fetching YF {ticker_symbol}: {e}")
    return None, None, None

def analyze_market(move, hy_oas, ig_oas, hyg_curr, hyg_prev, hyg_10d):
    """綜合判斷市場情境，包含利率壓力與信用市場壓力（含緩跌邏輯）"""
    
    # 1. 判斷利率壓力
    rate_stress = move > 100 if move else False
    
    # 2. 判斷 HYG 是否出現急跌或緩跌
    hyg_acute_stress = False
    hyg_chronic_stress = False
    
    if hyg_curr and hyg_prev:
        daily_pct_change = ((hyg_curr - hyg_prev) / hyg_prev) * 100
        if daily_pct_change <= -1.0:
            hyg_acute_stress = True
            
    if hyg_curr and hyg_10d:
        tenday_pct_change = ((hyg_curr - hyg_10d) / hyg_10d) * 100
        if tenday_pct_change <= -2.0:
            hyg_chronic_stress = True
            
    # 3. 綜合判斷信用壓力 (利差擴大 或 HYG 遭到顯著拋售)
    credit_stress = False
    if hy_oas and ig_oas:
        credit_stress = (hy_oas > 4.5) or (ig_oas > 1.5) or hyg_acute_stress or hyg_chronic_stress
    elif hyg_acute_stress or hyg_chronic_stress:
        # 即使 FRED 資料缺失，若 HYG 呈現明顯跌幅，仍視為信用承壓
        credit_stress = True
    
    # 4. 產出結論
    # 4. 產出結論
    if rate_stress and not credit_stress:
        summary = "🟡 【利率市場承壓，但信用結構健康】"
        detail = (
            "MOVE 指數高於 100，顯示美債市場波動劇烈、利率預期混亂；\n"
            "但信用利差維持在安全水準，且 HYG 無顯著跌幅（未出現急跌或連續緩跌），\n"
            "企業融資未現斷鏈危機。無須因殖利率高而盲目看空。"
        )
        color = 0xF1C40F  # 黃色邊線
    elif rate_stress and credit_stress:
        summary = "🔴 【警訊：利率壓力已傳導至信用市場】"
        detail = (
            "MOVE 指數偏高，且觀察到企業信用利差顯著擴大，或 HYG 出現拋售（單日大跌或波段緩跌）。\n"
            "顯示資金成本已實質傷及企業融資，股市恐面臨較大回調壓力。"
        )
        color = 0xE74C3C  # 紅色邊線
    elif not rate_stress and credit_stress:
        summary = "🟠 【注意：利率平穩但個別信用風險升溫】"
        detail = "公債波動不大，但信用利差擴散或 HYG 呈現跌勢，需警惕企業端個別違約或流動性收緊。"
        color = 0xE67E22  # 橘色邊線
    else:
        summary = "🟢 【市場處於穩定風險溢價區間】"
        detail = "公債波動度與信用利差均在健康低檔，HYG 價格平穩，無系統性風險訊號。"
        color = 0x2ECC71  # 綠色邊線
        
    return summary, detail, color

def send_discord_notification(embed_data):
    if not DISCORD_WEBHOOK_URL:
        print("未設定 DISCORD_WEBHOOK_URL")
        return
    payload = {"embeds": [embed_data]}
    res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if res.status_code != 204:
        print(f"Discord 發送失敗: {res.status_code}, {res.text}")

def main():
    # 1. 抓取指標
    move_curr, move_prev, _ = get_yf_metrics("^MOVE")
    hyg_curr, hyg_prev, hyg_10d = get_yf_metrics("HYG")
    
    hy_oas_curr, hy_oas_prev, fred_date = get_fred_latest("BAMLH0A0HYM2")
    ig_oas_curr, ig_oas_prev, _ = get_fred_latest("BAMLC0A0CM")
    
    # 2. 格式化數值變動 (包含日變動與 10 日變動計算)
    def fmt_chg(curr, prev, unit=""):
        if curr is None or prev is None:
            return "N/A"
        diff = curr - prev
        sign = "+" if diff > 0 else ""
        return f"{curr:.2f}{unit} ({sign}{diff:.2f})"

    # 特別為 HYG 準備一個 10 日跌幅的字串，方便在 Discord 觀察
    hyg_10d_str = "N/A"
    if hyg_curr and hyg_10d:
        pct_10d = ((hyg_curr - hyg_10d) / hyg_10d) * 100
        sign = "+" if pct_10d > 0 else ""
        hyg_10d_str = f"{sign}{pct_10d:.2f}%"

    # 3. 邏輯分析
    summary, detail, color = analyze_market(move_curr, hy_oas_curr, ig_oas_curr, hyg_curr, hyg_prev, hyg_10d)
    
    # 4. 組裝 Discord Rich Embed
    fields = [
        {"name": "MOVE（美債波動率）", "value": fmt_chg(move_curr, move_prev), "inline": True},
        {"name": "HY OAS（高收益債利差）", "value": fmt_chg(hy_oas_curr, hy_oas_prev, "%"), "inline": True},
        {"name": "IG OAS（投資級債利差）", "value": fmt_chg(ig_oas_curr, ig_oas_prev, "%"), "inline": True},
        {"name": "HYG（高收益債ETF）", "value": fmt_chg(hyg_curr, hyg_prev), "inline": True},
        {"name": "HYG 近10日變動", "value": hyg_10d_str, "inline": True},
        {"name": "FRED資料最新日期", "value": fred_date or datetime.today().strftime('%Y-%m-%d'), "inline": True},
        {"name": "研判結論", "value": detail, "inline": False}
    ]
    
    embed = {
        "title": f"📊 美債波動與信用利差市場監控 | {summary}",
        "color": color,
        "fields": fields,
        "footer": {"text": "每日自動排程監測 • 基於 FRED 與 Yahoo Finance"}
    }
    
    send_discord_notification(embed)

if __name__ == "__main__":
    main()
