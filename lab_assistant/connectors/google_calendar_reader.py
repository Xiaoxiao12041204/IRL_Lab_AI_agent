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

# 實驗室現役成員正式全名與日曆慣用兩字簡稱對照表
LAB_MEMBERS = {
    "邱子倫": "子倫",
    "袁倫廣": "倫廣",
    "尹才彥": "才彥",
    "林銘聖": "銘聖",
    "楊正宇": "正宇",
    "蘇冠宇": "冠宇",
    "蕭宇傑": "宇傑",
}

# 常見錯字、別字、同音字、別名對照表
MEMBER_TYPO_MAP = {
    # 林銘聖 (銘聖)
    "銘璽": "銘聖",
    "林銘璽": "銘聖",
    "銘勝": "銘聖",
    "林銘勝": "銘聖",
    "明聖": "銘聖",
    "林明聖": "銘聖",
    "明勝": "銘聖",
    "林明勝": "銘聖",
    "銘盛": "銘聖",
    "林銘盛": "銘聖",
    "銘笙": "銘聖",
    "林銘笙": "銘聖",
    "銘慎": "銘聖",
    "林銘慎": "銘聖",
    "林銘": "銘聖",
    "銘聖": "銘聖",
    "林銘聖": "銘聖",

    # 楊正宇 (正宇)
    "政宇": "正宇",
    "楊政宇": "正宇",
    "正雨": "正宇",
    "楊正雨": "正宇",
    "政雨": "正宇",
    "楊政雨": "正宇",
    "正羽": "正宇",
    "楊正羽": "正宇",
    "震宇": "正宇",
    "楊震宇": "正宇",
    "振宇": "正宇",
    "楊振宇": "正宇",
    "正語": "正宇",
    "楊正語": "正宇",
    "正宇": "正宇",
    "楊正宇": "正宇",

    # 袁倫廣 (倫廣)
    "倫光": "倫廣",
    "袁倫光": "倫廣",
    "輪廣": "倫廣",
    "袁輪廣": "倫廣",
    "輪光": "倫廣",
    "袁輪光": "倫廣",
    "綸廣": "倫廣",
    "袁綸廣": "倫廣",
    "倫廣": "倫廣",
    "袁倫廣": "倫廣",

    # 邱子倫 (子倫)
    "子輪": "子倫",
    "邱子輪": "子倫",
    "子綸": "子倫",
    "邱子綸": "子倫",
    "梓倫": "子倫",
    "邱梓倫": "子倫",
    "紫倫": "子倫",
    "邱紫倫": "子倫",
    "子倫": "子倫",
    "邱子倫": "子倫",

    # 尹才彥 (才彥)
    "采彥": "才彥",
    "尹采彥": "才彥",
    "彩彥": "才彥",
    "尹彩彥": "才彥",
    "才宴": "才彥",
    "尹才宴": "才彥",
    "才諺": "才彥",
    "尹才諺": "才彥",
    "才硯": "才彥",
    "尹才硯": "才彥",
    "才彥": "才彥",
    "尹才彥": "才彥",

    # 蘇冠宇 (冠宇)
    "冠羽": "冠宇",
    "蘇冠羽": "冠宇",
    "冠雨": "冠宇",
    "蘇冠雨": "冠宇",
    "冠語": "冠宇",
    "蘇冠語": "冠宇",
    "冠禹": "冠宇",
    "蘇冠禹": "冠宇",
    "冠宇": "冠宇",
    "蘇冠宇": "冠宇",

    # 蕭宇傑 (宇傑)
    "宇杰": "宇傑",
    "蕭宇杰": "宇傑",
    "蕭蕭": "宇傑",
    "宇捷": "宇傑",
    "蕭宇捷": "宇傑",
    "雨傑": "宇傑",
    "蕭雨傑": "宇傑",
    "雨杰": "宇傑",
    "蕭雨杰": "宇傑",
    "宇潔": "宇傑",
    "蕭宇潔": "宇傑",
    "宇傑": "宇傑",
    "蕭宇傑": "宇傑",
}

SHORT_TO_FULL = {
    "子倫": "邱子倫",
    "倫廣": "袁倫廣",
    "才彥": "尹才彥",
    "銘聖": "林銘聖",
    "正宇": "楊正宇",
    "冠宇": "蘇冠宇",
    "宇傑": "蕭宇傑",
}

def normalize_member_name(input_name: str) -> Dict[str, Any]:
    """
    成員姓名自動錯字更正與標準化模組
    自動校正同音字、錯別字，並轉換為行事曆歷史慣例之 2 字習慣稱呼與 3 字全名。
    """
    clean_name = (input_name or "").strip()
    if not clean_name:
        return {
            "display_name": "",
            "full_name": "",
            "original_name": "",
            "was_corrected": False
        }

    # 1. 字典快速精準比對 (包含全名、簡稱與已知錯字)
    if clean_name in MEMBER_TYPO_MAP:
        short = MEMBER_TYPO_MAP[clean_name]
        full = SHORT_TO_FULL.get(short, short)
        was_corrected = (clean_name != short and clean_name != full)
        return {
            "display_name": short,
            "full_name": full,
            "original_name": clean_name,
            "was_corrected": was_corrected
        }

    # 2. 包含匹配 (例如「林銘聖同學」->「銘聖」)
    for typo, short in MEMBER_TYPO_MAP.items():
        if typo in clean_name:
            full = SHORT_TO_FULL.get(short, short)
            was_corrected = (clean_name != short and clean_name != full)
            return {
                "display_name": short,
                "full_name": full,
                "original_name": clean_name,
                "was_corrected": was_corrected
            }

    # 3. 拼音同音/近音模糊比對 (Pinyin Matcher)
    try:
        from pypinyin import lazy_pinyin
        input_pinyin = "".join(lazy_pinyin(clean_name))
        for full, short in LAB_MEMBERS.items():
            full_pinyin = "".join(lazy_pinyin(full))
            short_pinyin = "".join(lazy_pinyin(short))
            if input_pinyin == full_pinyin or input_pinyin == short_pinyin:
                return {
                    "display_name": short,
                    "full_name": full,
                    "original_name": clean_name,
                    "was_corrected": True
                }
            if short_pinyin in input_pinyin or input_pinyin in short_pinyin:
                return {
                    "display_name": short,
                    "full_name": full,
                    "original_name": clean_name,
                    "was_corrected": (clean_name != short and clean_name != full)
                }
    except Exception:
        pass

    # 4. 編輯距離 / 相似度模糊比對 (difflib SequenceMatcher)
    import difflib
    best_match = None
    best_score = 0.0
    for full, short in LAB_MEMBERS.items():
        score_full = difflib.SequenceMatcher(None, clean_name, full).ratio()
        score_short = difflib.SequenceMatcher(None, clean_name, short).ratio()
        max_s = max(score_full, score_short)
        if max_s > best_score:
            best_score = max_s
            best_match = (short, full)

    if best_score >= 0.5 and best_match:
        short, full = best_match
        return {
            "display_name": short,
            "full_name": full,
            "original_name": clean_name,
            "was_corrected": (clean_name != short and clean_name != full)
        }

    # 若完全無法匹配，保留原名稱
    return {
        "display_name": clean_name,
        "full_name": clean_name,
        "original_name": clean_name,
        "was_corrected": False
    }

def check_member_leave(member_name: str, target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    檢查特定成員於指定日期是否有請假紀錄（支援自動錯字更正與姓名標準化）
    """
    if target_date is None:
        target_date = datetime.date.today()

    target_str = target_date.strftime("%Y-%m-%d")
    today_res = get_today_leaves(target_date)
    leaves = today_res.get("leaves", [])

    norm = normalize_member_name(member_name)
    disp_name = norm["display_name"]
    full_name = norm["full_name"]
    orig_name = norm["original_name"]

    matched_leaves = []
    search_keys = {orig_name, disp_name, full_name}
    if len(disp_name) >= 2:
        search_keys.add(disp_name[-2:])

    for l in leaves:
        title = l.get("title", "")
        if any(k and k in title for k in search_keys):
            matched_leaves.append(l)

    return {
        "status": "success",
        "member": disp_name or member_name,
        "full_name": full_name or member_name,
        "original_name": orig_name,
        "was_corrected": norm["was_corrected"],
        "date": target_str,
        "is_on_leave": len(matched_leaves) > 0,
        "leave_records": matched_leaves
    }

def add_leave_event(member_name: str, date_str: str, start_time: str = "10:00", end_time: str = "17:00", reason: str = "") -> Dict[str, Any]:
    """
    自動為成員於 Google 行事曆新增請假活動
    - 自動錯字更正（如 銘璽/銘勝 -> 銘聖）
    - 嚴格依照歷史慣例格式：活動標題一律為 2 字習慣稱呼（如 銘聖、倫廣、正宇、子倫、才彥、冠宇、宇傑）
    - 時段預設符合實驗室在室規範：10:00 至 17:00，時區 Asia/Taipei
    """
    service = get_calendar_service()
    if not service:
        return {"status": "error", "message": "Google Calendar 服務未連線"}

    try:
        norm = normalize_member_name(member_name)
        event_title = norm["display_name"]
        full_name = norm["full_name"]
        was_corrected = norm["was_corrected"]
        original = norm["original_name"]

        # 格式轉換: 2026-09-18T10:00:00+08:00
        start_dt = f"{date_str}T{start_time}:00+08:00"
        end_dt = f"{date_str}T{end_time}:00+08:00"

        clean_reason = reason.strip() if reason else ""
        desc_parts = ["由 IRL Lab AI 助理自動登記"]
        if was_corrected:
            desc_parts.append(f"（自動更正輸入錯字：{original} ➔ {event_title}）")
        if clean_reason:
            desc_parts.append(f"事由: {clean_reason}")
        desc_text = " ".join(desc_parts)

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

        msg = f"已成功為 {event_title}（{full_name}）登記 {date_str} 請假行程（{start_time}～{end_time}）"
        if was_corrected:
            msg = f"已自動將錯字『{original}』更正為成員『{event_title}（{full_name}）』，並" + msg

        return {
            "status": "success",
            "message": msg,
            "event_id": created_event.get("id"),
            "html_link": created_event.get("htmlLink"),
            "display_name": event_title,
            "full_name": full_name,
            "was_corrected": was_corrected,
            "original_name": original,
            "date": date_str,
            "period": f"{start_time} ～ {end_time}"
        }
    except Exception as e:
        return {"status": "error", "message": f"新增請假活動失敗: {str(e)}"}

def cancel_leave_event(member_name: str, date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    取消特定成員於指定日期（或最近一筆）的請假活動並從 Google 日曆刪除（支援自動錯字更正）
    """
    service = get_calendar_service()
    if not service:
        return {"status": "error", "message": "Google Calendar 服務未連線"}

    try:
        norm = normalize_member_name(member_name)
        disp_name = norm["display_name"]
        full_name = norm["full_name"]
        orig_name = norm["original_name"]
        was_corrected = norm["was_corrected"]

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

        search_keys = {orig_name, disp_name, full_name}
        if len(disp_name) >= 2:
            search_keys.add(disp_name[-2:])

        matched = []
        for l in leaves:
            title = l.get("title", "")
            if any(k and k in title for k in search_keys):
                matched.append(l)

        if not matched:
            target_desc = f"{date_str} " if date_str else ""
            target_label = f"{disp_name}（{full_name}）" if disp_name != full_name else disp_name
            return {
                "status": "error",
                "message": f"未在行事曆找到 {target_label} {target_desc}的請假活動"
            }

        deleted_records = []
        for m in matched:
            event_id = m.get("id")
            if event_id:
                service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
                deleted_records.append(m)

        msg = f"已成功為 {disp_name}（{full_name}）取消 {len(deleted_records)} 筆請假行程，並已從 Google 日曆同步刪除"
        if was_corrected:
            msg = f"已自動將錯字『{orig_name}』更正為『{disp_name}（{full_name}）』，並" + msg

        return {
            "status": "success",
            "message": msg,
            "deleted_events": deleted_records,
            "display_name": disp_name,
            "full_name": full_name,
            "was_corrected": was_corrected,
            "original_name": orig_name
        }
    except Exception as e:
        return {"status": "error", "message": f"取消請假活動失敗: {str(e)}"}

