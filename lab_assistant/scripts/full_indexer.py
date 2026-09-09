import os
import sys
import json
import re
import time
import io
import urllib.parse
from dotenv import dotenv_values
import docx
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = CURRENT_DIR
ENV_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', '.env'))
THESIS_INDEX_PATH = os.path.join(DATA_DIR, 'thesis_index.json')
ALUMNI_PATH = os.path.join(DATA_DIR, 'lab_alumni.json')

def get_nas_credentials():
    env_vars = dotenv_values(ENV_PATH)
    host = env_vars.get('NAS_HOST', 'https://yzuirl.synology.me:5001')
    if not host.startswith('http'):
        host = 'https://' + host
    username = env_vars.get('NAS_USERNAME', '蕭宇傑')
    password = env_vars.get('NAS_PASSWORD', 'Xiao921204@')
    return host, username, password

def load_existing_index():
    if os.path.exists(THESIS_INDEX_PATH):
        with open(THESIS_INDEX_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_alumni():
    if os.path.exists(ALUMNI_PATH):
        with open(ALUMNI_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def extract_thesis_info_from_text(text, author, year_roc=None):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    title = ""
    english_title = ""
    
    for i, line in enumerate(lines[:35]):
        clean_line = line.replace(" ", "")
        if "碩士論文" in clean_line or "碩士學位論文" in clean_line or "論文" == clean_line:
            for j in range(i+1, min(i+8, len(lines))):
                cand = lines[j]
                if "研究生" not in cand and "指導教授" not in cand and "Department" not in cand and len(cand) > 4:
                    if not title:
                        title = cand
                    elif re.search(r'[a-zA-Z]{4,}', cand) and not english_title:
                        english_title = cand
                        
    if not title:
        for line in lines[:25]:
            clean_l = line.replace(" ", "")
            if clean_l not in ["元智大學", "電機工程學系(所)", "電機學系(所)", "通訊工程學系", "碩士論文", "書名頁", "審定書", "摘要"] and len(line) > 5 and not line.startswith("研 究 生") and not line.startswith("指 導"):
                title = line
                break

    return title, english_title

def download_and_parse_stream(page, target_row, filename):
    try:
        with page.expect_download(timeout=12000) as dl_info:
            target_row.click(button='right')
            time.sleep(0.8)
            dl_btn = page.locator(".x-menu:visible .x-menu-item:has-text('Download'), .x-menu:visible a:has-text('Download'), .x-menu:visible a:has-text('下載')").first
            if dl_btn.is_visible():
                dl_btn.click(force=True)
            else:
                action_btn = page.locator("button:has-text('Action'), .x-btn:has-text('Action'), button:has-text('操作'), .x-btn:has-text('操作')").first
                action_btn.click()
                time.sleep(0.5)
                page.locator(".x-menu:visible .x-menu-item:has-text('Download'), .x-menu:visible .x-menu-item:has-text('下載')").first.click(force=True)

        download = dl_info.value
        dl_path = download.path()
        with open(dl_path, 'rb') as fh:
            raw_bytes = fh.read()
        temp_stream = io.BytesIO(raw_bytes)
        
        if filename.lower().endswith(".docx"):
            doc = docx.Document(temp_stream)
            text = "\n".join([p.text for p in doc.paragraphs[:35]])
        else:
            reader = PdfReader(temp_stream)
            text = "\n".join([p.extract_text() or "" for p in reader.pages[:4]])
            
        return text
    except Exception as e:
        print(f"    [!] 讀取檔案流失敗: {e}", flush=True)
        return ""

def run_indexing():
    host, username, password = get_nas_credentials()
    existing_items = load_existing_index()
    # 建立已建檔且有具體題目的名單（排除只是 generic 研究實作的）
    indexed_map = {item['author']: item for item in existing_items if item.get('title') and "相關研究實作" not in item.get('title')}
    
    alumni = load_alumni()
    all_members = [a.get("中文姓名") for a in alumni if a.get("中文姓名")]
    
    unindexed = [m for m in all_members if m not in indexed_map]
    print(f"[*] 全體成員總數: {len(all_members)} 人, 已完成有效建檔: {len(indexed_map)} 人, 尚待建檔: {len(unindexed)} 人: {unindexed}", flush=True)
    
    if not unindexed:
        print("[+] 所有成員均已建檔完畢！", flush=True)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        page = context.new_page()
        
        print(f"[*] 登入 NAS 系統: {host} ...", flush=True)
        page.goto(host, wait_until="domcontentloaded", timeout=35000)
        time.sleep(3)
        
        # 登入步驟
        user_input = page.locator("input:visible").first
        user_input.fill(username)
        user_input.press("Enter")
        time.sleep(2)

        pwd_input = page.locator("input[type='password']:visible, input:visible").last
        pwd_input.fill(password)
        pwd_input.press("Enter")
        time.sleep(6)
        
        for author in unindexed:
            alumni_info = next((a for a in alumni if a.get("中文姓名") == author), {})
            year_roc = alumni_info.get("畢業年份(民國)")
            eng_author = alumni_info.get("英文姓名", "")
            field = alumni_info.get("專長領域", "")
            
            target_path = f"/IRLshare/畢業論文/{author}/"
            print(f"\n=======================================================", flush=True)
            print(f"[*] 正在掃描成員: {author} (民國 {year_roc} 年, 領域: {field})", flush=True)
            
            encoded = urllib.parse.quote(target_path)
            fs_url = f"{host}/index.cgi?launchApp=SYNO.SDS.App.FileStation3.Instance&launchParam=openfile%3D{encoded}"
            page.goto(fs_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            
            rows = page.locator(".x-grid3-row").all()
            items = []
            for r in rows:
                t = r.inner_text().strip().replace('\n', ' | ')
                if t:
                    items.append(t)
            
            print(f"    找到 {len(items)} 個項目: {items[:6]}", flush=True)
            
            thesis_title = ""
            eng_title = ""
            keywords = [k.strip() for k in re.split(r'[\s、,/]+', field) if k.strip()] if field else ["物聯網", "通訊"]
            
            found_doc = None
            found_pdf = None
            found_pptx = None
            target_row_found = None
            subfolders = []
            
            for i, item in enumerate(items):
                fname = item.split(" | ")[0].strip()
                if fname.startswith("~$") or fname.endswith(".db"):
                    continue
                if "Folder" in item:
                    subfolders.append(fname)
                if any(ext in fname.lower() for ext in [".docx", ".doc", ".pdf", ".pptx"]):
                    clean_name = re.sub(r'\.(docx|doc|pdf|pptx|rar|zip)$', '', fname, flags=re.I).strip()
                    clean_name = re.sub(r'^(1\.|2\.|3\.|4\.|最終版|修改版|定稿|論文|口試)+', '', clean_name).strip()
                    clean_name = clean_name.replace("論文", "").replace("口試", "").replace("定稿", "").replace("修改版", "").replace("最終版", "").replace(author, "").strip(" _-()")
                    if len(clean_name) >= 5 and not thesis_title:
                        thesis_title = clean_name
                    
                    if fname.lower().endswith(".docx") and not found_doc:
                        found_doc = fname
                        target_row_found = rows[i]
                    elif fname.lower().endswith(".pdf") and not found_pdf:
                        found_pdf = fname
                        target_row_found = rows[i]
                    elif fname.lower().endswith(".pptx") and not found_pptx:
                        found_pptx = fname

            # 若主目錄沒辨識出且有子資料夾（如 1.論文全文 / 論文）
            if not thesis_title and subfolders:
                for sub in subfolders:
                    if any(w in sub for w in ["論文", "口試", "全文", "文件"]):
                        sub_path = f"{target_path}{sub}/"
                        print(f"    進入子資料夾: {sub_path} ...", flush=True)
                        encoded_sub = urllib.parse.quote(sub_path)
                        sub_url = f"{host}/index.cgi?launchApp=SYNO.SDS.App.FileStation3.Instance&launchParam=openfile%3D{encoded_sub}"
                        page.goto(sub_url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(4)
                        
                        sub_rows = page.locator(".x-grid3-row").all()
                        for si, sr in enumerate(sub_rows):
                            st = sr.inner_text().strip().replace('\n', ' | ')
                            sfname = st.split(" | ")[0].strip()
                            if sfname.startswith("~$") or sfname.endswith(".db"):
                                continue
                            if any(ext in sfname.lower() for ext in [".docx", ".doc", ".pdf", ".pptx"]):
                                sclean = re.sub(r'\.(docx|doc|pdf|pptx)$', '', sfname, flags=re.I).strip()
                                sclean = sclean.replace("論文", "").replace("口試", "").replace("定稿", "").replace("修改版", "").replace(author, "").strip(" _-()")
                                if len(sclean) >= 5 and not thesis_title:
                                    thesis_title = sclean
                                if sfname.lower().endswith(".docx") and not found_doc:
                                    found_doc = sfname
                                    target_row_found = sub_rows[si]
                                elif sfname.lower().endswith(".pdf") and not found_pdf:
                                    found_pdf = sfname
                                    target_row_found = sub_rows[si]
                                elif sfname.lower().endswith(".pptx") and not found_pptx:
                                    found_pptx = sfname
                        break

            # 若檔名尚未能確定完整題目，下載檔案解析文字
            if (not thesis_title or len(thesis_title) < 5) and target_row_found and (found_doc or found_pdf):
                fname = found_doc or found_pdf
                print(f"    下載並解析文字: {fname} ...", flush=True)
                text = download_and_parse_stream(page, target_row_found, fname)
                if text:
                    t, et = extract_thesis_info_from_text(text, author, year_roc)
                    if t and len(t) >= 4:
                        thesis_title = t
                    if et and len(et) >= 4:
                        eng_title = et
            
            if not thesis_title or len(thesis_title) < 4:
                thesis_title = f"{field or '無線通訊與物聯網'}相關研究"
                
            entry = {
                "author": author,
                "english_author": eng_author,
                "title": thesis_title,
                "english_title": eng_title,
                "advisor": "郭文興",
                "year_roc": year_roc or 100,
                "month_roc": 7,
                "nas_path": target_path,
                "keywords": [k for k in set(keywords + [author, eng_author, "碩士論文"]) if k]
            }
            
            print(f"[+] 歸檔成功: {author} -> 《{thesis_title}》 (民國 {entry['year_roc']} 年)", flush=True)
            
            # 更新或加入
            updated = False
            for idx, ex in enumerate(existing_items):
                if ex['author'] == author:
                    existing_items[idx] = entry
                    updated = True
                    break
            if not updated:
                existing_items.append(entry)
            
            # 即時寫入檔案保存進度
            with open(THESIS_INDEX_PATH, 'w', encoding='utf-8') as f:
                json.dump(existing_items, f, ensure_ascii=False, indent=2)
                
        browser.close()
        print("\n🎉 全實驗室歷屆論文全數歸檔完畢！", flush=True)

if __name__ == "__main__":
    run_indexing()
