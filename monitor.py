import os
import re
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TARGET_URL = "https://www.celebritycruises.com/cruises?search=departurePort:HKG,ICN,NRT,SIN,YOK&sort=by:PRICE|order:ASC&country=USA"

def send_discord_notification(cruise):
    if not DISCORD_WEBHOOK_URL:
        print("未設定 Discord Webhook URL")
        return

    content = (
        f"🚢 **發現低於 $1500 美金的名人郵輪航程！**\n"
        f"**【船名】** {cruise['ship_name']}\n"
        f"**【天數】** {cruise['nights']}\n"
        f"**【出發/目的港】** {cruise['ports_route']}\n"
        f"**【主要行程】** {cruise['itinerary_title']}\n"
        f"**【價格】** ${cruise['price']:,} USD (每人平均)\n"
        f"**【詳情連結】** https://www.celebritycruises.com{cruise['link']}\n"
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
    with sync_playwright() as p:
        # 開啟瀏覽器
        browser = p.chromium.launch(headless=True)
        
        # 模擬正常的 Mac 電腦瀏覽器
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\"",
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": "\"macOS\""
            }
        )
        page = context.new_page()
        
        # 載入隱身腳本，避免被識別為 Playwright
        stealth_sync(page)
        
        print("正在載入名人郵輪網頁 (Stealth Mode)...")
        
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000) # 強制等待 8 秒讓前端與防爬蟲系統運作
            
            # 等待郵輪卡片載入
            page.wait_for_selector("div[data-testid^='cruise-card-']", timeout=30000)
            
        except Exception as e:
            print(f"載入或等待元素時發生錯誤: {e}")
            print("正在擷取畫面與 HTML 原始碼以供除錯...")
            page.screenshot(path="error_screenshot.png", full_page=True)
            with open("error_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            browser.close()
            raise e
            
        # 取得所有郵輪卡片元素
        cards = page.query_selector_all("div[data-testid^='cruise-card-']")
        print(f"共找到 {len(cards)} 個航程卡片。")
        
        for card in cards:
            try:
                price_text_el = card.query_selector("span[class*='CruiseCardPriceValue']")
                if not price_text_el:
                    continue
                price_text = price_text_el.inner_text().replace(",", "").strip()
                price = int(re.search(r'\d+', price_text).group())
                
                # 條件：低於 1500 美金
                if price >= 1500:
                    continue
                
                ship_name_el = card.query_selector("h3[data-testid^='cruise-ship-label-']")
                ship_name = ship_name_el.inner_text().strip() if ship_name_el else "未知船名"
                
                nights_el = card.query_selector("span[class*='Tipper-styled__Tipper-content']")
                nights = nights_el.inner_text().strip() if nights_el else "未知天數"
                
                ports_route = "未知港口資訊"
                route_el = card.query_selector("div[class*='CruiseCardLocationListBase']")
                if route_el:
                    ports_route = route_el.inner_text().replace("\n", " ").strip()
                
                itinerary_title = "未知行程"
                link_attr = card.get_attribute("data-product-view-link")
                link = link_attr if link_attr else ""
                
                title_el = card.query_selector("div[class*='RefinedCruiseCardBase'] >> xpath=../..//h2")
                if title_el:
                    itinerary_title = title_el.inner_text().strip()
                elif "itinerary/" in link:
                    itinerary_title = link.split("itinerary/")[1].split("-from-")[0].replace("-", " ").title()

                cruise_data = {
                    "ship_name": ship_name,
                    "nights": nights,
                    "ports_route": ports_route,
                    "itinerary_title": itinerary_title,
                    "price": price,
                    "link": link
                }
                
                send_discord_notification(cruise_data)
                
            except Exception as card_err:
                print(f"解析卡片時發生錯誤: {card_err}")
                continue
                
        browser.close()

if __name__ == "__main__":
    parse_cruises()
