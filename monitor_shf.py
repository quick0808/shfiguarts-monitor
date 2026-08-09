# ============================================================
# 位置1：所有 import 集中放在这里
# ============================================================
import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime
import logging
from urllib.parse import urljoin
import time

# ============================================================
# 位置2：配置区域
# ============================================================
# 只监控 Moehime Japan Toys 这一个网站
SITES = [
    {
        "name": "Moehime Japan Toys",
        "url": "https://moehime-japantoys.com/product-category/figures/s-h-figuarts/",
        "item_selector": "li.product",
        "name_selector": "h2.woocommerce-loop-product__title",
        "link_selector": "a.woocommerce-LoopProduct-link",
        "id_attr": "data-product_id",
        "keyword": ""                      # 空字符串 = 该分类下所有商品都是 S.H.Figuarts，不需要过滤
    }
]

# QQ邮箱SMTP配置（SSL加密）
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = os.getenv('QQ_EMAIL')
AUTH_CODE = os.getenv('QQ_AUTH_CODE')
RECEIVER_EMAIL = "494923589@qq.com"       # 如需修改，直接改这里或改用环境变量

# 本地去重记录文件
DATA_FILE = "found_items.json"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================
# 位置3：函数定义（与之前完全相同）
# ============================================================
def load_found_items(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get("ids", []))
    return set()


def save_found_items(filepath, ids):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            "ids": list(ids),
            "last_updated": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)


def fetch_site(site_cfg, retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(retries):
        try:
            resp = requests.get(site_cfg["url"], headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select(site_cfg["item_selector"])
            if not items:
                logging.warning(f"{site_cfg['name']} 未找到商品元素，请检查选择器")
                return []

            keyword = site_cfg["keyword"].lower()
            found = []
            for item in items:
                name_tag = item.select_one(site_cfg["name_selector"])
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)

                # keyword 为空时不进行过滤，直接抓取所有商品
                if keyword and keyword not in name.lower():
                    continue

                link_tag = item.select_one(site_cfg["link_selector"])
                link = ""
                if link_tag and link_tag.get("href"):
                    link = link_tag["href"]
                    if link.startswith("/"):
                        link = urljoin(site_cfg["url"], link)

                item_id = None
                if site_cfg.get("id_attr"):
                    item_id = item.get(site_cfg["id_attr"])
                    if not item_id and item.parent:
                        item_id = item.parent.get(site_cfg["id_attr"])
                if not item_id:
                    item_id = link or name

                found.append({
                    "site": site_cfg["name"],
                    "name": name,
                    "link": link,
                    "id": str(item_id)
                })
            return found

        except Exception as e:
            logging.error(f"第 {attempt+1} 次访问 {site_cfg['name']} 失败：{e}")
            time.sleep(2)
    logging.error(f"所有 {retries} 次重试均失败，跳过 {site_cfg['name']}")
    return []


def send_notification(new_items):
    if not new_items:
        return

    subject = f"S.H.Figuarts 新品通知 - {len(new_items)} 件新商品"
    body_lines = ["发现以下新商品：\n"]
    for item in new_items:
        body_lines.append(f"网站：{item['site']}")
        body_lines.append(f"名称：{item['name']}")
        body_lines.append(f"链接：{item['link']}")
        body_lines.append("---")
    body = "\n".join(body_lines)

    html_content = f"""
    <html>
    <head><meta charset="UTF-8"></head>
    <body>
        <h2>🚀 {subject}</h2>
        <pre style="font-family: Arial, sans-serif; font-size: 14px;">{body}</pre>
        <p style="color:gray;font-size:small;">* 此邮件由自动监控脚本生成。</p>
    </body>
    </html>
    """

    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, AUTH_CODE)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        server.quit()
        logging.info("邮件发送成功！")
    except Exception as e:
        logging.error(f"邮件发送失败：{e}")


def main():
    logging.info("开始检查商品更新...")
    found_ids = load_found_items(DATA_FILE)
    new_all = []

    for site in SITES:
        items = fetch_site(site)
        for item in items:
            if item["id"] not in found_ids:
                found_ids.add(item["id"])
                new_all.append(item)

    if new_all:
        logging.info(f"发现 {len(new_all)} 件新商品，正在发送邮件...")
        send_notification(new_all)
        save_found_items(DATA_FILE, found_ids)
    else:
        logging.info("没有新商品")


if __name__ == "__main__":
    main()
