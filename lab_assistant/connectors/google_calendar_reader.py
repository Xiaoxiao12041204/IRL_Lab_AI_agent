"""
IRL Lab AI Assistant - Google Calendar 實驗室行事曆連動模組
負責連動 Google Calendar REST API，即時檢索實驗室成員請假狀態、日期與時段。
"""
import os
import sys
import datetime
from typing import List, Dict, Any, Optional

# 載入自訂套件路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) in ('connectors', 'core') else CURRENT_DIR
PYLIB_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "pylib"))
if PYLIB_DIR not in sys.path:
    sys.path.insert(0, PYLIB_DIR)

# 載入環境變數
ENV_FILE = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_FILE):
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass

CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "legptj6nu1ite83tuijr5996pg@group.calendar.google.com")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials", "service_account.json")
SCOPES = ['https://www.googleapis.com/auth/calendar']

_calendar_service = None

def get_calendar_service():
    """取得或快取 Google Calendar API Service"""
    global _calendar_service
    if _calendar_service is not None:
        return _calendar_service

    if not os.path.exists(CREDENTIALS_FILE):
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        _calendar_service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
        return _calendar_service
    except Exception as e:
        print(f"[CalendarError] 初始化 Google Calendar 服務失敗: {e}", file=sys.stderr)
        return None

def _parse_event_time(dt_dict: Dict[str, Any]) -> str:
    """格式化活動時間"""
    if not dt_dict:
        return ""
    if 'dateTime' in dt_dict:
        raw = dt_dict['dateTime']
        # 格式範例: 2026-09-08T10:00:00+08:00
        try:
            dt = datetime.datetime.fromisoformat(raw)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw
    elif 'date' in dt_dict:
        return dt_dict['date']
    return ""

def list_calendar_events(time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 50) -> List[Dict[str, Any]]:
    """查詢行事曆指定時間範圍內的事件"""
    service = get_calendar_service()
    if not service:
        return []

    try:
        params = {
            "calendarId": CALENDAR_ID,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results
        }
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max

        events_result = service.events().list(**params).execute()
        return events_result.get("items", [])
    except Exception as e:
        print(f"[CalendarError] 查詢行事曆失敗: {e}", file=sys.stderr)
        return []

def get_today_leaves(target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    查詢指定日期（預設為今日）之請假名冊
    """
    if target_date is None:
        target_date = datetime.date.today()

    target_str = target_date.strftime("%Y-%m-%d")
    # 建立該日 00:00:00 ~ 23:59:59 (Taipei UTC+8)
    time_min = f"{target_str}T00:00:00+08:00"
    time_max = f"{target_str}T23:59:59+08:00"

    raw_events = list_calendar_events(time_min=time_min, time_max=time_max)
    leaves = []

    for ev in raw_events:
        summary = ev.get("summary", "").strip()
        start_str = _parse_event_time(ev.get("start", {}))
        end_str = _parse_event_time(ev.get("end", {}))
        desc = ev.get("description", "").strip()
        leaves.append({
            "title": summary,
            "start": start_str,
            "end": end_str,
            "description": desc,
            "id": ev.get("id", "")
        })

    return {
        "status": "success",
        "date": target_str,
        "count": len(leaves),
        "leaves": leaves
    }

def get_week_leaves(target_date: Optional[datetime.date] = None, week_offset: int = 0) -> Dict[str, Any]:
    """
    查詢指定週（預設本週，週一至週日）之請假活動紀錄
    """
    if target_date is None:
        target_date = datetime.date.today()

    start_date = target_date - datetime.timedelta(days=target_date.weekday()) + datetime.timedelta(weeks=week_offset)
    end_date = start_date + datetime.timedelta(days=6)

    time_min = f"{start_date.strftime('%Y-%m-%d')}T00:00:00+08:00"
    time_max = f"{end_date.strftime('%Y-%m-%d')}T23:59:59+08:00"

    raw_events = list_calendar_events(time_min=time_min, time_max=time_max)
    leaves = []

    for ev in raw_events:
        summary = ev.get("summary", "").strip()
        start_str = _parse_event_time(ev.get("start", {}))
        end_str = _parse_event_time(ev.get("end", {}))
        desc = ev.get("description", "").strip()
        leaves.append({
            "title": summary,
            "start": start_str,
            "end": end_str,
            "description": desc,
            "id": ev.get("id", "")
        })

    return {
        "status": "success",
        "range": f"{start_date} ~ {end_date}",
        "count": len(leaves),
        "leaves": leaves
    }

def get_recent_leaves(days_back: int = 21, days_forward: int = 14) -> Dict[str, Any]:
    """
    查詢近幾天之所有請假活動紀錄（預設涵蓋過去 3 週至未來 2 週）
    """
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days_back)
    end_date = today + datetime.timedelta(days=days_forward)

    time_min = f"{start_date.strftime('%Y-%m-%d')}T00:00:00+08:00"
    time_max = f"{end_date.strftime('%Y-%m-%d')}T23:59:59+08:00"

    raw_events = list_calendar_events(time_min=time_min, time_max=time_max)
    leaves = []

    for ev in raw_events:
        summary = ev.get("summary", "").strip()
        start_str = _parse_event_time(ev.get("start", {}))
        end_str = _parse_event_time(ev.get("end", {}))
        desc = ev.get("description", "").strip()
        leaves.append({
            "title": summary,
            "start": start_str,
            "end": end_str,
            "description": desc,
            "id": ev.get("id", "")
        })

    return {
        "status": "success",
        "range": f"{start_date} ~ {end_date}",
        "count": len(leaves),
        "leaves": leaves
    }

def get_month_leaves(year: int, month: int) -> Dict[str, Any]:
    """
    查詢指定月份（如 2026-09）之所有請假活動紀錄
    """
    import calendar as pycal
    _, last_day = pycal.monthrange(year, month)
    time_min = f"{year:04d}-{month:02d}-01T00:00:00+08:00"
    time_max = f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59+08:00"

    raw_events = list_calendar_events(time_min=time_min, time_max=time_max)
    leaves = []

    for ev in raw_events:
        summary = ev.get("summary", "").strip()
        start_str = _parse_event_time(ev.get("start", {}))
        end_str = _parse_event_time(ev.get("end", {}))
        desc = ev.get("description", "").strip()
        leaves.append({
            "title": summary,
            "start": start_str,
            "end": end_str,
            "description": desc,
            "id": ev.get("id", "")
        })

    return {
        "status": "success",
        "month": f"{year:04d}-{month:02d}",
        "count": len(leaves),
        "leaves": leaves
    }

def check_member_leave(member_name: str, target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    檢查特定成員於指定日期是否有請假紀錄
    """
    if target_date is None:
        target_date = datetime.date.today()

    target_str = target_date.strftime("%Y-%m-%d")
    today_res = get_today_leaves(target_date)
    leaves = today_res.get("leaves", [])

    matched_leaves = []
    clean_name = member_name.strip()

    for l in leaves:
        title = l["title"]
        # 支援簡稱與全名匹配（如 倫廣 <-> 袁倫廣）
        if clean_name in title or any(part in title for part in [clean_name[-2:], clean_name]):
            matched_leaves.append(l)

    return {
        "status": "success",
        "member": member_name,
        "date": target_str,
        "is_on_leave": len(matched_leaves) > 0,
        "leave_records": matched_leaves
    }

def add_leave_event(member_name: str, date_str: str, start_time: str = "10:00", end_time: str = "17:00", reason: str = "") -> Dict[str, Any]:
    """
    自動為成員於 Google 行事曆新增請假活動（符合實驗室慣例：活動標題預設為成員姓名）
    """
    service = get_calendar_service()
    if not service:
        return {"status": "error", "message": "Google Calendar 服務未連線"}

    try:
        # 格式轉換: 2026-09-18T10:00:00+08:00
        start_dt = f"{date_str}T{start_time}:00+08:00"
        end_dt = f"{date_str}T{end_time}:00+08:00"

        clean_reason = reason.strip() if reason else ""
        event_title = f"{member_name} {clean_reason}".strip() if clean_reason else member_name
        desc_text = "由 IRL Lab AI 助理自動登記"

        event_body = {
            'summary': event_title,
            'description': desc_text,
            'start': {
                'dateTime': start_dt,
                'timeZone': 'Asia/Taipei',
            },
            'end': {
                'dateTime': end_dt,
                'timeZone': 'Asia/Taipei',
            },
        }

        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        return {
            "status": "success",
            "message": f"已成功為 {member_name} 登記 {date_str} 請假行程",
            "event_id": created_event.get("id"),
            "html_link": created_event.get("htmlLink")
        }
    except Exception as e:
        return {"status": "error", "message": f"新增請假活動失敗: {str(e)}"}

def cancel_leave_event(member_name: str, date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    取消特定成員於指定日期（或最近一筆）的請假活動並從 Google 日曆刪除
    """
    service = get_calendar_service()
    if not service:
        return {"status": "error", "message": "Google Calendar 服務未連線"}

    try:
        if date_str:
            time_min = f"{date_str}T00:00:00+08:00"
            time_max = f"{date_str}T23:59:59+08:00"
            raw_events = list_calendar_events(time_min=time_min, time_max=time_max)
            leaves = []
            for ev in raw_events:
                leaves.append({
                    "title": ev.get("summary", "").strip(),
                    "start": _parse_event_time(ev.get("start", {})),
                    "end": _parse_event_time(ev.get("end", {})),
                    "description": ev.get("description", "").strip(),
                    "id": ev.get("id", "")
                })
        else:
            recent = get_recent_leaves(days_back=30, days_forward=90)
            leaves = recent.get("leaves", [])

        clean_name = member_name.strip()
        matched = []
        for l in leaves:
            title = l.get("title", "")
            if clean_name in title or any(part in title for part in [clean_name[-2:], clean_name]):
                matched.append(l)

        if not matched:
            target_desc = f"{date_str} " if date_str else ""
            return {
                "status": "error",
                "message": f"未在行事曆找到 {member_name} {target_desc}的請假活動"
            }

        deleted_records = []
        for m in matched:
            event_id = m.get("id")
            if event_id:
                service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
                deleted_records.append(m)

        return {
            "status": "success",
            "message": f"已成功為 {member_name} 取消 {len(deleted_records)} 筆請假行程，並已從 Google 日曆同步刪除",
            "deleted_events": deleted_records
        }
    except Exception as e:
        return {"status": "error", "message": f"取消請假活動失敗: {str(e)}"}

