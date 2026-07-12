import os
import re
import json
import requests
from playwright.sync_api import sync_playwright

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TARGET_URL = "https://www.celebritycruises.com/cruises?search=departurePort:HKG,ICN,NRT,SIN,YOK&sort=by:PRICE|order:ASC&country=USA"
HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def send_discord_notification(cruise, is_price_drop=False, old_price=None):
    if not DISCORD_WEBHOOK_URL:
        print("未設定 Discord Webhook URL")
        return

    if is_price_drop:
        title_msg = f"📉 **【價格調降】名人郵輪變得更便宜了！** (原價 ${old_price})"
    else:
        title_msg = f"🚢 **發現低於 $1500 美金的名人郵輪航程！**"

    content = (
        f"{title_msg}\n"
        f"**【船名】** {cruise['ship_name']}\n"
        f"**【天數】** {cruise['nights']}\n"
        f"**【出發日期】** {cruise['sail_date']}\n"
        f"**【出發/目的港】** {cruise['ports_route']}\n"
        f"**【主要行程】** {cruise['itinerary_title']}\n"
        f"**【最新價格】** ${cruise['price']:,} USD (每人平均)\n"
        f"**【詳情連結】** {cruise['full_link']}\n"
        f"----------------------------------------"
    )
    
    payload = {"content": content}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print(f"成功通知: {cruise['ship_name']} - ${cruise['price']}")
        else:
            print(f"Discord 通知失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print(f"發送 Discord 通知時發生錯誤: {e}")

def parse_cruises():
    history = load_history()
    history_updated = False

    with sync_playwright() as p:
        print("啟動 Firefox 瀏覽器...")
        browser = p.firefox.launch(headless=True)
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            locale="en-US",
            timezone_id="America/New_York"
        )
        page = context.new_page()
        
        print("正在載入名人郵輪網頁 (Firefox)...")
        
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000) 
            page.wait_for_selector("div[data-testid^='cruise-card-']", timeout=30000)
        except Exception as e:
            print(f"載入或等待元素時發生錯誤: {e}")
            page.screenshot(path="error_screenshot.png", full_page=True)
            with open("error_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            browser.close()
            raise e
            
        cards = page.query_selector_all("div[data-testid^='cruise-card-']")
        print(f"共找到 {len(cards)} 個航程卡片。")
        
        for card in cards:
            try:
                price_text_el = card.query_selector("span[class*='CruiseCardPriceValue']")
                if not price_text_el:
                    continue
                price_text = price_text_el.inner_text().replace(",", "").strip()
                price = int(re.search(r'\d+', price_text).group())
                
                if price >= 1500:
                    continue
                
                ship_name_el = card.query_selector("h3[data-testid^='cruise-ship-label-']")
                ship_name = ship_name_el.inner_text().strip() if ship_name_el else "未知船名"
                
                ports_route = "未知港口資訊"
                route_el = card.query_selector("div[class*='CruiseCardLocationListBase']")
                if route_el:
                    ports_route = route_el.inner_text().replace("\n", " ").strip()
                
                link_attr = card.get_attribute("data-product-view-link")
                link = link_attr if link_attr else ""
                clean_link = link.lstrip('/') 
                full_link = f"https://www.celebritycruises.com/{clean_link}" if clean_link else "無連結"

                # 提取出發日期 (供歷史紀錄與顯示使用)
                sail_date = "未知日期"
                date_match = re.search(r'sailDate=([^&]+)', full_link)
                if date_match:
                    sail_date = date_match.group(1)

                nights = "未知天數"
                night_match = re.search(r'itinerary/(\d+)-night', link, re.IGNORECASE)
                if night_match:
                    nights = f"{night_match.group(1)} Nights"
                else:
                    nights_el = card.query_selector("span[class*='Tipper-styled__Tipper-content']")
                    nights = nights_el.inner_text().strip() if nights_el else "未知天數"
                
                itinerary_title = "未知行程"
                title_el = card.query_selector("div[class*='RefinedCruiseCardBase'] >> xpath=../..//h2")
                if title_el:
                    itinerary_title = title_el.inner_text().strip()
                elif "itinerary/" in link:
                    raw_title = link.split("itinerary/")[1].split("-from-")[0].replace("-", " ").title()
                    title_match = re.search(r'^\d+\s*Nights?\s+(.*)', raw_title, re.IGNORECASE)
                    if title_match:
                        itinerary_title = title_match.group(1).strip()
                    else:
                        itinerary_title = raw_title

                # 建立唯一識別碼：船名 + 出發日期 + 行程
                unique_id = f"{ship_name}_{sail_date}_{itinerary_title}"

                cruise_data = {
                    "ship_name": ship_name,
                    "nights": nights,
                    "sail_date": sail_date,
                    "ports_route": ports_route,
                    "itinerary_title": itinerary_title,
                    "price": price,
                    "full_link": full_link
                }
                
                # 檢查歷史紀錄
                if unique_id in history:
                    old_price = history[unique_id]
                    if price == old_price:
                        print(f"[{unique_id}] 價格相同 (${price})，跳過通知。")
                        continue
                    elif price < old_price:
                        send_discord_notification(cruise_data, is_price_drop=True, old_price=old_price)
                    else:
                        # 價格變貴了但還在 1500 以下，仍然通知
                        send_discord_notification(cruise_data)
                else:
                    # 全新低於 1500 的行程
                    send_discord_notification(cruise_data)
                
                # 更新歷史紀錄
                history[unique_id] = price
                history_updated = True
                
            except Exception as card_err:
                print(f"解析卡片時發生錯誤: {card_err}")
                continue
                
        browser.close()

        if history_updated:
            save_history(history)
            print("歷史紀錄已更新。")

if __name__ == "__main__":
    parse_cruises()
