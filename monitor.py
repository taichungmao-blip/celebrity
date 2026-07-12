import os
import re
import requests
from playwright.sync_api import sync_playwright

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
    with sync_playwright() as p:
        print("啟動 Firefox 瀏覽器...")
        browser = p.firefox.launch(headless=True)
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.5",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1"
            }
        )
        page = context.new_page()
        
        print("正在載入名人郵輪網頁 (Firefox)...")
        
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000) # 強制等待 8 秒
            
            page.wait_for_selector("div[data-testid^='cruise-card-']", timeout=30000)
            
        except Exception as e:
            print(f"載入或等待元素時發生錯誤: {e}")
            print("正在擷取畫面與 HTML 原始碼以供除錯...")
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
                
                # 處理連結並修復 .comitinerary 錯誤
                link_attr = card.get_attribute("data-product-view-link")
                link = link_attr if link_attr else ""
                clean_link = link.lstrip('/') # 確保不會有重複的斜線
                full_link = f"https://www.celebritycruises.com/{clean_link}" if clean_link else "無連結"

                # 利用正則表達式從網址中精準抽出天數 (例如 itinerary/11-night)
                nights = "未知天數"
                night_match = re.search(r'itinerary/(\d+)-night', link, re.IGNORECASE)
                if night_match:
                    nights = f"{night_match.group(1)} Nights"
                else:
                    nights_el = card.query_selector("span[class*='Tipper-styled__Tipper-content']")
                    nights = nights_el.inner_text().strip() if nights_el else "未知天數"
                
                # 處理主要行程，把裡面夾帶的天數資訊濾掉
                itinerary_title = "未知行程"
                title_el = card.query_selector("div[class*='RefinedCruiseCardBase'] >> xpath=../..//h2")
                if title_el:
                    itinerary_title = title_el.inner_text().strip()
                elif "itinerary/" in link:
                    raw_title = link.split("itinerary/")[1].split("-from-")[0].replace("-", " ").title()
                    # 把 "11 Night " 從主要行程字串中拿掉
                    title_match = re.search(r'^\d+\s*Nights?\s+(.*)', raw_title, re.IGNORECASE)
                    if title_match:
                        itinerary_title = title_match.group(1).strip()
                    else:
                        itinerary_title = raw_title

                cruise_data = {
                    "ship_name": ship_name,
                    "nights": nights,
                    "ports_route": ports_route,
                    "itinerary_title": itinerary_title,
                    "price": price,
                    "full_link": full_link
                }
                
                send_discord_notification(cruise_data)
                
            except Exception as card_err:
                print(f"解析卡片時發生錯誤: {card_err}")
                continue
                
        browser.close()

if __name__ == "__main__":
    parse_cruises()
