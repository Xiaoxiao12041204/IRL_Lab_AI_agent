import os, sys, json, io, time, urllib.parse
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
THESIS_INDEX_PATH = os.path.join(CURRENT_DIR, 'thesis_index.json')
ENV_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', '.env'))

# 需要重新抓取真實論文題目的成員清單（附預設搜尋關鍵字）
NEED_FIX = {
    "童彥諴":  "車用",     # 車用網路/VANET
    "楊舒智":  "車用",
    "陳奕燁":  "車用",
    "黃仁襄":  "車用",
    "林庭陽":  "射頻",
    "徐睿誌":  "LTE",
    "呂映萱":  "UB",
    "王駿程":  "M2M",
    "陳家豪":  "論文",
    "張浚暢":  "定稿",
    "周家仲":  "周家仲",
    "林威翰":  "論文",
}

BAD_TITLE_MARKERS = [
    "A Thesis", "College of", "Yuan Ze", "改版", "完稿",
    "自動儲存", "投影片_", "s111461", "定稿", "UBLAA_",
    "威翻", "威翰PPT", "周家仲論", ".pdf"
]

def is_bad_title(title):
    for m in BAD_TITLE_MARKERS:
        if m in title:
            return True
    return len(title) < 5

def get_nas_credentials():
    env_vars = dotenv_values(ENV_PATH)
    host = env_vars.get('NAS_HOST', 'https://yzuirl.synology.me:5001')
    if not host.startswith('http'):
        host = 'https://' + host
    return host, env_vars.get('NAS_USERNAME', '蕭宇傑'), env_vars.get('NAS_PASSWORD', 'Xiao921204@')

def extract_title_from_text(text, author):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    bad_words = ["元智大學", "College", "Yuan Ze", "Engineering", "Department",
                 "碩士論文", "碩士學位", "審定書", "書名頁", "摘要", "研究生",
                 "指導教授", "A Thesis", "Submitted"]
    
    # 1. 碩士論文關鍵字後面找題目
    for i, line in enumerate(lines[:40]):
        cl = line.replace(" ", "")
        if "碩士論文" in cl or "碩士學位論文" in cl:
            for j in range(i+1, min(i+8, len(lines))):
                cand = lines[j].strip()
                if not any(bw in cand for bw in bad_words) and len(cand) >= 5 and cand != author:
                    if not all(c.isascii() for c in cand):  # 優先中文題目
                        return cand
    
    # 2. 找第一行中文長字串
    for line in lines[:20]:
        if len(line) >= 8 and not any(bw in line for bw in bad_words) and not line.startswith(("A ", "The ")):
            if not all(c.isascii() for c in line.replace(' ', '')):
                return line
    
    return ""

def run_fix():
    host, username, password = get_nas_credentials()
    
    with open(THESIS_INDEX_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 找出需要修正的項目
    to_fix = {}
    for item in data:
        author = item['author']
        title = item.get('title', '')
        if author in NEED_FIX and is_bad_title(title):
            to_fix[author] = item
    
    if not to_fix:
        print("[+] 所有標題均正常，無需修正！")
        return

    print(f"[*] 需要修正的筆數: {len(to_fix)} 筆: {list(to_fix.keys())}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        page = context.new_page()
        
        print(f"[*] 登入 NAS: {host} ...", flush=True)
        page.goto(host, wait_until="domcontentloaded", timeout=35000)
        time.sleep(3)
        user_input = page.locator("input:visible").first
        user_input.fill(username)
        user_input.press("Enter")
        time.sleep(2)
        pwd_input = page.locator("input[type='password']:visible, input:visible").last
        pwd_input.fill(password)
        pwd_input.press("Enter")
        time.sleep(6)

        for author, item in to_fix.items():
            target_path = item['nas_path']
            print(f"\n=== 修正: {author} ({target_path}) ===", flush=True)
            
            # 嘗試幾個子資料夾關鍵字
            subfolders_to_try = [target_path]
            
            # 先看主目錄
            encoded = urllib.parse.quote(target_path)
            fs_url = f"{host}/index.cgi?launchApp=SYNO.SDS.App.FileStation3.Instance&launchParam=openfile%3D{encoded}"
            page.goto(fs_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            
            rows = page.locator(".x-grid3-row").all()
            items_found = [r.inner_text().strip().replace('\n', ' | ') for r in rows if r.inner_text().strip()]
            print(f"  主目錄: {items_found[:5]}", flush=True)
            
            # 找子目錄（論文相關）
            for item_text in items_found:
                fname = item_text.split(" | ")[0].strip()
                if "Folder" in item_text and any(w in fname for w in ["論文", "口試", "全文", "文件"]):
                    subfolders_to_try.append(f"{target_path}{fname}/")
            
            best_title = ""
            for try_path in subfolders_to_try:
                if best_title:
                    break
                if try_path != target_path:
                    enc2 = urllib.parse.quote(try_path)
                    url2 = f"{host}/index.cgi?launchApp=SYNO.SDS.App.FileStation3.Instance&launchParam=openfile%3D{enc2}"
                    page.goto(url2, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(4)
                    rows = page.locator(".x-grid3-row").all()
                    items_found = [r.inner_text().strip().replace('\n', ' | ') for r in rows if r.inner_text().strip()]
                    print(f"  子目錄 {try_path}: {items_found[:5]}", flush=True)
                
                for i, item_text in enumerate(items_found):
                    fname = item_text.split(" | ")[0].strip()
                    if fname.startswith("~$") or fname.endswith(".db"):
                        continue
                    
                    # 先試著從檔名判斷
                    import re
                    clean_name = re.sub(r'\.(docx|doc|pdf|pptx)$', '', fname, flags=re.I).strip()
                    clean_name = clean_name.replace(author, "").strip(" _-()")
                    if len(clean_name) >= 8 and not is_bad_title(clean_name):
                        best_title = clean_name
                        print(f"  從檔名推斷題目: {best_title}", flush=True)
                        break
                    
                    # 嘗試下載 DOCX/PDF 解析
                    if not best_title and fname.lower().endswith((".docx", ".pdf")) and not fname.startswith("~$"):
                        print(f"  下載解析: {fname} ...", flush=True)
                        try:
                            target_row = rows[i]
                            with page.expect_download(timeout=12000) as dl_info:
                                target_row.click(button='right')
                                time.sleep(0.8)
                                dl_btn = page.locator(".x-menu:visible .x-menu-item:has-text('Download'), .x-menu:visible a:has-text('Download')").first
                                if dl_btn.is_visible():
                                    dl_btn.click(force=True)
                                else:
                                    page.locator("button:has-text('Action'), .x-btn:has-text('Action')").first.click()
                                    time.sleep(0.5)
                                    page.locator(".x-menu:visible .x-menu-item:has-text('Download')").first.click(force=True)
                            
                            dl_path = dl_info.value.path()
                            with open(dl_path, 'rb') as fh:
                                raw = fh.read()
                            
                            import io
                            stream = io.BytesIO(raw)
                            if fname.lower().endswith(".docx"):
                                import docx as docx_lib
                                doc = docx_lib.Document(stream)
                                text = "\n".join([p.text for p in doc.paragraphs[:40]])
                            else:
                                from pypdf import PdfReader
                                reader = PdfReader(stream)
                                text = "\n".join([p.extract_text() or "" for p in reader.pages[:4]])
                            
                            title = extract_title_from_text(text, author)
                            if title and not is_bad_title(title):
                                best_title = title
                                print(f"  從文字解析題目: {best_title}", flush=True)
                        except Exception as e:
                            print(f"  [!] 解析失敗: {e}", flush=True)
            
            if best_title:
                # 更新 data
                for d in data:
                    if d['author'] == author:
                        d['title'] = best_title
                        print(f"[+] 更新 {author} 題目 -> 《{best_title}》", flush=True)
                        break
                
                with open(THESIS_INDEX_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                print(f"[-] {author}: 無法取得更好的題目，保留現有", flush=True)

        browser.close()
    
    print("\n🎉 標題修正完畢！", flush=True)

if __name__ == "__main__":
    run_fix()
