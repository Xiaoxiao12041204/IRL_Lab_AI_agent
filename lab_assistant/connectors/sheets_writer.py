"""
IRL Lab AI Assistant - Google Sheets 自動記帳模組
透過既有 Service Account 直接讀寫實驗室公用經費試算表。
不需額外申請憑證，與 Google Calendar 模組共用同一組 Service Account。
"""
import os
import sys
import json
import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) in ('connectors', 'core') else CURRENT_DIR
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 載入 .env
ENV_FILE = os.path.join(BASE_DIR, '.env')
if os.path.exists(ENV_FILE):
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass

# Service Account 憑證（與 google_calendar_reader.py 共用同一檔案）
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials", "service_account.json")

# 試算表設定（從 .env 讀取，或使用已知 ID）
SPREADSHEET_ID = os.getenv(
    'GOOGLE_SPREADSHEET_ID',
    '1un-VyqNpeIMiQvHZSW51Koo7_WZI-XwQdxs_mTc7O2w'
)
# 工作表索引頁名稱（GID=9 對應的工作表標籤名稱，請依實際填入）
SHEET_TAB = os.getenv('GOOGLE_SHEET_TAB', '公用經費')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
]

_sheets_service = None


def get_sheets_service():
    """取得或快取 Google Sheets API Service（與 Calendar 共用 Service Account）"""
    global _sheets_service
    if _sheets_service is not None:
        return _sheets_service

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[SheetsError] 找不到憑證檔案: {CREDENTIALS_FILE}", file=sys.stderr)
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        _sheets_service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        return _sheets_service
    except ImportError:
        print("[SheetsError] 缺少套件，請執行: pip install google-api-python-client google-auth", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[SheetsError] 初始化 Google Sheets 服務失敗: {e}", file=sys.stderr)
        return None


def get_current_balance() -> float:
    """
    讀取試算表最後一筆有效結餘。
    若試算表連線失敗，自動 fallback 至本地 lab_funds_ledger.json。
    """
    service = get_sheets_service()
    if service:
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{SHEET_TAB}!A:D'
            ).execute()
            rows = result.get('values', [])
            # 從最後一列往上找有效結餘數值
            for row in reversed(rows):
                if len(row) >= 3 and row[2]:
                    try:
                        val = str(row[2]).replace(',', '').replace('$', '').replace(' ', '')
                        return float(val)
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            print(f"[SheetsWarning] 讀取試算表結餘失敗，改用本地快取: {e}", file=sys.stderr)

    return _get_local_balance()


def _get_local_balance() -> float:
    """從本地 lab_funds_ledger.json 取得最新結餘"""
    ledger_path = os.path.join(DATA_DIR, 'lab_funds_ledger.json')
    if not os.path.exists(ledger_path):
        return 0.0
    try:
        with open(ledger_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for entry in reversed(data):
            if entry.get('結餘') is not None:
                return float(entry['結餘'])
    except Exception:
        pass
    return 0.0


def append_transaction(amount: float, memo: str, date_str: str = None) -> dict:
    """
    新增一筆收支記錄，同時寫入：
      1. Google Sheets 試算表（主要）
      2. 本地 lab_funds_ledger.json（快取，確保離線也可查詢）

    Args:
        amount:   金額（正數 = 收入，負數 = 支出）
        memo:     備註說明（如「買零食」、「計畫補助款」）
        date_str: 日期字串 YYYY-MM-DD，預設今天

    Returns:
        dict 包含 status、new_balance、synced_to_sheets 等欄位
    """
    if not date_str:
        today = datetime.date.today()
        # 使用試算表現有格式：YYYY/M/D（無前補零，斜線分隔）
        date_str = f"{today.year}/{today.month}/{today.day}"

    # 取得目前結餘並計算新結餘
    current_balance = get_current_balance()
    new_balance = round(current_balance + amount, 2)

    service = get_sheets_service()
    synced_to_sheets = False

    if service:
        try:
            new_row = [[date_str, amount, new_balance, memo]]
            body = {'values': new_row}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{SHEET_TAB}!A:D',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            synced_to_sheets = True
        except Exception as e:
            print(f"[SheetsError] 寫入試算表失敗: {e}", file=sys.stderr)

    # 無論 Sheets 是否成功都同步本地 JSON
    _append_local_ledger(date_str, amount, new_balance, memo)

    # 組裝回傳訊息
    amount_str = f"+{amount:,.0f}" if amount >= 0 else f"{amount:,.0f}"
    if synced_to_sheets:
        sync_msg = "✅ 已同步寫入 Google Sheets 試算表與本地快取"
    else:
        sync_msg = "⚠️ 試算表連線失敗，已寫入本地快取（請稍後重試或手動補登）"

    return {
        "status": "success" if synced_to_sheets else "local_only",
        "synced_to_sheets": synced_to_sheets,
        "date": date_str,
        "amount": amount,
        "amount_display": amount_str,
        "previous_balance": current_balance,
        "new_balance": new_balance,
        "memo": memo,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}",
        "message": sync_msg,
        "summary": f"📅 {date_str}　{amount_str} 元　備註：{memo}　→ 目前結餘：{new_balance:,.0f} 元"
    }


def _append_local_ledger(date_str: str, amount: float, new_balance: float, memo: str):
    """同步更新本地 lab_funds_ledger.json 快取"""
    ledger_path = os.path.join(DATA_DIR, 'lab_funds_ledger.json')
    data = []
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = []

    data.append({
        "日期": date_str,
        "收支金額(增減)": amount,
        "結餘": new_balance,
        "備註": memo
    })

    with open(ledger_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_recent_transactions(n: int = 10) -> dict:
    """
    讀取試算表最近 n 筆收支記錄。
    Fallback 至本地 JSON。

    Returns:
        dict 包含 transactions list 與 current_balance
    """
    service = get_sheets_service()
    rows_data = []

    if service:
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{SHEET_TAB}!A:D'
            ).execute()
            rows = result.get('values', [])
            # 跳過標題列，取最後 n 筆
            data_rows = [r for r in rows if len(r) >= 2 and r[0] and r[0] != '日期']
            for row in data_rows[-n:]:
                rows_data.append({
                    "日期": row[0] if len(row) > 0 else "",
                    "收支金額(增減)": row[1] if len(row) > 1 else "",
                    "結餘": row[2] if len(row) > 2 else "",
                    "備註": row[3] if len(row) > 3 else ""
                })
        except Exception as e:
            print(f"[SheetsWarning] 讀取最近帳目失敗，改用本地快取: {e}", file=sys.stderr)

    if not rows_data:
        # Fallback 至本地
        ledger_path = os.path.join(DATA_DIR, 'lab_funds_ledger.json')
        if os.path.exists(ledger_path):
            with open(ledger_path, 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            rows_data = [e for e in local_data if e.get('日期')][-n:]

    current_balance = get_current_balance()
    return {
        "transactions": rows_data,
        "current_balance": current_balance,
        "count": len(rows_data),
        "source": "google_sheets" if service else "local_cache"
    }


# 「實驗室共用經費」工作表的 GID（試算表 URL 中 #gid=9）
SHEET_GID = int(os.getenv('GOOGLE_SHEET_GID', '9'))


def _get_all_data_rows() -> list:
    """取得試算表所有有效資料列（含 0-based row index，用於刪除定位）"""
    service = get_sheets_service()
    if not service:
        return []
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{SHEET_TAB}!A:D'
    ).execute()
    rows = result.get('values', [])
    data_rows = []
    for i, row in enumerate(rows):
        if not row or not row[0] or row[0] == '日期':
            continue
        data_rows.append((i, row))
    return data_rows


def delete_last_transaction() -> dict:
    """刪除試算表最後一筆有效記錄，並同步移除本地 JSON 最後一筆。"""
    service = get_sheets_service()
    if not service:
        return {"status": "error", "message": "試算表連線失敗，無法執行刪除"}
    data_rows = _get_all_data_rows()
    if not data_rows:
        return {"status": "error", "message": "試算表中找不到任何資料列"}
    last_idx, last_row = data_rows[-1]
    deleted_info = {
        "日期": last_row[0] if len(last_row) > 0 else "",
        "收支金額": last_row[1] if len(last_row) > 1 else "",
        "結餘": last_row[2] if len(last_row) > 2 else "",
        "備註": last_row[3] if len(last_row) > 3 else "",
    }
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId": SHEET_GID,
                "dimension": "ROWS",
                "startIndex": last_idx,
                "endIndex": last_idx + 1
            }}}]}
        ).execute()
    except Exception as e:
        return {"status": "error", "message": f"刪除試算表列失敗: {e}"}
    _delete_local_last()
    new_balance = get_current_balance()
    return {
        "status": "success",
        "message": "已刪除最後一筆記帳記錄",
        "deleted": deleted_info,
        "new_balance": new_balance,
        "summary": f"已刪除：{deleted_info['日期']} {deleted_info['收支金額']} 元（{deleted_info['備註']}）→ 目前結餘回到 {new_balance:,.0f} 元"
    }


def delete_transaction_by_keyword(keyword: str) -> dict:
    """依備註關鍵字搜尋並刪除最近一筆符合的記錄（從最新往回找）。"""
    service = get_sheets_service()
    if not service:
        return {"status": "error", "message": "試算表連線失敗"}
    data_rows = _get_all_data_rows()
    target_idx, target_row = None, None
    for idx, row in reversed(data_rows):
        memo = row[3] if len(row) > 3 else ""
        if keyword.lower() in memo.lower():
            target_idx = idx
            target_row = row
            break
    if target_idx is None:
        return {"status": "not_found", "message": f"找不到備註包含「{keyword}」的記錄"}
    deleted_info = {
        "日期": target_row[0] if len(target_row) > 0 else "",
        "收支金額": target_row[1] if len(target_row) > 1 else "",
        "備註": target_row[3] if len(target_row) > 3 else "",
    }
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId": SHEET_GID,
                "dimension": "ROWS",
                "startIndex": target_idx,
                "endIndex": target_idx + 1
            }}}]}
        ).execute()
    except Exception as e:
        return {"status": "error", "message": f"刪除試算表列失敗: {e}"}
    _delete_local_by_keyword(keyword)
    new_balance = get_current_balance()
    return {
        "status": "success",
        "message": f"已刪除備註含「{keyword}」的記錄",
        "deleted": deleted_info,
        "new_balance": new_balance,
        "summary": f"已刪除：{deleted_info['日期']} {deleted_info['收支金額']} 元（{deleted_info['備註']}）→ 目前結餘 {new_balance:,.0f} 元"
    }


def _delete_local_last():
    """刪除本地 lab_funds_ledger.json 最後一筆"""
    ledger_path = os.path.join(DATA_DIR, 'lab_funds_ledger.json')
    if not os.path.exists(ledger_path):
        return
    with open(ledger_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if data:
        data.pop()
    with open(ledger_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _delete_local_by_keyword(keyword: str):
    """刪除本地 JSON 中最新一筆備註符合 keyword 的記錄"""
    ledger_path = os.path.join(DATA_DIR, 'lab_funds_ledger.json')
    if not os.path.exists(ledger_path):
        return
    with open(ledger_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for i in range(len(data) - 1, -1, -1):
        memo = data[i].get('備註', '') or ''
        if keyword.lower() in memo.lower():
            data.pop(i)
            break
    with open(ledger_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
