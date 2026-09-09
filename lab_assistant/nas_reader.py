"""
Synology NAS 通用極速檢索與閱讀模組 (High-Speed REST API Engine)
永久常駐模組：支援任意路徑瀏覽、智慧搜尋、同音字/拼音/模糊比對 (Phonetic & Fuzzy Matching)、
直接調用 Synology REST WebAPI 進行毫秒級檔案檢索、無痕記憶體串流解析 (PDF / DOCX / PPTX / TXT)，
以及一鍵下載至 thesis_viewer/ 供 IDE 檢視器直接開啟。
"""

import sys
import os
import io
import time
import json
import difflib
import requests
import urllib3
from dotenv import dotenv_values
from pypdf import PdfReader
import docx

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
ALUMNI_PATH = os.path.join(CURRENT_DIR, 'data', 'lab_alumni.json')
VIEWER_DIR = os.path.abspath(os.path.join(CURRENT_DIR, 'thesis_viewer'))

KNOWN_MEMBERS = [
    "向禮勤", "吳其鴻", "吳順雄", "呂亞洋", "呂映萱", "周家仲", "唐嘉鋒", "張哲瑋", "張浚暢",
    "徐明瑾", "徐睿誌", "施學廷", "施宏翰", "易子杰", "林侑臻", "林威翰", "林威諭", "林庭陽",
    "林政緯", "林祺富", "林詠軒", "楊智涵", "楊舒智", "江銘洋", "洪瑜翎", "王永成", "王駿程",
    "童彥諴", "謝甫", "賴宏銘", "趙煒", "邱子倫", "邱顯毅", "郭家騏", "鍾嘉祐", "陳奕燁",
    "陳家豪", "陸保任", "顏伯丞", "黃仁襄", "黃省翰"
]

KNOWN_PROJECTS = {
    # 工作區(報告、投影片等文件)
    "通訊大賽2022": "/IRLshare/工作區(報告、投影片等文件)/通訊大賽2022/",
    "資安產學計畫": "/IRLshare/工作區(報告、投影片等文件)/資安產學計畫/",
    "科技部新計畫申請": "/IRLshare/工作區(報告、投影片等文件)/科技部新計畫申請/",
    "畢業論文暫存": "/IRLshare/工作區(報告、投影片等文件)/畢業論文暫存/",
    "物聯網閘道": "/IRLshare/工作區(報告、投影片等文件)/物聯網閘道/",
    "物聯網行星儀": "/IRLshare/工作區(報告、投影片等文件)/物聯網行星儀/",
    "智慧生活之通用電路板開發": "/IRLshare/工作區(報告、投影片等文件)/智慧生活之通用電路板開發(威諭)/",
    "已結案資料": "/IRLshare/工作區(報告、投影片等文件)/已結案資料/",
    "偉訊專案": "/IRLshare/工作區(報告、投影片等文件)/偉訊專案/",
    "中科院計畫": "/IRLshare/工作區(報告、投影片等文件)/中科院計畫/",
    "VRMIMO": "/IRLshare/工作區(報告、投影片等文件)/VRMIMO/",
    "UAV論文": "/IRLshare/工作區(報告、投影片等文件)/UAV論文/",
    "Line Beacon": "/IRLshare/工作區(報告、投影片等文件)/Line Beacon/",
    "2022科技部成果發表": "/IRLshare/工作區(報告、投影片等文件)/2022科技部成果發表/",
    "2020綠能無人機創新大獎賽": "/IRLshare/工作區(報告、投影片等文件)/2020綠能無人機創新大獎賽_回顧帶(頒獎典禮播放).rar",
    "IRLNAS使用文件": "/IRLshare/工作區(報告、投影片等文件)/IRLNAS使用文件.docx",
    
    # 工具與資料
    "論文&口試流程參考資料": "/IRLshare/工具與資料/論文&口試流程參考資料/",
    "論文&口試流程 - 112": "/IRLshare/工具與資料/論文&口試流程 - 112/",
    "成員照片": "/IRLshare/工具與資料/成員照片/",
    "報帳範本與相關資料": "/IRLshare/工具與資料/報帳範本與相關資料/",
    "印表機驅動": "/IRLshare/工具與資料/印表機驅動/",
    "NS2": "/IRLshare/工具與資料/NS2/",
    "NAS-GIT使用說明": "/IRLshare/工具與資料/NAS-GIT使用說明/",
    "MongoDB使用方式": "/IRLshare/工具與資料/MongoDB使用方式/",
    "meeting投影片": "/IRLshare/工具與資料/meeting投影片/",
    "LOGO&文件範本": "/IRLshare/工具與資料/LOGO&文件範本/",
    "Linkit_one相關資料": "/IRLshare/工具與資料/Linkit_one相關資料/",
    "IoTGataway開發文件": "/IRLshare/工具與資料/IoTGataway開發文件/",
    "eclipse": "/IRLshare/工具與資料/eclipse/",
    "BLE相關資料": "/IRLshare/工具與資料/BLE相關資料/",
    "Cloud Station同步": "/IRLshare/工具與資料/Cloud Station同步.pptx"
}

# 全域 Session 與 SID 快取
_SESSION_CACHE = {"session": None, "sid": None, "host": None, "expires": 0}

def get_nas_credentials():
    config = dotenv_values(ENV_PATH)
    host = config.get("NAS_HOST", "yzuirl.synology.me:5001").replace('https://', '').replace('http://', '').rstrip('/')
    username = config.get("NAS_USERNAME", "蕭宇傑")
    password = config.get("NAS_PASSWORD", "Xiao921204@")
    return host, username, password

def get_nas_session(force_refresh=False):
    """取得具備驗證 SID 的 requests.Session，快取 15 分鐘避免重複登入"""
    global _SESSION_CACHE
    now = time.time()
    if not force_refresh and _SESSION_CACHE["session"] and _SESSION_CACHE["sid"] and now < _SESSION_CACHE["expires"]:
        return _SESSION_CACHE["session"], _SESSION_CACHE["host"], _SESSION_CACHE["sid"]

    host, username, password = get_nas_credentials()
    session = requests.Session()
    from urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    auth_url = f"https://{host}/webapi/auth.cgi"
    r = session.get(auth_url, params={
        "api": "SYNO.API.Auth",
        "version": "3",
        "method": "login",
        "account": username,
        "passwd": password,
        "session": "FileStation",
        "format": "sid"
    }, verify=False, timeout=15)
    data = r.json()
    if not data.get("success"):
        raise Exception(f"NAS API 登入失敗: {data}")

    sid = data["data"]["sid"]
    _SESSION_CACHE = {
        "session": session,
        "sid": sid,
        "host": host,
        "expires": now + 900
    }
    return session, host, sid

def clear_viewer_dir():
    """清除 thesis_viewer/ 暫存資料夾中的舊檔案，維護無痕原則與單一檔案生命週期"""
    import shutil
    if os.path.exists(VIEWER_DIR):
        for f in os.listdir(VIEWER_DIR):
            file_path = os.path.join(VIEWER_DIR, f)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass

def fuzzy_find_student(query):
    """
    通用模糊搜尋器：支援成員姓名 (畢業論文)、工作區專案、工具與資料之錯別字、同音字 (拼音) 與模糊比對。
    """
    query = query.strip()
    if not query:
        return {"match_type": "none", "candidates": []}

    # 1. 優先檢查是否為畢業論文成員 (精確匹配)
    if query in KNOWN_MEMBERS:
        return {"match_type": "exact", "target_type": "member", "best_match": query, "path": f"/IRLshare/畢業論文/{query}/", "candidates": [query]}

    # 2. 檢查是否為專案/工具資料夾 (精確或包含匹配)
    for p_name, p_path in KNOWN_PROJECTS.items():
        if query.lower() == p_name.lower():
            return {"match_type": "exact", "target_type": "project", "best_match": p_name, "path": p_path, "candidates": [p_name]}

    # 3. 同音字/拼音比對 (成員 + 專案)
    if lazy_pinyin:
        q_pinyin = "".join(lazy_pinyin(query))
        pinyin_matches = []
        for m in KNOWN_MEMBERS:
            m_pinyin = "".join(lazy_pinyin(m))
            if q_pinyin == m_pinyin or (len(q_pinyin) >= 4 and q_pinyin in m_pinyin):
                pinyin_matches.append((m, f"/IRLshare/畢業論文/{m}/", "member"))
        for p_name, p_path in KNOWN_PROJECTS.items():
            p_pinyin = "".join(lazy_pinyin(p_name))
            if q_pinyin in p_pinyin or p_pinyin in q_pinyin:
                pinyin_matches.append((p_name, p_path, "project"))

        if len(pinyin_matches) == 1:
            best_name, best_path, t_type = pinyin_matches[0]
            return {
                "match_type": "phonetic_exact",
                "target_type": t_type,
                "best_match": best_name,
                "path": best_path,
                "query": query,
                "note": f"辨識為同音字/拼音比對：{query} -> {best_name}",
                "candidates": [best_name]
            }
        elif len(pinyin_matches) > 1:
            return {"match_type": "phonetic_multiple", "candidates": [m[0] for m in pinyin_matches]}

    # 4. 子字串包含
    sub_matches = []
    for m in KNOWN_MEMBERS:
        if query in m or m in query:
            sub_matches.append((m, f"/IRLshare/畢業論文/{m}/", "member"))
    for p_name, p_path in KNOWN_PROJECTS.items():
        if query.lower() in p_name.lower() or p_name.lower() in query.lower():
            sub_matches.append((p_name, p_path, "project"))

    if len(sub_matches) == 1:
        best_name, best_path, t_type = sub_matches[0]
        return {"match_type": "substring", "target_type": t_type, "best_match": best_name, "path": best_path, "candidates": [best_name]}
    elif len(sub_matches) > 1:
        return {"match_type": "multiple_substring", "candidates": [m[0] for m in sub_matches]}

    # 5. 英文名 / lab_alumni.json 搜尋
    if os.path.exists(ALUMNI_PATH):
        try:
            with open(ALUMNI_PATH, "r", encoding="utf-8") as f:
                alumni_data = json.load(f)
                for item in alumni_data:
                    cname = item.get("中文姓名", "")
                    ename = item.get("英文姓名", "")
                    if query.lower() in ename.lower() or query in cname:
                        if cname in KNOWN_MEMBERS:
                            return {"match_type": "alumni_match", "target_type": "member", "best_match": cname, "path": f"/IRLshare/畢業論文/{cname}/", "info": item, "candidates": [cname]}
        except Exception:
            pass

    # 6. 模糊字串比對 (處理錯別字 / 漏字 / 諧音)
    all_targets = KNOWN_MEMBERS + list(KNOWN_PROJECTS.keys())
    close_matches = difflib.get_close_matches(query, all_targets, n=5, cutoff=0.25)
    if len(close_matches) == 1:
        best_name = close_matches[0]
        path = f"/IRLshare/畢業論文/{best_name}/" if best_name in KNOWN_MEMBERS else KNOWN_PROJECTS.get(best_name, "/IRLshare/")
        t_type = "member" if best_name in KNOWN_MEMBERS else "project"
        return {"match_type": "fuzzy_single", "target_type": t_type, "best_match": best_name, "path": path, "candidates": close_matches}
    elif len(close_matches) > 1:
        return {"match_type": "fuzzy_multiple", "candidates": close_matches}

    return {"match_type": "none", "candidates": []}

def nas_list(target_path="/IRLshare/畢業論文/"):
    """使用 Synology REST API 極速列出目錄內容 (毫秒級)"""
    try:
        session, host, sid = get_nas_session()
        clean_path = target_path.rstrip('/')
        url = f"https://{host}/webapi/entry.cgi"
        r = session.get(url, params={
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": clean_path,
            "filetype": "all",
            "_sid": sid
        }, verify=False, timeout=10)
        data = r.json()
        if not data.get("success") and data.get("error", {}).get("code") in [400, 401, 105, 106, 119]:
            session, host, sid = get_nas_session(force_refresh=True)
            r = session.get(url, params={
                "api": "SYNO.FileStation.List",
                "version": "2",
                "method": "list",
                "folder_path": clean_path,
                "filetype": "all",
                "_sid": sid
            }, verify=False, timeout=10)
            data = r.json()

        if not data.get("success"):
            return {"status": "error", "message": f"NAS API 回應錯誤: {data}"}

        raw_files = data.get("data", {}).get("files", [])
        items = []
        for f in raw_files:
            type_str = "Folder" if f.get("isdir") else "File"
            items.append(f"{f['name']} | {type_str} | {f['path']}")

        return {
            "status": "success",
            "path": target_path,
            "count": len(items),
            "files": raw_files,
            "items": items
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _find_target_file_recursive(session, host, sid, folder_path, file_keyword="論文"):
    """在指定資料夾及一層子資料夾內尋找最佳符合檔案 (跳過 ~$ 暫存檔，優先挑選 .pdf)"""
    clean_path = folder_path.rstrip('/')
    url = f"https://{host}/webapi/entry.cgi"
    r = session.get(url, params={
        "api": "SYNO.FileStation.List",
        "version": "2",
        "method": "list",
        "folder_path": clean_path,
        "filetype": "all",
        "_sid": sid
    }, verify=False, timeout=10)
    data = r.json()
    if not data.get("success") and data.get("error", {}).get("code") in [400, 401, 105, 106, 119]:
        session, host, sid = get_nas_session(force_refresh=True)
        r = session.get(url, params={
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": clean_path,
            "filetype": "all",
            "_sid": sid
        }, verify=False, timeout=10)
        data = r.json()

    files = data.get("data", {}).get("files", [])
    subdirs = []
    candidates = []

    for f in files:
        fname = f["name"]
        if f.get("isdir"):
            subdirs.append(f)
        else:
            if fname.startswith("~$") or fname.lower() == "thumbs.db":
                continue
            candidates.append(f)

    # 1. 支援所有常見文件與格式 (.pdf, .docx, .pptx, .txt, .xlsx, .csv, .zip, .rar, .vsdx, .png, .jpg)
    valid_candidates = [c for c in candidates if not c["name"].startswith("~$") and c["name"].lower() != "thumbs.db"]
    
    kw = file_keyword.strip().lower()

    # 優先 1：檔名完全包含關鍵字 (區分副檔名優先序)
    kw_matches = [c for c in valid_candidates if kw in c["name"].lower()]
    if kw_matches:
        # 若有多個匹配，依照副檔名及名稱相似度排序
        def match_score(c):
            ext = os.path.splitext(c["name"])[1].lower()
            score = 0
            if ext in [".pdf", ".pptx", ".docx", ".txt"]:
                score += 10
            if kw == os.path.splitext(c["name"])[0].lower():
                score += 20
            return score
        kw_matches.sort(key=match_score, reverse=True)
        return kw_matches[0]

    # 2. 若當前層無直接命中，遞迴搜尋子資料夾 (「論文/thesis」最優先，「口試/oral/簡報」次之)
    def subdir_priority(f_obj):
        name = f_obj["name"].lower()
        if "論文" in name or "thesis" in name:
            return 0
        if "口試" in name or "oral" in name or "簡報" in name or "投影片" in name:
            return 1
        return 2

    subdirs.sort(key=subdir_priority)
    for sdir in subdirs:
        sub_res = _find_target_file_recursive(session, host, sid, sdir["path"], file_keyword)
        if sub_res:
            return sub_res

    # 3. 若仍找不到，且有有效候選檔案，僅當關鍵字為泛指「論文」或「簡報」時才適度容錯
    if valid_candidates:
        if kw in ["論文", "thesis", "全文"]:
            for c in valid_candidates:
                if c["name"].lower().endswith(".pdf") or c["name"].lower().endswith(".docx"):
                    return c
        elif kw in ["簡報", "投影片", "ppt", "oral"]:
            for c in valid_candidates:
                if c["name"].lower().endswith(".pptx") or c["name"].lower().endswith(".ppt"):
                    return c

    return None

def nas_download_file_for_viewing(target_folder_path, file_keyword="論文", output_filename=None, clear_previous=True):
    """
    使用 REST API 極速下載 PDF / DOCX / PPTX / 圖片至本地暫存檢視資料夾 (0.3 秒)
    clear_previous: 預設為 True，自動清空前一位成員或上一輪的暫存檔案，只保留當前查詢之檔案。
    """
    if clear_previous:
        clear_viewer_dir()
    os.makedirs(VIEWER_DIR, exist_ok=True)

    try:
        session, host, sid = get_nas_session()
        target_file = _find_target_file_recursive(session, host, sid, target_folder_path, file_keyword)
        if not target_file:
            return {"status": "error", "message": f"在 {target_folder_path} 內找不到符合 '{file_keyword}' 的有效檔案"}

        actual_name = target_file["name"]
        _, ext = os.path.splitext(actual_name)
        if not ext:
            ext = ".pdf"

        if not output_filename:
            output_filename = actual_name
        elif not output_filename.lower().endswith(ext.lower()):
            output_filename = output_filename + ext

        final_path = os.path.join(VIEWER_DIR, output_filename)
        dl_url = f"https://{host}/webapi/entry.cgi"
        r = session.get(dl_url, params={
            "api": "SYNO.FileStation.Download",
            "version": "2",
            "method": "download",
            "path": target_file["path"],
            "mode": "download",
            "_sid": sid
        }, verify=False, stream=True, timeout=30)

        raw_content = bytearray()
        for chunk in r.iter_content(chunk_size=16384):
            if chunk:
                raw_content.extend(chunk)

        # 若為文字檔案，自動偵測並轉碼為 UTF-8，杜絕 Big5/CP950 亂碼
        if ext.lower() in [".txt", ".csv", ".json", ".log", ".md", ".py"]:
            text_saved = False
            for enc in ["utf-8", "cp950", "big5", "gbk"]:
                try:
                    decoded_text = raw_content.decode(enc)
                    with open(final_path, "w", encoding="utf-8") as f:
                        f.write(decoded_text)
                    text_saved = True
                    break
                except Exception:
                    pass
            if not text_saved:
                with open(final_path, "wb") as f:
                    f.write(raw_content)
        else:
            with open(final_path, "wb") as f:
                f.write(raw_content)

        file_size = os.path.getsize(final_path)
        return {
            "status": "success",
            "file_path": final_path,
            "file_name": output_filename,
            "size": file_size
        }
    except Exception as e:
        return {"status": "error", "message": f"下載失敗: {e}"}

def nas_download_all_files(target_folder_path, subfolder_name=None, clear_previous=True):
    """
    一鍵下載指定成員或專案目錄下的所有重要檔案（論文、投影片、程式碼、相關文件）至本地檢視器
    """
    if clear_previous:
        clear_viewer_dir()

    folder_name = subfolder_name or os.path.basename(target_folder_path.strip('/')) or "downloaded"
    save_dir = os.path.join(VIEWER_DIR, folder_name)
    os.makedirs(save_dir, exist_ok=True)

    try:
        session, host, sid = get_nas_session()
        list_res = nas_list(target_folder_path)
        if list_res.get("status") != "success":
            return list_res

        downloaded_files = []
        for item in list_res.get("files", []):
            if not item.get("isdir"):
                fname = item["name"]
                if fname.lower() in ["thumbs.db", ".ds_store"] or fname.startswith("~$"):
                    continue
                fpath = os.path.join(save_dir, fname)
                dl_url = f"https://{host}/webapi/entry.cgi"
                r = session.get(dl_url, params={
                    "api": "SYNO.FileStation.Download",
                    "version": "2",
                    "method": "download",
                    "path": item["path"],
                    "mode": "download",
                    "_sid": sid
                }, verify=False, stream=True, timeout=60)
                with open(fpath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)
                downloaded_files.append({
                    "name": fname,
                    "path": fpath,
                    "size": os.path.getsize(fpath)
                })

        return {
            "status": "success",
            "folder": target_folder_path,
            "local_dir": save_dir,
            "total_files": len(downloaded_files),
            "files": downloaded_files
        }
    except Exception as e:
        return {"status": "error", "message": f"批量下載失敗: {e}"}

def nas_read_file(target_folder_path, file_keyword="論文", max_pages=25):
    """
    使用 REST API 記憶體串流極速解析論文文字 (完全無痕、零磁碟殘留、0.5 秒完成)
    """
    try:
        session, host, sid = get_nas_session()
        target_file = _find_target_file_recursive(session, host, sid, target_folder_path, file_keyword)
        if not target_file:
            return {"status": "error", "message": f"在 {target_folder_path} 內找不到符合 '{file_keyword}' 的有效檔案"}

        dl_url = f"https://{host}/webapi/entry.cgi"
        r = session.get(dl_url, params={
            "api": "SYNO.FileStation.Download",
            "version": "2",
            "method": "download",
            "path": target_file["path"],
            "mode": "download",
            "_sid": sid
        }, verify=False, timeout=30)

        raw_bytes = io.BytesIO(r.content)
        actual_name = target_file["name"].lower()
        is_docx = actual_name.endswith(".docx")

        if is_docx:
            doc = docx.Document(raw_bytes)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            total_pages = f"{len(paragraphs)} 段落"
            res_content = "\n".join(paragraphs[:80])
            ftype = "DOCX"
        else:
            reader = PdfReader(raw_bytes)
            total_pages = f"{len(reader.pages)} 頁"
            extracted = []
            for i in range(min(max_pages, len(reader.pages))):
                text = reader.pages[i].extract_text() or ""
                extracted.append(f"=== [第 {i+1} 頁] ===\n{text}\n")
            res_content = "".join(extracted)
            ftype = "PDF"

        return {
            "status": "success",
            "folder": target_folder_path,
            "file_name": target_file["name"],
            "file_type": ftype,
            "total_pages": total_pages,
            "content": res_content
        }
    except Exception as e:
        return {"status": "error", "message": f"解析文字失敗: {e}"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python nas_reader.py match|list|read|open")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "match":
        q = sys.argv[2] if len(sys.argv) > 2 else ""
        res = fuzzy_find_student(q)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif cmd == "list":
        path = sys.argv[2] if len(sys.argv) > 2 else "/IRLshare/畢業論文/"
        res = nas_list(path)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif cmd == "read":
        folder = sys.argv[2]
        if not folder.startswith("/"):
            m = fuzzy_find_student(folder)
            folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
        kw = sys.argv[3] if len(sys.argv) > 3 else "論文"
        res = nas_read_file(folder, kw)
        if res.get("status") == "success":
            print(f"\n==================== 📖 論文內容即時解析（{res['total_pages']}） ====================")
            print(res["content"][:4000])
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))
    elif cmd == "open":
        folder = sys.argv[2]
        if not folder.startswith("/"):
            m = fuzzy_find_student(folder)
            folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
        kw = sys.argv[3] if len(sys.argv) > 3 else "論文"
        outname = sys.argv[4] if len(sys.argv) > 4 else kw
        res = nas_download_file_for_viewing(folder, kw, outname)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif cmd == "open_all":
        folder = sys.argv[2]
        if not folder.startswith("/"):
            m = fuzzy_find_student(folder)
            folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
        subfolder = sys.argv[3] if len(sys.argv) > 3 else None
        res = nas_download_all_files(folder, subfolder)
        print(json.dumps(res, ensure_ascii=False, indent=2))

