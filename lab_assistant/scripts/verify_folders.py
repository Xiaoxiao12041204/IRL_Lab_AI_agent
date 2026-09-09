"""
使用 Synology FileStation REST API 直接列出所有子資料夾，
不受 Playwright UI 分頁/捲動限制，確保取得完整清單。
"""
import os, sys, json, requests, urllib3
from dotenv import dotenv_values

urllib3.disable_warnings()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', '.env'))
THESIS_INDEX_PATH = os.path.join(CURRENT_DIR, 'thesis_index.json')
ALUMNI_PATH = os.path.join(CURRENT_DIR, 'lab_alumni.json')
NAS_ROOT_FOLDER = "/IRLshare/畢業論文"

def get_creds():
    env = dotenv_values(ENV_PATH)
    host = env.get('NAS_HOST', 'yzuirl.synology.me:5001').replace('https://', '').replace('http://', '')
    return host, env.get('NAS_USERNAME', '蕭宇傑'), env.get('NAS_PASSWORD', 'Xiao921204@')

def api_login(session, host, user, pwd):
    url = f"https://{host}/webapi/auth.cgi"
    r = session.get(url, params={
        "api": "SYNO.API.Auth",
        "version": "3",
        "method": "login",
        "account": user,
        "passwd": pwd,
        "session": "FileStation",
        "format": "sid"
    }, verify=False, timeout=20)
    data = r.json()
    if data.get('success'):
        sid = data['data']['sid']
        print(f"[*] 登入成功，SID: {sid[:10]}...", flush=True)
        return sid
    else:
        raise Exception(f"登入失敗: {data}")

def api_list_folder(session, host, sid, folder_path, offset=0, limit=500):
    # DSM 7.x 使用 entry.cgi
    for endpoint in ["/webapi/entry.cgi", "/webapi/FileStation/list.cgi"]:
        url = f"https://{host}{endpoint}"
        r = session.get(url, params={
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": folder_path,
            "offset": offset,
            "limit": limit,
            "filetype": "dir",
            "_sid": sid
        }, verify=False, timeout=20)
        if r.status_code == 200 and r.text.strip():
            try:
                return r.json()
            except Exception:
                print(f"[!] {endpoint} 回應無法解析 JSON，嘗試下一個端點", flush=True)
                continue
    raise Exception("所有 API 端點均失敗")

def run():
    host, user, pwd = get_creds()

    with open(ALUMNI_PATH, 'r', encoding='utf-8') as f:
        alumni = json.load(f)
    with open(THESIS_INDEX_PATH, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    all_alumni_names = [a['中文姓名'] for a in alumni]
    print(f"[*] 校友總人數: {len(all_alumni_names)} 人", flush=True)

    session = requests.Session()
    sid = api_login(session, host, user, pwd)

    # 取得所有資料夾 (分頁直到取完)
    all_folders = []
    offset = 0
    limit = 500
    while True:
        result = api_list_folder(session, host, sid, NAS_ROOT_FOLDER, offset=offset, limit=limit)
        if not result.get('success'):
            print(f"[!] API 錯誤: {result}", flush=True)
            break
        items = result['data'].get('files', [])
        all_folders.extend(items)
        total = result['data'].get('total', 0)
        offset += limit
        if offset >= total:
            break

    real_folder_names = set()
    for item in all_folders:
        name = item.get('name', '')
        if name:
            real_folder_names.add(name)

    print(f"\n[*] NAS 畢業論文根目錄實際資料夾數: {len(real_folder_names)} 個", flush=True)
    print(f"[*] 完整清單: {sorted(real_folder_names)}", flush=True)

    # 比對
    print("\n==============================", flush=True)
    print("📋 校友 vs NAS 比對結果：", flush=True)
    print("==============================", flush=True)
    has_folder = []
    no_folder = []
    for name in all_alumni_names:
        if name in real_folder_names:
            has_folder.append(name)
            print(f"  ✅ {name}", flush=True)
        else:
            no_folder.append(name)
            print(f"  ❌ {name} — NAS 無資料夾", flush=True)

    print(f"\n✅ 有 NAS 資料夾: {len(has_folder)} 人", flush=True)
    print(f"❌ 無 NAS 資料夾: {len(no_folder)} 人: {no_folder}", flush=True)

    # 更新 thesis_index.json
    updated = 0
    for item in index_data:
        author = item['author']
        if author in no_folder and item.get('nas_path'):
            print(f"\n[清空] {author}: nas_path 清空 (原: {item['nas_path']})", flush=True)
            item['nas_path'] = ""
            updated += 1
        elif author in has_folder and not item.get('nas_path'):
            correct = f"/IRLshare/畢業論文/{author}/"
            print(f"\n[補回] {author}: nas_path 補回 -> {correct}", flush=True)
            item['nas_path'] = correct
            updated += 1

    if updated:
        with open(THESIS_INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        print(f"\n[+] 共更新 {updated} 筆 thesis_index.json", flush=True)
    else:
        print("\n[+] thesis_index.json 無需更新，資料已正確！", flush=True)

    # 登出
    session.get(f"https://{host}/webapi/auth.cgi", params={
        "api": "SYNO.API.Auth", "version": "1",
        "method": "logout", "session": "FileStation", "_sid": sid
    }, verify=False)

    print("\n🎉 API 比對完成！", flush=True)

if __name__ == "__main__":
    run()
