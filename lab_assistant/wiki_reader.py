"""
Synology MediaWiki 實驗室維基知識庫檢索模組 (MediaWiki API Service)
支援即時全文檢索、章節精準擷取、Wikitext 清洗、同音字/模糊比對，以及自動認證連線。
Wiki 站台：https://yzuirl.synology.me/mediawiki/
"""

import os
import sys
import re
import json
import time
import requests
import urllib3
import difflib
from dotenv import dotenv_values

urllib3.disable_warnings()

try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(CURRENT_DIR, '.env')
WIKI_CACHE_PATH = os.path.join(CURRENT_DIR, 'data', 'wiki_knowledge.json')
WIKI_API_URL = "https://yzuirl.synology.me/mediawiki/api.php"

# 快取 Wiki Session
_WIKI_SESSION = {"session": None, "expires": 0}

def get_wiki_session():
    """取得 MediaWiki Session，快取 15 分鐘，支援自動重試防逾時"""
    global _WIKI_SESSION
    now = time.time()
    if _WIKI_SESSION["session"] and now < _WIKI_SESSION["expires"]:
        return _WIKI_SESSION["session"]

    session = requests.Session()
    from urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    env = dotenv_values(ENV_PATH)
    user = env.get("NAS_USERNAME", "蕭宇傑")
    pwd = env.get("NAS_PASSWORD", "Xiao921204@")

    try:
        # 嘗試取得 login token 並登入
        r_token = session.get(WIKI_API_URL, params={
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json"
        }, verify=False, timeout=8).json()
        token = r_token.get("query", {}).get("tokens", {}).get("logintoken")

        if token:
            session.post(WIKI_API_URL, data={
                "action": "login",
                "lgname": user,
                "lgpassword": pwd,
                "lgtoken": token,
                "format": "json"
            }, verify=False, timeout=8)
    except Exception:
        pass

    _WIKI_SESSION = {"session": session, "expires": now + 900}
    return session

def clean_wikitext(text):
    """將 MediaWiki 語法清洗為乾淨、易讀的繁體中文純文字"""
    if not text:
        return ""
    
    # 1. 移除註解 <!-- ... -->
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # 2. 處理內部連結 [[Link|Text]] -> Text, [[Link]] -> Link
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
    
    # 3. 處理外部連結 [http://... Text] -> Text (http://...), [http://...] -> http://...
    text = re.sub(r'\[(https?://[^\s\]]+)\s+([^\]]+)\]', r'\2 (\1)', text)
    text = re.sub(r'\[(https?://[^\s\]]+)\]', r'\1', text)
    
    # 4. 清理粗體與斜體 '''bold''' -> bold, ''italic'' -> italic
    text = re.sub(r"'{2,5}", '', text)
    
    # 5. 清理 HTML 標籤
    text = re.sub(r'<[^>]+>', '', text)
    
    # 6. 清理多餘的連續空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def extract_wiki_sections(wikitext):
    """將 Wikitext 依據 == 標題 == 分割成章節結構清單"""
    lines = wikitext.split('\n')
    sections = []
    current_title = "前言與簡介"
    current_level = 1
    current_lines = []
    
    header_pattern = re.compile(r'^(={1,5})\s*(.*?)\s*\1$')
    
    for line in lines:
        m = header_pattern.match(line.strip())
        if m:
            if current_lines:
                sections.append({
                    "title": current_title,
                    "level": current_level,
                    "raw_content": '\n'.join(current_lines),
                    "clean_content": clean_wikitext('\n'.join(current_lines))
                })
                current_lines = []
            current_level = len(m.group(1))
            current_title = m.group(2).strip()
        else:
            current_lines.append(line)
            
    if current_lines:
        sections.append({
            "title": current_title,
            "level": current_level,
            "raw_content": '\n'.join(current_lines),
            "clean_content": clean_wikitext('\n'.join(current_lines))
        })
        
    return sections

def get_section_content(wikitext, keyword=""):
    """
    從頁面內容中精準定位並擷取與關鍵字相符的特定章節
    """
    if not keyword:
        return clean_wikitext(wikitext)
        
    sections = extract_wiki_sections(wikitext)
    kw = keyword.strip().lower()
    
    # 1. 精確與無空格標題比對
    kw_nospace = kw.replace(' ', '')
    matched_sections = [s for s in sections if kw in s["title"].lower() or kw_nospace in s["title"].lower().replace(' ', '')]
    
    # 2. 若標題未命中，比對章節內容
    if not matched_sections:
        matched_sections = [s for s in sections if kw in s["raw_content"].lower() or kw_nospace in s["raw_content"].lower().replace(' ', '')]
        
    if matched_sections:
        output_parts = []
        for s in matched_sections:
            output_parts.append(f"【{s['title']}】\n{s['clean_content']}")
        return '\n\n'.join(output_parts)
        
    return clean_wikitext(wikitext)

def wiki_list_pages():
    """列出 MediaWiki 內的所有頁面"""
    session = get_wiki_session()
    try:
        r = session.get(WIKI_API_URL, params={
            "action": "query",
            "list": "allpages",
            "aplimit": "100",
            "format": "json"
        }, verify=False, timeout=10).json()
        pages = r.get("query", {}).get("allpages", [])
        return [p["title"] for p in pages]
    except Exception:
        # Fallback to local cache if offline
        if os.path.exists(WIKI_CACHE_PATH):
            with open(WIKI_CACHE_PATH, "r", encoding="utf-8") as f:
                return list(json.load(f).keys())
        return []

def wiki_get_page(title):
    """取得指定頁面的內容、純文字與章節結構"""
    session = get_wiki_session()
    try:
        r = session.get(WIKI_API_URL, params={
            "action": "parse",
            "page": title,
            "prop": "wikitext|text",
            "format": "json"
        }, verify=False, timeout=10).json()
        if "parse" in r:
            wikitext = r["parse"].get("wikitext", {}).get("*", "")
            return {
                "status": "success",
                "title": title,
                "content": wikitext,
                "clean_content": clean_wikitext(wikitext),
                "sections": extract_wiki_sections(wikitext)
            }
        elif "error" in r:
            return {"status": "error", "message": r["error"].get("info", "Page not found")}
    except Exception:
        pass

    # Fallback to local cache
    if os.path.exists(WIKI_CACHE_PATH):
        try:
            with open(WIKI_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if title in data:
                    raw = data[title]
                    return {
                        "status": "success",
                        "title": title,
                        "content": raw,
                        "clean_content": clean_wikitext(raw),
                        "sections": extract_wiki_sections(raw)
                    }
        except Exception:
            pass

    return {"status": "error", "message": f"無法取得頁面 {title}"}

def wiki_search(query):
    """
    智慧搜尋 MediaWiki 知識庫：支援標題比對、內文全文檢索、章節精準擷取與同音字模糊匹配
    """
    query = query.strip()
    if not query:
        return {"status": "error", "message": "搜尋關鍵字為空"}

    session = get_wiki_session()
    search_results = []
    
    # 1. 優先使用 MediaWiki API 進行全文檢索
    try:
        r = session.get(WIKI_API_URL, params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": "10",
            "format": "json"
        }, verify=False, timeout=10).json()
        raw_hits = r.get("query", {}).get("search", [])
        for hit in raw_hits:
            search_results.append({
                "title": hit["title"],
                "snippet": clean_wikitext(hit.get("snippet", ""))
            })
    except Exception:
        pass

    # 2. 本地知識庫快取全文比對與同音字/錯字模糊比對
    cached_hits = []
    q_pinyin = "".join(lazy_pinyin(query)) if lazy_pinyin else ""

    if os.path.exists(WIKI_CACHE_PATH):
        try:
            with open(WIKI_CACHE_PATH, "r", encoding="utf-8") as f:
                wiki_data = json.load(f)
                
                q_nospace = query.lower().replace(' ', '')
                for t, content in wiki_data.items():
                    t_clean = t.lower().replace(' ', '')
                    c_clean = content.lower().replace(' ', '')
                    if q_nospace in t_clean or q_nospace in c_clean or query.lower() in t.lower() or query.lower() in content.lower():
                        if not any(h["title"] == t for h in search_results):
                            idx = content.lower().find(query.lower()) if query.lower() in content.lower() else 0
                            start = max(0, idx - 40)
                            end = min(len(content), idx + 100)
                            snip = clean_wikitext(content[start:end])
                            cached_hits.append({"title": t, "snippet": f"...{snip}...", "score": 1.0})

                if not search_results and not cached_hits:
                    for t, content in wiki_data.items():
                        t_pinyin = "".join(lazy_pinyin(t)) if lazy_pinyin else ""
                        ratio = difflib.SequenceMatcher(None, query.lower(), t.lower()).ratio()
                        pinyin_match = bool(q_pinyin and t_pinyin and (q_pinyin in t_pinyin or t_pinyin in q_pinyin))
                        
                        if pinyin_match or ratio >= 0.4:
                            score = 0.9 if pinyin_match else ratio
                            cached_hits.append({
                                "title": t,
                                "snippet": f"（同音/錯字辨識：{query} -> {t}）\n{clean_wikitext(content[:120])}...",
                                "score": score
                            })
        except Exception:
            pass

    cached_hits.sort(key=lambda x: x.get("score", 0), reverse=True)
    combined_hits = search_results + [{"title": h["title"], "snippet": h["snippet"]} for h in cached_hits]

    # 精準擷取頂部命中頁面之對應章節
    exact_content = None
    matched_section_text = None
    if combined_hits:
        top_title = combined_hits[0]["title"]
        page_res = wiki_get_page(top_title)
        if page_res.get("status") == "success":
            raw_text = page_res["content"]
            exact_content = page_res["clean_content"]
            matched_section_text = get_section_content(raw_text, query)

    return {
        "status": "success",
        "query": query,
        "count": len(combined_hits),
        "results": combined_hits,
        "matched_section": matched_section_text or exact_content,
        "top_content": exact_content
    }

def sync_wiki_cache():
    """同步 MediaWiki 全部頁面到本地快取 data/wiki_knowledge.json"""
    session = get_wiki_session()
    try:
        pages = wiki_list_pages()
        db = {}
        for p in pages:
            res = wiki_get_page(p)
            if res.get("status") == "success":
                db[p] = res["content"]
        os.makedirs(os.path.dirname(WIKI_CACHE_PATH), exist_ok=True)
        with open(WIKI_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        return {"status": "success", "count": len(db), "pages": list(db.keys())}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python wiki_reader.py list | get <標題> | search <關鍵字> | sync")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "list":
        print(json.dumps(wiki_list_pages(), ensure_ascii=False, indent=2))
    elif cmd == "get":
        title = sys.argv[2] if len(sys.argv) > 2 else "首頁"
        res = wiki_get_page(title)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif cmd == "search":
        q = sys.argv[2] if len(sys.argv) > 2 else "報帳"
        res = wiki_search(q)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif cmd == "sync":
        res = sync_wiki_cache()
        print(json.dumps(res, ensure_ascii=False, indent=2))
