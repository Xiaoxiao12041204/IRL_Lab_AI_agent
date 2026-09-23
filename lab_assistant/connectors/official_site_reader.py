"""
IRL 實驗室官方網站即時檢索模組 (Official Website Reader)
支援即時連線抓取、解析 https://irl.ee.yzu.edu.tw/ 之 7 大單元內容：
1. Introduction 實驗室簡介
2. Advisor 指導教授
3. Member 成員名冊
4. Alumni 校友
5. Cooperation 產學合作與實績
6. Contact Us 聯絡方式
7. Recruits 誠徵新成員
"""

import os
import sys
import re
import json
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_BASE_URL = "https://irl.ee.yzu.edu.tw"

PAGE_ROUTES = {
    "intro": "/introduction-%E5%AF%A6%E9%A9%97%E5%AE%A4%E7%B0%A1%E4%BB%8B",
    "advisor": "/advisor-%E6%8C%87%E5%B0%8E%E6%95%99%E6%8E%88",
    "member": "/member-%E6%88%90%E5%93%A1",
    "alumni": "/alumni-%E6%A0%A1%E5%8F%8B",
    "cooperation": "/cooperation-%E7%94%A2%E5%AD%B8%E5%90%88%E4%BD%9C",
    "contact": "/contact-us-%E8%81%AF%E7%B5%A1%E6%96%B9%E5%BC%8F",
    "recruits": "/recruits-%E8%AA%A0%E5%BE%B5%E6%96%B0%E6%88%90%E5%93%A1"
}

_SITE_CACHE = {}
_CACHE_EXPIRES = 0
CACHE_TTL = 12 * 3600  # 12 小時快取

def _get_page_content(route):
    url = f"{SITE_BASE_URL}{route}"
    try:
        r = requests.get(url, verify=False, timeout=10)
        r.encoding = 'utf-8'
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # 移除導覽列與頁尾重複雜訊
            for nav in soup.find_all(['nav', 'header', 'footer']):
                nav.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text
    except Exception as e:
        return f"連線至官網頁面失敗: {e}"
    return ""

def _get_active_workstation_users_text():
    possible_paths = [
        os.path.join(CURRENT_DIR, "data", "lab_properties.json"),
        os.path.join(CURRENT_DIR, "..", "lab_assistant", "data", "lab_properties.json"),
        os.path.join(CURRENT_DIR, "lab_assistant", "data", "lab_properties.json"),
        "/home/openclaw/irl_lab/lab_assistant/data/lab_properties.json"
    ]
    prop_path = next((p for p in possible_paths if os.path.exists(p)), None)
    if not prop_path:
        return ""
    try:
        with open(prop_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = []
        for item in data:
            user = item.get("使用者")
            status = item.get("設備狀態")
            if user and status == "使用中" and "公用" not in str(user):
                user_str = str(user).strip()
                ip = item.get("網路IP")
                ip_display = f"IP: {int(ip)}" if isinstance(ip, (int, float)) and not str(ip).endswith(".5") else (f"IP: {ip}" if ip else "")
                role = "智慧系統與 AI 助理開發者" if user_str == "蕭宇傑" else ("研究助理" if user_str == "邱子倫" else "碩士班研究生")
                users.append(f"* {user_str} ➔ 身分：{role}，70640 實驗室主機使用中 ({ip_display})")
        if users:
            return "\n\n【實驗室現役使用中工作站成員名冊（含系統開發者與全體在學成員）】：\n" + "\n".join(users)
    except Exception:
        pass
    return ""

def fetch_all_pages(force=False):
    global _SITE_CACHE, _CACHE_EXPIRES
    now = time.time()
    if not force and _SITE_CACHE and now < _CACHE_EXPIRES:
        return _SITE_CACHE

    results = {}
    for key, route in PAGE_ROUTES.items():
        content = _get_page_content(route)
        if key == "member":
            extra_users = _get_active_workstation_users_text()
            if extra_users:
                content = (content or "") + extra_users
        results[key] = {
            "url": f"{SITE_BASE_URL}{route}",
            "content": content
        }
    _SITE_CACHE = results
    _CACHE_EXPIRES = now + CACHE_TTL
    return _SITE_CACHE

def query_official_site(keyword=""):
    """
    依關鍵字查詢官網 7 大單元內容，無關鍵字時回傳全站概覽
    """
    data = fetch_all_pages()
    if not keyword:
        return {
            "status": "success",
            "source": SITE_BASE_URL,
            "pages": list(PAGE_ROUTES.keys()),
            "data": data,
            "suggestions": [
                "查詢實驗室核心研究方向與簡介 (intro)",
                "查詢指導教授學經歷、得獎與專利 (advisor)",
                "查詢產學合作實績與知名案例 (cooperation)",
                "查詢現役研究生與研究主題 (member)",
                "查詢誠徵新成員與實驗室福利 (recruits)"
            ]
        }

    kw = keyword.strip().lower()
    matched_pages = {}
    for key, page_info in data.items():
        c = page_info.get("content", "")
        if kw in key or kw in c.lower():
            matched_pages[key] = page_info

    # 智慧對應別名
    if not matched_pages:
        alias_map = {
            "簡介": "intro", "介紹": "intro", "方向": "intro", "研究": "intro",
            "教授": "advisor", "老師": "advisor", "郭文興": "advisor", "學歷": "advisor", "專利": "advisor", "獎項": "advisor",
            "成員": "member", "研究生": "member", "助理": "member", "學生": "member",
            "校友": "alumni", "畢業": "alumni",
            "產學": "cooperation", "實績": "cooperation", "合作": "cooperation", "桃機": "cooperation", "無人機": "cooperation", "line": "cooperation",
            "聯絡": "contact", "電話": "contact", "email": "contact", "信箱": "contact", "位置": "contact", "地址": "contact",
            "誠徵": "recruits", "招募": "recruits", "加入": "recruits", "助學金": "recruits", "福利": "recruits", "出勤": "recruits"
        }
        for alias, page_key in alias_map.items():
            if alias in kw and page_key in data:
                matched_pages[page_key] = data[page_key]

    return {
        "status": "success",
        "keyword": keyword,
        "source": SITE_BASE_URL,
        "matched_count": len(matched_pages),
        "results": matched_pages if matched_pages else data,
        "suggestions": [
            "查看實驗室官網全部 7 大主題完整資訊",
            "連線 MediaWiki 查詢實驗室公用經費與日常規範",
            "檢索 NAS 歷屆畢業論文全文與口試投影片"
        ]
    }

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    res = query_official_site(kw)
    print(json.dumps(res, ensure_ascii=False, indent=2))
