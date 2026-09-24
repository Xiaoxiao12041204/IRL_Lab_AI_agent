"""
實驗室智慧問答與知識庫檢索服務 (Lab Assistant Query Service)
支援：校友名冊、經費預算帳本、財產清冊、會計報銷法規、360度人物全景聯查、智慧延伸推薦與報帳合規防呆試算。
"""

import os
import sys
import json
import time
import difflib
import re

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass



CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) in ('connectors', 'core') else CURRENT_DIR
DATA_DIR = os.path.join(BASE_DIR, 'data')

CONNECTORS_DIR = os.path.join(BASE_DIR, 'connectors')
if os.path.exists(CONNECTORS_DIR) and CONNECTORS_DIR not in sys.path:
    sys.path.insert(0, CONNECTORS_DIR)

# 12 小時快取過期時間 (秒)
CACHE_TTL_SECONDS = 12 * 3600
_LAST_CHECK_TIME = 0

def check_and_auto_sync(force=False, max_age_seconds=CACHE_TTL_SECONDS):
    """
    檢查本地知識庫是否超過 12 小時未更新，若超時則以【背景執行緒】刷新 Wiki 快取。
    主查詢流程完全不等待網路，絕不卡死。
    """
    import threading
    global _LAST_CHECK_TIME
    now = time.time()

    # 避免短時間內重複觸發（30 分鐘檢查一次，減少連線頻率）
    if not force and (now - _LAST_CHECK_TIME < 1800):
        return False

    _LAST_CHECK_TIME = now
    wiki_cache_path = os.path.join(DATA_DIR, 'wiki_knowledge.json')
    need_sync = force

    if not os.path.exists(wiki_cache_path):
        need_sync = True
    else:
        file_age = now - os.path.getmtime(wiki_cache_path)
        if file_age > max_age_seconds:
            need_sync = True

    if need_sync:
        # ── 背景執行緒：主流程不等待，網路超時不影響查詢 ──
        def _bg_sync():
            try:
                from wiki_reader import sync_wiki_cache
                sync_wiki_cache()
            except Exception:
                pass  # 網路異常靜默忽略，下次觸發時再試

        t = threading.Thread(target=_bg_sync, daemon=True)
        t.start()

    return False

def load_json(filename):
    # 在載入知識庫時自動執行 12 小時過期檢查
    check_and_auto_sync()
    
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def _match_tokens_all(text, keyword):
    """檢查是否所有分詞皆出現在目標文字中 (AND 比對)"""
    if not keyword:
        return True
    tokens = [t.strip().lower() for t in keyword.strip().split() if t.strip()]
    if not tokens:
        return True
    text_lower = text.lower()
    return all(tok in text_lower for tok in tokens)

def _clean_category_keyword(keyword, stop_words):
    """
    通用類別詞過濾器：
    當使用者傳入「校友名冊」、「設備清冊」、「歷屆論文」、「現役成員」等大類別通用詞時，
    自動剝除通用詞。若剝除後為空字串，代表使用者需要的是「該類別的完整清冊」；
    若剝除後仍有詞（如「資工系 校友名冊」->「資工系」），則以實質關鍵字進行精準檢索。
    """
    kw = (keyword or "").strip()
    if not kw:
        return ""
    cleaned = kw
    sorted_stops = sorted(stop_words, key=len, reverse=True)
    import re
    for w in sorted_stops:
        cleaned = re.sub(re.escape(w), "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def query_members(keyword=""):
    """
    從「使用中設備的所有者清冊」(lab_properties.json) 動態獲取現役實驗室成員名單與主機配置。
    """
    prop_data = load_json('lab_properties.json') or []
    if not prop_data:
        return {"status": "error", "message": "找不到設備財產清冊資料庫", "suggestions": []}
    
    # 篩選使用中設備之所有者（排除公用電腦與一般公用設備）
    members_map = {}
    for item in prop_data:
        user = item.get("使用者")
        status = item.get("設備狀態")
        if user and status == "使用中" and "公用" not in str(user):
            user_clean = str(user).strip()
            if user_clean not in members_map:
                loc = str(item.get("放置位置", 70640))
                members_map[user_clean] = {
                    "中文姓名": user_clean,
                    "身分": "現役成員",
                    "所在研究室": f"{loc} 研究室"
                }
    
    all_members = list(members_map.values())
    
    # 支援「現役成員」、「成員名冊」等通用關鍵字直接回傳完整清冊
    MEMBER_STOPWORDS = [
        "現役成員名冊", "實驗室成員名冊", "現役成員名單", "實驗室成員名單",
        "現役成員", "實驗室成員", "成員名冊", "成員名單", "所有成員", "全部成員",
        "現在成員", "現有成員", "成員有哪些", "成員有誰", "有哪些成員",
        "成員", "名冊", "名單", "誰", "members", "member"
    ]
    effective_kw = _clean_category_keyword(keyword, MEMBER_STOPWORDS)
    
    if not effective_kw:
        # 挑選前 2~3 位成員作為建議範例
        sample_names = [m.get("中文姓名", "") for m in all_members[:3] if m.get("中文姓名")]
        sample_str = "、".join(sample_names) if sample_names else "邱子倫"
        return {
            "status": "success",
            "source": "現役成員名冊",
            "total": len(all_members),
            "items": all_members,
            "suggestions": [
                f"查詢特定現役成員（如：{sample_str}）的 360 度個人檔案與保管設備",
                "查詢 70640 實驗室電腦與設備財產清冊",
                "查詢歷屆已畢業校友名冊與畢業論文"
            ]
        }
        
    matches = []
    for m in all_members:
        full_str = f"{m.get('中文姓名')} {m.get('身分')} {m.get('所在研究室')}"
        if _match_tokens_all(full_str, effective_kw):
            matches.append(m)
            
    suggestions = []
    if matches:
        first_person = matches[0].get("中文姓名", "")
        suggestions.append(f"查詢 {first_person} 的 360 度個人檔案 (主機/專案/設備)")
        suggestions.append(f"查看 {first_person} 保管的實驗室電腦與財產設備")
        suggestions.append(f"檢索 {first_person} 相關之研究主題與專案報告")
    else:
        suggestions.append("查看所有使用中設備之成員清冊")
        suggestions.append("查詢歷屆畢業校友名冊")

    return {
        "status": "success",
        "keyword": keyword,
        "source": "使用中設備清冊 (lab_properties.json)",
        "count": len(matches),
        "results": matches,
        "suggestions": suggestions
    }

def query_alumni(keyword=""):
    data = load_json('lab_alumni.json')
    if not data:
        return {"status": "error", "message": "找不到校友資料庫", "suggestions": []}
    
    # 支援「校友名冊」、「歷屆校友」、「畢業校友」等通用關鍵字直接回傳完整名冊
    ALUMNI_STOPWORDS = [
        "歷屆畢業校友名冊", "歷屆校友名冊", "畢業校友名冊", "歷屆畢業校友",
        "畢業校友清冊", "歷屆校友清冊", "歷屆畢業生", "畢業校友", "歷屆校友",
        "校友名冊", "校友清冊", "校友名單", "所有校友", "全部校友", "學長姐名單",
        "學長姐", "畢業生", "校友", "名冊", "名單", "alumni", "alumnus"
    ]
    effective_kw = _clean_category_keyword(keyword, ALUMNI_STOPWORDS)

    if not effective_kw:
        return {
            "status": "success",
            "total": len(data),
            "items": data,
            "suggestions": ["查詢特定年份畢業校友 (如 112年)", "查詢特定指導教授學生", "查詢某位校友的 360度全景資料"]
        }
    
    matches = []
    for item in data:
        cname = item.get("中文姓名", "")
        ename = item.get("英文姓名", "")
        dept = item.get("系所", "")
        field = item.get("專長領域", "")
        year = str(item.get("入學年度", "")) + str(item.get("畢業年度", "")) + str(item.get("畢業年份(民國)", ""))
        full_str = f"{cname} {ename} {dept} {year} {field}"
        
        if _match_tokens_all(full_str, effective_kw):
            matches.append(item)
            
    # 動態產生延伸建議
    suggestions = []
    if matches:
        first_person = matches[0].get("中文姓名", "")
        suggestions.append(f"查詢 {first_person} 的個人檔案與研究主題 (論文/設備/經費)")
        suggestions.append(f"檢索 {first_person} 的碩士畢業論文與口試投影片")
        suggestions.append(f"查看 {first_person} 目前保管的實驗室財產設備")
    else:
        suggestions.append("嘗試使用同音字或英文姓名再次搜尋")
        suggestions.append("查看歷屆校友總名冊")

    return {
        "status": "success",
        "keyword": keyword,
        "count": len(matches),
        "results": matches,
        "suggestions": suggestions
    }

def query_properties(keyword=""):
    data = load_json('lab_properties.json')
    if not data:
        return {"status": "error", "message": "找不到財產清冊資料庫", "suggestions": []}
    
    # 支援「設備清冊」、「財產清冊」、「全部設備」等通用關鍵字直接回傳完整清冊
    PROP_STOPWORDS = [
        "實驗室財產設備清冊", "實驗室設備財產清冊", "實驗室財產清冊", "實驗室設備清冊",
        "財產設備清冊", "設備財產清冊", "財產清冊", "設備清冊", "所有設備", "全部設備",
        "所有財產", "全部財產", "實驗室設備", "實驗室財產", "硬體清冊", "電腦清冊",
        "設備列表", "財產列表", "設備", "財產", "清冊", "property", "properties"
    ]
    effective_kw = _clean_category_keyword(keyword, PROP_STOPWORDS)

    if not effective_kw:
        return {
            "status": "success",
            "data": data,
            "suggestions": ["查詢伺服器與主機設備", "查詢放置在 70523 的設備", "查詢特定成員保管的財產"]
        }
    
    matches = []
    items = data.get("財產列表", []) if isinstance(data, dict) else data
    for item in items:
        name = str(item.get("物品名稱", "") or item.get("設備類型", "") or item.get("廠牌與型號", "") or "")
        custodian = str(item.get("保管人", "") or item.get("使用者", "") or "")
        loc = str(item.get("放置位置", "") or "")
        sn = str(item.get("財產編號", "") or "")
        spec = str(item.get("詳細規格", "") or "")
        ip = str(item.get("網路IP", "") or "")
        status = str(item.get("設備狀態", "") or "")
        note = str(item.get("備註", "") or "")
        full_prop_str = f"{name} {custodian} {loc} {sn} {spec} {ip} {status} {note}"
        
        if _match_tokens_all(full_prop_str, effective_kw):
            matches.append(item)
            
    suggestions = []
    if matches:
        first_item = matches[0]
        c = first_item.get("保管人") or first_item.get("使用者")
        first_loc = first_item.get("放置位置")
        if c:
            suggestions.append(f"查詢保管人 {c} 名下的所有實驗室設備")
        suggestions.append("查詢報帳法規中『1萬元以上財產列管與登錄流程』")
        if first_loc:
            suggestions.append(f"查詢 {first_loc} 放置之其他周邊設備清冊")
        else:
            suggestions.append("查詢 70640 放置之其他周邊設備清冊")
    else:
        suggestions.append("查詢實驗室全部伺服器與電腦清冊")
        suggestions.append("查詢財產報廢與交接規定")

    return {
        "status": "success",
        "keyword": keyword,
        "count": len(matches),
        "results": matches,
        "suggestions": suggestions
    }

def query_budget(keyword=""):
    """
    經費與公用經費查詢：改為直接連線 MediaWiki 知識庫（「公用經費清單」與「報帳」專區）檢索，
    取得最新 Wiki 頁面內文、Google 試算表來源與相關核銷章節。
    """
    import wiki_reader
    
    # 1. 優先至 MediaWiki 取得「公用經費清單」頁面
    wiki_fund_page = wiki_reader.wiki_get_page("公用經費清單")
    fund_url = "https://yzuirl.synology.me/mediawiki/index.php/%E5%85%AC%E7%94%A8%E7%B6%93%E8%B2%BB%E6%B8%85%E5%96%AE"
    
    # 2. 同步檢索 Wiki 報帳與經費相關條目
    search_kw = f"經費 {keyword}".strip() if keyword else "公用經費"
    wiki_search_res = wiki_reader.wiki_search(search_kw)
    
    # 3. 讀取本地帳本作為結構化歷史收支比對資料 (作為補充明細)
    ledger_data = load_json('lab_funds_ledger.json') or []
    latest_balance = ledger_data[-1].get("結餘", 0) if ledger_data else 0
    latest_date = ledger_data[-1].get("日期", "") if ledger_data else ""
    
    matched_ledger = []
    total_change = 0.0
    
    # 判斷 keyword 是否為純數字或筆數請求（如 "5", "10", "15", "5筆", "最近5筆"）
    is_limit = False
    limit_num = 10
    clean_kw = str(keyword).strip()
    
    import re
    m_num = re.match(r'^(?:最近)?(\d+)(?:筆|條)?$', clean_kw)
    if m_num:
        is_limit = True
        limit_num = int(m_num.group(1))
    elif not clean_kw:
        is_limit = True
        limit_num = 10

    if is_limit and ledger_data:
        # 取最近 limit_num 筆（依時間先後遞進呈現）
        matched_ledger = ledger_data[-limit_num:]
    elif clean_kw and ledger_data:
        for entry in ledger_data:
            note = str(entry.get("備註", "") or "")
            date_str = str(entry.get("日期", "") or "")
            item_str = str(entry.get("項目", "") or "")
            full_entry_str = f"{note} {date_str} {item_str}"
            if _match_tokens_all(full_entry_str, clean_kw):
                matched_ledger.append(entry)
                amt = entry.get("收支金額(增減)")
                if amt is not None:
                    try:
                        total_change += float(amt)
                    except Exception:
                        pass

    # 嚴格依照日期先後順序（由先至後、由舊到新）排序，確保時間遞進一致
    matched_ledger.sort(key=lambda x: str(x.get("日期") or "0000-00-00"))

    # 動態產生經費延伸建議 (過濾筆數等純數字關鍵字)
    fund_suggestions = []
    if is_limit or not clean_kw or clean_kw.isdigit():
        fund_suggestions.append("查詢便當餐費、差旅與耗材之元智會計報帳核銷標準與上限")
        fund_suggestions.append("進行單筆經費報帳合規防呆試算 (如便當上限、估價單門檻、境外電商營業稅)")
        fund_suggestions.append("查詢特定成員名下之經費收支紀錄 (如：蕭宇傑、邱子倫)")
    else:
        fund_suggestions.append(f"查詢『{clean_kw}』相關會計報銷法規與核銷標準")
        fund_suggestions.append(f"試算採購『{clean_kw}』之報帳防呆與必備單據檢核")
        fund_suggestions.append("查看實驗室公用經費最新總結餘與近 10 筆收支")

    return {
        "status": "success",
        "keyword": keyword,
        "current_balance": latest_balance,
        "latest_update_date": latest_date,
        "total_amount_change": total_change if keyword and not is_limit else None,
        "matched_ledger_count": len(matched_ledger),
        "ledger_details": matched_ledger,
        "suggestions": fund_suggestions
    }

query_funds = query_budget


def query_accounting_rules(question=""):
    clean_q = str(question).strip().lower()

    # ── 請假規定：與報帳完全分流，直接查 Wiki 請假條目 ──────────────────────
    LEAVE_KEYWORDS = ["請假", "出席", "出勤", "罰款", "缺席", "補假", "留在實驗室",
                      "在室時間", "工作時間", "開學時間", "寒暑假時間"]
    if any(kw in clean_q for kw in LEAVE_KEYWORDS):
        wiki_data = load_json('wiki_knowledge.json') or {}
        leave_content = wiki_data.get("請假", "")
        if leave_content:
            formatted = (
                "### 🏛️ 實驗室請假規則\n\n"
                "* **開學期間**：上午 10:00–12:00、下午 13:00–17:00（不上課時間須待在實驗室）\n"
                "* **寒暑假期間**：上午 11:00–12:00、下午 13:00–17:00\n"
                "* **請假方式**：須事先透過 Google 行事曆進行請假手續\n"
                "* **未請假懲處**：無故缺席者罰款一次 500 元起，均分給當時出席同學\n\n"
                "💡 **您可能還想了解**\n\n"
                "* 查詢出差申請流程（出差與一般請假不同，需另填出差申請單）\n"
                "* 查詢實驗室報帳規定（採購、雜項費、研究助理費等）\n"
                "* 查詢 BlackMamba 回訊系統使用說明"
            )
            return {
                "status": "success",
                "topic": "請假規定",
                "formatted_response": formatted
            }
        return {"status": "error", "message": "找不到請假規定資料，請直接查閱 MediaWiki", "suggestions": []}


    # ── 報帳規定：查 accounting_rules.json ────────────────────────────────────
    data = load_json('accounting_rules.json')
    if not data:
        return {"status": "error", "message": "找不到報帳法規資料庫", "suggestions": []}

    PORTAL_FLOW_KEYWORDS = ["portal", "建立採購單", "採購單建立", "填單流程", "操作流程", "系統填單", "報帳步驟", "如何填單", "自辦採購", "電子單"]
    is_portal_flow = any(kw in clean_q for kw in PORTAL_FLOW_KEYWORDS)

    if is_portal_flow:
        portal_formatted = (
            "### 🖥️ 元智大學 Portal 報帳與採購單建立操作流程\n\n"
            "透過元智大學預算會計系統建立各類報銷與採購電子單據，請依循以下標準步驟辦理：\n\n"
            "### 📌 進入預算會計系統\n"
            "* 登入元智大學入口網站（Portal）。\n"
            "* 點選進入「預算會計系統」。\n"
            "* 依據申報項目選擇對應單據類別（自辦採購單、零用金申請單、雜項單或薪資單）。\n\n"
            "### 📌 填寫品項與採購細節\n"
            "* **採購品類別選取**：消耗品與耗材請選「A. 一般消耗品」；設備儀器請選「C. 一般設備」。\n"
            "* **人員與廠商資料**：請購人與驗收人先填入指導教授老師資料，待系統通過審核後再行印單蓋章。\n"
            "* **支出說明填寫**：明確註明採購品名與用途（例如：線上 AI 服務應用費用、耗材耗損補充、研討會差旅交通等）。\n\n"
            "### 📌 設備列管與大型採購程序\n"
            "* **財產判定**：若為設備採購，系統送出後會先由學校財管組判定是否可認列為財產。\n"
            "* **驗收與財產標籤**：通過後開始跑驗收程序，需依規定至財管組領取並黏貼財產標籤。\n"
            "* **估價單門檻**：採購金額 1 萬～10 萬元需檢附 1 家估價單；10 萬元以上需檢附 2 家以上估價單進行公開比價。\n\n"
            "### 📌 列印單據與簽辦核銷流程\n"
            "* **列印正式表單**：系統送出電子單後，至 Portal 列印帶有專屬條碼之「支出憑證黏存單」與相關表單。\n"
            "* **檢附原始憑證**：附上原始發票或收據（若為老師代墊需附信用卡帳單；若發票未打統編需手寫補正元智統編 00966880 並蓋章）。\n"
            "* **實體核章流程**：備齊單據依序簽辦：填單經辦人 ➔ 指導教授郭文興老師 ➔ 系主任劉維昇 ➔ 送交會計室審核撥款。"
        )
        return {
            "status": "success",
            "question": question,
            "topic": "Portal 報帳與採購單操作流程",
            "results": data,
            "rules": data,
            "formatted_response": portal_formatted,
            "suggestions": [
                "進行單筆經費報帳合規防呆試算 (如便當上限、估價單門檻、境外電商營業稅)",
                "查詢 OpenAI / Grok / GitHub 境外電商免扣繳專用統編",
                "查詢國內外差旅費與出席會議核銷必備單據清單"
            ]
        }

    is_general = not clean_q or clean_q in [
        "報帳", "規定", "報帳規定", "會計", "會計規定", "核銷", "規則", "全", "all",
        "說明", "流程", "法規", "報帳流程", "一般規定", "注意事項", "怎麼報帳", "如何報帳"
    ]
    
    if is_general:
        general_formatted = (
            "### 🏛️ 元智大學會計報帳與核銷核心規範\n\n"
            "### 📌 發票與單據抬頭基本規範\n"
            "* **學校統一編號**：一律填寫元智大學統編 `00966880`。\n"
            "* **發票聯式要求**：請索取雙聯式發票；若取得三聯式發票需於黏存單註明延遲或特殊原因並蓋主持人章。\n"
            "* **核銷期程限制**：單據開立日起算 4 個月內須完成報銷，逾期需填延遲說明書並由主持人蓋章。\n"
            "* **核章簽辦流程**：填單經辦人 ➔ 郭文興老師 ➔ 劉維昇主任 ➔ 會計室。\n\n"
            "### 🍽️ 會議餐費與便當上限\n"
            "* **金額上限**：每人每餐上限 100～120 元。\n"
            "* **必備單據清單**：支出憑證黏存單、**會議簽到名冊**、免用統一發票收據或發票、零用金申請單。\n\n"
            "### 🖥️ 採購金額門檻與估價單\n"
            "* **未達 1 萬元**：小額採購免附估價單。\n"
            "* **1 萬～10 萬元**：中額採購需檢附 1 家估價單，並申請財產標籤列管。\n"
            "* **10 萬元以上**：大額採購需檢附 2 家以上估價單進行公開比價。\n"
            "* **境外電商勞務（OpenAI / GitHub / Grok 等）**：需加計 5% 營業稅，填寫專用免扣繳統編並檢附信用卡帳單。\n\n"
            "### 🚗 差旅費與兼任助理薪資（請假與報帳關聯）\n"
            "* **差旅請假出差手續**：出差前必須先於 Portal 填寫出差申請單（公假手續），填單日期不可晚於出差日；需檢附交通票根、議程表、出差紀錄表與與會合照。\n"
            "* **兼任助理出勤薪資**：專案人員需完成正式約用，每月薪資需檢附收據、聘用申請表與出勤日誌（08:00 前簽到退）；若有請假或補簽需檢附主管核准之請假單或補簽到退單。"
        )
        return {
            "status": "success",
            "question": question,
            "is_general_overview": True,
            "results": data,
            "rules": data,
            "formatted_response": general_formatted,
            "suggestions": [
                "進行單筆經費報帳合規防呆試算 (如便當上限、估價單門檻、境外電商營業稅)",
                "查詢 OpenAI / Grok / GitHub 境外電商免扣繳專用統編",
                "查詢國內外差旅費與出席會議核銷必備單據清單"
            ]
        }
        
    matches = []
    if isinstance(data, dict):
        for main_cat, cat_data in data.items():
            if main_cat == "快速啟動步驟":
                if _match_tokens_all(str(cat_data), question):
                    matches.append({"主類別": main_cat, "內容": cat_data})
                continue
            
            items = cat_data.get("報帳項目清單", {}) if isinstance(cat_data, dict) else {}
            for item_name, item_details in items.items():
                full_text = f"{main_cat} {item_name} {json.dumps(item_details, ensure_ascii=False)}"
                if _match_tokens_all(full_text, question):
                    matches.append({
                        "主類別": main_cat,
                        "項目名稱": item_name,
                        "詳細規則": item_details
                    })
    elif isinstance(data, list):
        for r in data:
            if _match_tokens_all(json.dumps(r, ensure_ascii=False), question):
                matches.append(r)

    # 為特定匹配結果自動組裝純文字結構化 formatted_response，避免前端 LLM 拼裝表格與 <br>
    formatted_blocks = []
    if matches:
        for m in matches[:3]:
            name = m.get("項目名稱", m.get("主類別", "報帳項目"))
            details = m.get("詳細規則", {})
            block = f"### 📌 {name}\n"
            if isinstance(details, dict):
                steps = details.get("電子單操作步驟", [])
                if steps:
                    block += "* **電子單操作步驟**：\n"
                    for s in steps:
                        clean_s = re.sub(r'<\s*/?\s*br\s*/?>', ' ', str(s), flags=re.IGNORECASE).strip()
                        clean_s = re.sub(r'^\d+[\.、]\s*', '', clean_s)
                        block += f"  ➔ {clean_s}\n"
                reqs = details.get("實體憑證需求清單", [])
                if reqs:
                    block += "* **實體憑證需求清單**：\n"
                    for r in reqs:
                        clean_r = re.sub(r'<\s*/?\s*br\s*/?>', ' ', str(r), flags=re.IGNORECASE).strip()
                        clean_r = re.sub(r'^\d+[\.、]\s*', '', clean_r)
                        block += f"  ➔ {clean_r}\n"
                note = details.get("特別備註", "")
                if note:
                    clean_n = re.sub(r'<\s*/?\s*br\s*/?>', ' ', str(note), flags=re.IGNORECASE).strip()
                    block += f"* **特別備註**：{clean_n}\n"
            formatted_blocks.append(block)

    formatted_str = "\n".join(formatted_blocks).strip() if formatted_blocks else None
            
    return {
        "status": "success",
        "question": question,
        "count": len(matches),
        "results": matches if matches else data,
        "formatted_response": formatted_str,
        "suggestions": [
            f"依據『{question}』進行情境式報帳防呆試算 (輸入金額與廠商)",
            "查詢 MediaWiki 上的最新請假與差旅補充規定",
            "查詢元智大學統編 (00966880) 與報單填寫流程"
        ]
    }

def query_thesis(keyword=""):
    data = load_json('thesis_index.json')
    if not data:
        return {"status": "error", "message": "找不到論文索引資料庫", "suggestions": []}

    # 支援「歷屆論文」、「畢業論文」、「碩士論文」、「論文清冊」等通用關鍵字直接回傳完整清冊
    THESIS_STOPWORDS = [
        "歷屆碩士畢業論文清冊", "歷屆畢業論文清冊", "碩士畢業論文清冊", "歷屆碩士論文清冊",
        "歷屆論文清冊", "畢業論文清冊", "碩士論文清冊", "論文清冊", "論文名冊", "論文列表",
        "歷屆畢業論文", "碩士畢業論文", "歷屆碩士論文", "歷屆論文", "畢業論文", "碩士論文",
        "全部論文", "所有論文", "論文", "清冊", "theses", "thesis"
    ]
    effective_kw = _clean_category_keyword(keyword, THESIS_STOPWORDS)

    if not effective_kw:
        return {
            "status": "success",
            "total": len(data),
            "items": data,
            "suggestions": ["搜尋無人機相關畢業論文", "搜尋物聯網與定位演算法論文", "依作者姓名查詢歷屆論文"]
        }

    kw = effective_kw.strip().lower()
    matches = []

    kw_pinyin = ""
    try:
        from pypinyin import lazy_pinyin
        kw_pinyin = "".join(lazy_pinyin(kw))
    except Exception:
        pass

    for t in data:
        title = t.get("title", "")
        etitle = t.get("english_title", "")
        author = t.get("author", "")
        eauthor = t.get("english_author", "")
        year = str(t.get("year_roc", ""))
        keywords = " ".join(t.get("keywords", []))
        
        full_text = f"{title} {etitle} {author} {eauthor} {year} {keywords}".lower()
        
        # 1. 多分詞 AND 比對
        if _match_tokens_all(full_text, effective_kw):
            matches.append({"score": 1.0, "thesis": t})
            continue
            
        ratio_title = difflib.SequenceMatcher(None, kw, title.lower()).ratio()
        ratio_author = difflib.SequenceMatcher(None, kw, author.lower()).ratio()
        
        pinyin_ratio = 0.0
        if kw_pinyin:
            t_pinyin = "".join(lazy_pinyin(title))
            a_pinyin = "".join(lazy_pinyin(author))
            if kw_pinyin in t_pinyin or kw_pinyin in a_pinyin:
                pinyin_ratio = 0.85
            else:
                pinyin_ratio = max(
                    difflib.SequenceMatcher(None, kw_pinyin, t_pinyin).ratio(),
                    difflib.SequenceMatcher(None, kw_pinyin, a_pinyin).ratio()
                )
                
        best_score = max(ratio_title, ratio_author, pinyin_ratio)
        if best_score >= 0.45:
            matches.append({"score": round(best_score, 3), "thesis": t})
            
    # 若有完全匹配 (score == 1.0)，過濾掉低相似度的模糊雜訊
    exact_matches = [m for m in matches if m["score"] == 1.0]
    if exact_matches:
        matches = exact_matches
    else:
        matches.sort(key=lambda x: x["score"], reverse=True)
        
    raw_results = [m["thesis"] for m in matches]
    
    # 動態補全本機 Z 槽路徑與自動讀取摘要預覽 (若為特定成員/前 1~3 筆查詢)
    has_z_drive = os.path.exists("Z:/") or os.path.exists("Z:\\")
    results = []
    for idx, t in enumerate(raw_results):
        item = dict(t)
        if has_z_drive and "nas_path" in item:
            item["local_path"] = item["nas_path"].replace("/IRLshare/", "Z:\\").replace("/", "\\")
            
        # 若為精準成員查詢或前 1~2 筆結果，自動讀取論文摘要並提取至 thesis_viewer/
        if idx < 2:
            try:
                import nas_reader
                # 自動主動提取檔案至 thesis_viewer/ (供 IDE 直接點擊開啟，並精準提取真實中英文摘要正文)
                author_name = item.get("author", "研究生")
                dl_res = nas_reader.nas_download_file_for_viewing(item.get("nas_path", ""), "論文", f"{author_name}_碩士論文")
                if dl_res.get("status") == "success":
                    item["auto_extracted_file"] = dl_res.get("file_name")
                    item["local_viewer_path"] = dl_res.get("file_path")
                    if dl_res.get("chinese_abstract"):
                        item["chinese_abstract"] = dl_res.get("chinese_abstract")
                    if dl_res.get("english_abstract"):
                        item["english_abstract"] = dl_res.get("english_abstract")
                    if dl_res.get("preview"):
                        item["abstract_preview"] = dl_res.get("preview")

                if not item.get("abstract_preview"):
                    read_res = nas_reader.nas_read_file(item.get("nas_path", ""), "論文", max_pages=15)
                    if read_res.get("status") == "success":
                        content_str = read_res.get("content", "")
                        item["abstract_preview"] = content_str[:1200]
            except Exception:
                pass
        results.append(item)
    
    # 動態產生個性化深度延伸建議 (根據該成員資料夾實際存在的檔案與論文核心技術)
    suggestions = []
    if results:
        first_t = results[0]
        auth = first_t.get("author", "")
        title = first_t.get("title", "")
        keywords = first_t.get("keywords", [])
        
        # 1. 偵測該成員資料夾內實際存在的其他檔案或子目錄
        folder_items = []
        z_folder = first_t.get("local_path")
        if z_folder and os.path.exists(z_folder):
            try:
                folder_items = os.listdir(z_folder)
            except Exception:
                pass
        elif os.path.exists(f"/mnt/z/畢業論文/{auth}"):
            try:
                folder_items = os.listdir(f"/mnt/z/畢業論文/{auth}")
            except Exception:
                pass
                
        # 根據實際資料夾檔案產生延伸建議
        has_sim = any("模擬" in x or "sim" in x.lower() or ".awk" in x for x in folder_items)
        has_data = any("數據" in x or "圖" in x or ".xlsx" in x or "data" in x.lower() for x in folder_items)
        has_demo = any("demo" in x.lower() or "影片" in x for x in folder_items)
        has_ppt = any("投影片" in x or "ppt" in x.lower() or "簡報" in x for x in folder_items)
        
        # 提煉具體技術主題詞
        core_tech = keywords[0] if keywords and keywords[0] != auth else (keywords[1] if len(keywords) > 1 and keywords[1] != auth else "核心機制")
        
        # 組合 3 個完全不同面向的深度問題
        suggestions.append(f"深入解析論文中「{core_tech}」的演算法數學推導與關鍵參數設計")
        
        if has_sim:
            suggestions.append(f"檢視該資料夾內收錄的 NS2 模擬原始碼、腳本與網路拓撲設定")
        elif has_data:
            suggestions.append(f"檢視該資料夾內收錄的實驗數據試算表與效能統計原始圖表")
        elif has_demo:
            suggestions.append(f"了解該成員資料夾內留存的 Demo 實作影片與系統展示")
        elif has_ppt:
            suggestions.append(f"探討口試簡報 (PPTX) 中針對口試委員與教授提問的重點回應")
        else:
            suggestions.append(f"了解該論文第三章所提系統架構與狀態轉移流程")
            
        suggestions.append(f"比較此研究與實驗室同領域其他學長姐論文的技術演進與突破")
    else:
        suggestions.append("使用同音字或研究關鍵字再次檢索")
        suggestions.append("列出歷屆所有碩士畢業論文清冊")
    
    return {
        "status": "success",
        "keyword": keyword,
        "count": len(results),
        "results": results,
        "suggestions": suggestions
    }

def query_wiki(keyword=""):
    """查詢 MediaWiki 實驗室維基百科 (包含請假規定、報帳細則、助理約用、BlackMamba 等)"""
    try:
        from wiki_reader import wiki_search, wiki_get_page, wiki_list_pages
        if not keyword:
            pages = wiki_list_pages()
            return {
                "status": "success",
                "total_pages": len(pages),
                "pages": pages,
                "suggestions": ["查詢請假出勤規範", "查詢境外電商 (OpenAI/Grok) 統編", "查詢研究助理約用流程"]
            }
        res = wiki_search(keyword)
        if isinstance(res, dict):
            res["suggestions"] = [
                f"查看『{keyword}』之詳細頁面全文",
                "進行相關項目的報帳合規防呆試算",
                "查詢相關主題之歷屆產學與論文報告"
            ]
        return res
    except Exception as e:
        return {"status": "error", "message": f"MediaWiki 查詢失敗: {e}", "suggestions": []}

# =========================================================================
# 新增功能 1：360 度人物/專案全景速查 (query_person_360)
# =========================================================================
def query_person_360(person_name):
    """
    一鍵跨 5 大資料庫 (現役成員、校友名冊、論文索引、設備清冊、經費帳本) 聯查個人 360 度全景資訊。
    """
    name = person_name.strip()
    if not name:
        return {"status": "error", "message": "請提供欲查詢之成員姓名", "suggestions": []}

    profile = {
        "query_name": name,
        "basic_info": None,
        "is_active_member": False,
        "thesis_info": [],
        "managed_properties": [],
        "budget_records": [],
        "summary": {}
    }

    # 1. 優先查現役成員資料庫，若無則查校友/基本資料庫
    mem_res = query_members(name)
    if mem_res.get("status") == "success" and mem_res.get("results"):
        profile["basic_info"] = mem_res["results"][0]
        profile["is_active_member"] = True
        profile["all_matched_members"] = mem_res["results"]
    else:
        alumni_res = query_alumni(name)
        if alumni_res.get("status") == "success" and alumni_res.get("results"):
            profile["basic_info"] = alumni_res["results"][0]
            profile["all_matched_alumni"] = alumni_res["results"]

    # 2. 查論文資料庫 (嚴格過濾為該作者的論文，絕對嚴禁將他人論文誤植給現役成員)
    thesis_res = query_thesis(name)
    if thesis_res.get("status") == "success" and thesis_res.get("results"):
        exact_author_theses = [
            t for t in thesis_res["results"]
            if name.lower() in t.get("author", "").lower() or name.lower() in t.get("english_author", "").lower()
        ]
        profile["thesis_info"] = exact_author_theses

    # 3. 查財產清冊
    prop_res = query_properties(name)
    if prop_res.get("status") == "success" and prop_res.get("results"):
        profile["managed_properties"] = prop_res["results"]

    # 4. 查經費帳本 (結合 Wiki 來源與收支備註)
    budget_res = query_budget(name)
    if budget_res.get("status") == "success":
        profile["budget_records"] = budget_res.get("ledger_details", [])
        profile["budget_wiki_source"] = budget_res.get("wiki_url")



    # 彙總摘要
    cname = profile["basic_info"].get("中文姓名") if profile["basic_info"] else name
    has_thesis = len(profile["thesis_info"]) > 0
    if has_thesis:
        thesis_title = profile["thesis_info"][0].get("title", "已登錄論文")
    elif profile["is_active_member"]:
        thesis_title = "在學研究中（尚未發表畢業論文）"
    else:
        thesis_title = "無登錄論文"

    prop_count = len(profile["managed_properties"])
    budget_count = len(profile["budget_records"])

    if profile["is_active_member"]:
        role = profile["basic_info"].get("身分", "現役成員")
        room = profile["basic_info"].get("所在研究室", "70640 研究室")
        dept_and_year_str = f"{role} ({room})"
    else:
        grad_year = profile["basic_info"].get("畢業年份(民國)") or profile["basic_info"].get("畢業年度") if profile["basic_info"] else None
        dept = profile["basic_info"].get("系所", "") if profile["basic_info"] else ""
        dept_and_year_str = f"{dept} (民國 {grad_year} 年畢業)" if grad_year else ("在學/未註明畢業年份" if profile["basic_info"] else "非名冊登錄校友或在學成員")

    profile["summary"] = {
        "name": cname,
        "dept_and_year": dept_and_year_str,
        "thesis_title": thesis_title,
        "property_count": f"名下保管 {prop_count} 件實驗室財產設備",
        "budget_activity_count": f"經費帳本相關收支紀錄共 {budget_count} 筆"
    }

    # 動態產生精準建議（嚴格依據是否已有論文產出推薦）
    suggestions = []
    if has_thesis:
        suggestions.append(f"提取並檢視 {cname} 的碩士口試簡報 (PPTX)")
        if prop_count > 0:
            suggestions.append(f"查看 {cname} 保管的 {prop_count} 件設備詳細清單與放置地點")
        suggestions.append(f"查詢與 {cname} 同屆或相同研究主題之歷屆論文")
    else:
        if prop_count > 0:
            suggestions.append(f"查看 {cname} 保管的 {prop_count} 件設備詳細清單與放置地點")
        suggestions.append("查詢 70640 實驗室電腦與設備財產清冊")
        suggestions.append("查詢歷屆已畢業校友名冊與畢業論文")

    return {
        "status": "success",
        "data": profile,
        "suggestions": suggestions
    }

# =========================================================================
# 新增功能 5：報帳規章情境式互動試算與防呆檢核顧問 (evaluate_expense_compliance)
# =========================================================================
def evaluate_expense_compliance(item_name="", amount=0.0, vendor_type="國內", is_foreign=False):
    """
    情境式報帳合規防呆試算顧問：
    - 金額門檻判定 (資本門/財產列管、估價單張數、招標門檻)
    - 餐費便當限額防呆 (便當 100~120元/人、會議名冊)
    - 統編防呆 (元智大學統編 00966880、境外電商專屬免扣繳統編)
    - 稅額試算 (境外電商 5% 營業稅加計)
    - 應備單據清單檢核
    """
    try:
        amt = float(amount)
    except Exception:
        amt = 0.0

    item_kw = str(item_name).strip()
    is_foreign = bool(is_foreign or "境外" in vendor_type or "國外" in vendor_type or any(f in item_kw.lower() for f in ["openai", "grok", "github", "aws", "google", "chatgpt"]))

    checklist = []
    warnings = []
    required_documents = ["支出憑證黏存單 / 報銷單 (Portal 產生)", "原始發票 / 電子收據"]
    tax_info = {"tax_rate": 0.0, "estimated_tax": 0.0, "total_payable": amt}

    # 1. 境外電商與稅額試算
    if is_foreign:
        tax_info["tax_rate"] = 0.05
        tax_info["estimated_tax"] = round(amt * 0.05, 2)
        tax_info["total_payable"] = round(amt * 1.05, 2)
        warnings.append("【境外電商專屬提醒】：境外勞務採購需申報 5% 營業稅 (外加)，請依元智會計室規定填寫境外電商專用免扣繳統編。")
        required_documents.extend(["境外電商電子 Invoice / 收據", "信用卡刷卡水單 / 扣款證明 (需含匯率與手續費)", "境外勞務營業稅繳款書"])
        checklist.append({
            "check_item": "境外勞務統編檢核",
            "status": "PASS",
            "detail": "請確認使用 MediaWiki 記載之各境外電商免扣繳專屬統編 (如 OpenAI、Grok、GitHub)"
        })
    else:
        checklist.append({
            "check_item": "國內統編檢核",
            "status": "INFO",
            "detail": "國內發票請務必開立元智大學統一編號：【00966880】，買受人抬頭勿填寫個人姓名。"
        })

    # 2. 金額門檻與估價單要求
    if amt < 10000:
        checklist.append({
            "check_item": "採購程序與估價單",
            "status": "PASS",
            "detail": "金額未達 10,000 元，屬小額採購，免附估價單。"
        })
    elif 10000 <= amt < 100000:
        checklist.append({
            "check_item": "採購程序與估價單",
            "status": "WARNING",
            "detail": "金額達 10,000 元以上（未達 10 萬元）：需檢附【1 家廠商估價單】；若屬單價逾 1 萬元之耐久設備，請向保管組申請【財產標籤/列管】。"
        })
        required_documents.append("廠商正式估價單 (1家)")
        warnings.append("金額達 1 萬元以上，結案前請確認是否需登錄財產編號並張貼財產標籤。")
    elif 100000 <= amt < 500000:
        checklist.append({
            "check_item": "採購程序與估價單",
            "status": "WARNING",
            "detail": "金額達 100,000 元以上（未達 50 萬元）：需檢附【2 家以上廠商估價單】並進行比價。"
        })
        required_documents.append("2 家以上廠商估價單與比價紀錄")
        warnings.append("金額達 10 萬元以上，需先經計畫主持人與研發處/總務處事前簽核。")
    else:
        checklist.append({
            "check_item": "採購程序與估價單",
            "status": "ALERT",
            "detail": "金額達 500,000 元以上：屬重大採購案，需檢附 3 家估價單並由學校總務處辦理公開招標採購。"
        })
        required_documents.append("3 家估價單、公開招標文件與驗收紀錄")

    # 3. 特殊項目防呆 (便當/餐費/差旅)
    if any(k in item_kw for k in ["便當", "餐費", "點心", "飲料", "聚餐"]):
        checklist.append({
            "check_item": "餐費上限防呆",
            "status": "INFO",
            "detail": "一般便當每人上限 100 ~ 120 元；會議餐費需有具體開會事由，且不得報銷含酒精性飲料。"
        })
        required_documents.extend(["開會通知 / 議程", "出席人員簽到表 (含校內外名冊)"])
    
    if any(k in item_kw for k in ["差旅", "出差", "高鐵", "車資", "住宿"]):
        checklist.append({
            "check_item": "差旅費核銷檢核",
            "status": "INFO",
            "detail": "差旅需事先於 Portal 申請出差單；交通費依實際搭乘票根核實報銷 (高鐵需票根或購票證明)。"
        })
        required_documents.extend(["出差申請單 (經主管核准)", "出差行程報告書", "交通與住宿票根原始憑證"])

    # 4. 查詢現行經費帳本結餘以供參考
    budget_data = load_json('lab_funds_ledger.json')
    current_balance = budget_data[-1].get("結餘", 0) if (budget_data and isinstance(budget_data, list)) else 0

    suggestions = [
        "查看元智大學會計室完整核銷法規清冊",
        f"查詢經費帳本目前最新結餘 (目前結餘約 {current_balance:,} 元)",
        "使用 Portal 自動化機器人建立報帳單據"
    ]

    return {
        "status": "success",
        "item_name": item_kw or "一般採購項目",
        "declared_amount": amt,
        "is_foreign": is_foreign,
        "tax_calculation": tax_info,
        "compliance_checklist": checklist,
        "required_documents": list(dict.fromkeys(required_documents)),
        "important_warnings": warnings,
        "current_lab_balance": current_balance,
        "suggestions": suggestions
    }

def query_official_website(topic=""):
    """
    實驗室官方網站 (https://irl.ee.yzu.edu.tw/) 即時檢索服務
    支援 7 大主題：簡介、指導教授、成員、校友、產學合作實績、聯絡方式、誠徵新成員
    若查詢包含成員 (member)，自動整合使用中設備所有者清冊 (lab_properties.json)。
    """
    try:
        import official_site_reader
        res = official_site_reader.query_official_site(topic)
        # 若為成員相關查詢，補充動態萃取之使用中設備所有者名冊
        if any(w in str(topic).lower() for w in ["member", "成員", "研究生", "學生", "開發者", "名冊", "誰", ""]):
            device_members = query_members()
            if isinstance(res, dict) and device_members.get("status") == "success":
                res["active_workstation_owners"] = device_members.get("items", [])
        return res
    except Exception as e:
        return {"status": "error", "message": f"連線至官網失敗: {e}"}

def query_leaves(keyword=""):
    """
    Google Calendar 行事曆請假狀態檢索服務
    支援：今日請假、特定成員請假狀態、近期/月度請假清冊、特定日期請假查詢。
    """
    try:
        import google_calendar_reader
        import datetime
        import re

        raw_kw = str(keyword).strip()
        kw_norm = raw_kw.lower().replace(" ", "").replace("_", "").replace("-", "")

        # 1. 判斷精準週範圍 (這禮拜, 這週, 本週, thisweek, week, etc.)
        THIS_WEEK_KW = [
            "這禮拜", "本禮拜", "這週", "本週", "這星期", "本星期", "這個禮拜", "這個星期",
            "這個週", "這周", "本周", "今週", "今周", "thisweek", "currentweek", "week"
        ]
        NEXT_WEEK_KW = ["下禮拜", "下個禮拜", "下週", "下周", "下個週", "下個周", "下星期", "下個星期", "nextweek"]
        LAST_WEEK_KW = ["上禮拜", "上個禮拜", "上週", "上周", "上個週", "上個周", "上星期", "上個星期", "lastweek", "prevweek"]
        TWO_WEEKS_KW = ["兩週", "2週", "雙週", "近兩週", "這兩週", "twoweeks", "2weeks"]

        if any(w in kw_norm for w in NEXT_WEEK_KW):
            res = google_calendar_reader.get_week_leaves(week_offset=1)
            res["query_type"] = "week_range"
            res["suggestions"] = ["查詢這禮拜誰請假", "查詢今天誰請假", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        if any(w in kw_norm for w in LAST_WEEK_KW):
            res = google_calendar_reader.get_week_leaves(week_offset=-1)
            res["query_type"] = "week_range"
            res["suggestions"] = ["查詢這禮拜誰請假", "查詢今天誰請假", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        if any(w in kw_norm for w in TWO_WEEKS_KW):
            res = google_calendar_reader.get_recent_leaves(days_back=7, days_forward=7)
            res["query_type"] = "two_weeks_range"
            res["suggestions"] = ["查詢這禮拜誰請假", "查詢今天誰請假", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        if any(w in kw_norm for w in THIS_WEEK_KW) or ("禮拜" in kw_norm) or ("星期" in kw_norm) or ("週" in kw_norm and "兩週" not in kw_norm) or ("周" in kw_norm and "兩周" not in kw_norm):
            res = google_calendar_reader.get_week_leaves(week_offset=0)
            res["query_type"] = "week_range"
            res["suggestions"] = ["查詢今天誰請假", "查詢下禮拜請假名單", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        # 2. 判斷精準月份範圍 (上個月, 這個月/本月, 下個月, 或特定月份如 8月, 8月份, 2026年8月, 2026-08 等)
        today = datetime.date.today()
        LAST_MONTH_KW = ["上個月", "上月", "上個月份", "上月份", "前一個月", "前個月", "前月", "lastmonth", "last_month"]
        THIS_MONTH_KW = ["這個月", "這月", "本月", "本月份", "當月", "當月份", "今月", "這個月份", "thismonth", "this_month", "currentmonth"]
        NEXT_MONTH_KW = ["下個月", "下月", "下個月份", "下月份", "nextmonth", "next_month"]

        if any(w in kw_norm for w in LAST_MONTH_KW):
            t_year = today.year
            t_month = today.month - 1
            if t_month == 0:
                t_month = 12
                t_year -= 1
            res = google_calendar_reader.get_month_leaves(t_year, t_month)
            res["query_type"] = "month_range"
            res["month_label"] = f"{t_year}年{t_month}月"
            res["suggestions"] = ["查詢這個月請假名單", "查詢這禮拜請假名冊", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        if any(w in kw_norm for w in THIS_MONTH_KW):
            res = google_calendar_reader.get_month_leaves(today.year, today.month)
            res["query_type"] = "month_range"
            res["month_label"] = f"{today.year}年{today.month}月"
            res["suggestions"] = ["查詢這禮拜請假名冊", "查詢今天誰請假", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        if any(w in kw_norm for w in NEXT_MONTH_KW):
            t_year = today.year
            t_month = today.month + 1
            if t_month > 12:
                t_month = 1
                t_year += 1
            res = google_calendar_reader.get_month_leaves(t_year, t_month)
            res["query_type"] = "month_range"
            res["month_label"] = f"{t_year}年{t_month}月"
            res["suggestions"] = ["查詢這個月請假名單", "查詢這禮拜請假名冊", "查詢特定成員請假狀態 (如：袁倫廣)"]
            return res

        # 3. 判斷是否為「今天」、「今日」、相對日（明天、昨天）或無明確時間之問句（誰請假、有誰請假）
        if not raw_kw or kw_norm in ("今天", "今日", "today", "現在", "目前", "誰請假", "有誰請假", "誰有請假", "誰", "who"):
            res = google_calendar_reader.get_today_leaves()
            res["query_type"] = "today"
            res["suggestions"] = ["查詢這禮拜請假名單", "查詢特定成員請假狀態 (如：袁倫廣、林銘聖)", "查詢實驗室缺席罰款與請假規定"]
            return res

        if kw_norm in ("明天", "明日", "tomorrow"):
            target_date = datetime.date.today() + datetime.timedelta(days=1)
            res = google_calendar_reader.get_today_leaves(target_date)
            res["query_type"] = "specific_date"
            res["suggestions"] = ["查詢今天誰請假", "查詢這禮拜請假名單", "查詢實驗室出勤規定"]
            return res

        if kw_norm in ("昨天", "昨日", "yesterday"):
            target_date = datetime.date.today() - datetime.timedelta(days=1)
            res = google_calendar_reader.get_today_leaves(target_date)
            res["query_type"] = "specific_date"
            res["suggestions"] = ["查詢今天誰請假", "查詢這禮拜請假名單", "查詢實驗室出勤規定"]
            return res

        # 4. 判斷是否為完整特定年月日 (例如 2026-09-14, 2026/09/14, 9-14, 9/14, 9月14日)
        m_full_date = re.search(r'(?:(\d{4})[-/年])?(\d{1,2})[-/月](\d{1,2})日?', raw_kw)
        if m_full_date:
            year = int(m_full_date.group(1)) if m_full_date.group(1) else datetime.date.today().year
            month = int(m_full_date.group(2))
            day = int(m_full_date.group(3))
            try:
                target_date = datetime.date(year, month, day)
                res = google_calendar_reader.get_today_leaves(target_date)
                res["query_type"] = "specific_date"
                res["suggestions"] = ["查詢今天誰請假", "查詢這禮拜請假名單", "查詢實驗室出勤規定"]
                return res
            except Exception:
                pass

        # 5. 判斷是否為明確指定月份 (例如 2026-08, 2026/08, 2026年8月, 8月份, 8月, 八月, 8月呢, 8月請假)
        CN_MONTH_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
        m_month_spec = re.search(r'(?:(\d{4})[-/年\.\s]*)?(\d{1,2}|[一二三四五六七八九十]{1,2})月(?:份)?', raw_kw)
        if not m_month_spec:
            m_month_spec = re.search(r'(\d{4})[-/](\d{1,2})(?![-/\d])', raw_kw)

        if m_month_spec:
            year_val = int(m_month_spec.group(1)) if m_month_spec.group(1) else today.year
            raw_m = m_month_spec.group(2)
            month_val = CN_MONTH_MAP.get(raw_m) if raw_m in CN_MONTH_MAP else int(raw_m) if raw_m.isdigit() else None
            if month_val and 1 <= month_val <= 12:
                res = google_calendar_reader.get_month_leaves(year_val, month_val)
                res["query_type"] = "month_range"
                res["month_label"] = f"{year_val}年{month_val}月"
                res["suggestions"] = ["查詢今天誰請假", "查詢這禮拜請假名單", "查詢實驗室出勤規定"]
                return res

        # 6. 成員比對：支援自動錯字更正與姓名標準化 (例如 銘璽/銘勝 -> 銘聖, 政宇 -> 正宇)
        norm_mem = google_calendar_reader.normalize_member_name(raw_kw)
        target_member = None
        if norm_mem.get("display_name") and norm_mem.get("display_name") in google_calendar_reader.LAB_MEMBERS.values():
            target_member = norm_mem.get("display_name")
        else:
            clean_name = raw_kw
            for noise in ["有沒有請假", "請假了嗎", "請假名單", "請假名冊", "請假紀錄", "請假記錄", "有請假嗎", "請假", "查詢", "請問", "想問", "查一下"]:
                clean_name = clean_name.replace(noise, "")
            clean_name = clean_name.strip()
            norm_clean = google_calendar_reader.normalize_member_name(clean_name)
            if norm_clean.get("display_name") and norm_clean.get("display_name") in google_calendar_reader.LAB_MEMBERS.values():
                target_member = norm_clean.get("display_name")

        if target_member:
            res = google_calendar_reader.check_member_leave(target_member)
            recent = google_calendar_reader.get_recent_leaves(days_back=14, days_forward=14)
            member_history = [
                l for l in recent.get("leaves", []) 
                if target_member in l.get("title", "") or any(part in l.get("title", "") for part in [target_member[-2:], target_member])
            ]
            res["query_type"] = "member_check"
            res["history_leaves"] = member_history
            res["suggestions"] = ["查詢今天全體請假名單", "查詢這禮拜請假名冊", f"查詢 {target_member} 保管之設備清冊"]
            return res

        # 7. 廣義近期名冊查詢 fallback (近兩週~一個月)
        res = google_calendar_reader.get_recent_leaves(days_back=14, days_forward=14)
        res["query_type"] = "recent_range"
        res["suggestions"] = ["查詢今天誰請假", "查詢這禮拜請假名單", "查詢特定成員請假狀態 (如：袁倫廣)"]
        return res

    except Exception as e:
        return {"status": "error", "message": f"連線至 Google 日曆失敗: {e}", "suggestions": ["查詢實驗室請假規則與懲處標準"]}

query_leave = query_leaves

def apply_leave(member_name, date_str="今天", start_time="10:00", end_time="17:00", reason=""):
    """
    透過 AI 自動登記請假至 Google 行事曆（自動校正錯字，嚴格遵循歷史慣例格式：標題為兩字習慣稱呼，時段預設 10:00~17:00）
    """
    try:
        import google_calendar_reader
        import datetime
        import re

        today = datetime.date.today()
        clean_date = str(date_str).strip()
        target_date = today

        if clean_date in ("今天", "今日", "today"):
            target_date = today
        elif clean_date in ("明天", "明日", "tomorrow"):
            target_date = today + datetime.timedelta(days=1)
        elif clean_date in ("後天", "後日"):
            target_date = today + datetime.timedelta(days=2)
        else:
            m = re.search(r'(?:(\d{4})[-/])?(\d{1,2})[-/](\d{1,2})', clean_date)
            if m:
                y = int(m.group(1)) if m.group(1) else today.year
                m_val = int(m.group(2))
                d_val = int(m.group(3))
                try:
                    target_date = datetime.date(y, m_val, d_val)
                except Exception:
                    pass

        target_date_str = target_date.strftime("%Y-%m-%d")
        res = google_calendar_reader.add_leave_event(
            member_name=member_name,
            date_str=target_date_str,
            start_time=start_time,
            end_time=end_time,
            reason=reason
        )

        if res.get("status") == "success":
            disp = res.get("display_name", member_name)
            res["details"] = {
                "original_input": res.get("original_name", member_name),
                "member": disp,
                "full_name": res.get("full_name", member_name),
                "was_corrected": res.get("was_corrected", False),
                "date": target_date_str,
                "period": f"{start_time} ～ {end_time}",
                "reason": reason if reason else "未特別註明"
            }
            res["suggestions"] = ["查詢今天誰請假", f"查詢 {disp} 近期請假紀錄", "查詢實驗室請假規則"]
        return res
    except Exception as e:
        return {"status": "error", "message": f"自動登記請假失敗: {e}"}

def cancel_leave(member_name, date_str=None):
    """
    透過 AI 取消指定成員的請假紀錄並同步自 Google 日曆刪除（支援自動錯字更正）
    """
    try:
        import google_calendar_reader
        import datetime
        import re

        clean_date = None
        if date_str:
            raw = str(date_str).strip()
            today = datetime.date.today()
            if raw in ("今天", "今日", "today"):
                clean_date = today.strftime("%Y-%m-%d")
            elif raw in ("明天", "明日", "tomorrow"):
                clean_date = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            elif raw in ("後天", "後日"):
                clean_date = (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
            else:
                m = re.search(r'(?:(\d{4})[-/年])?(\d{1,2})[-/月](\d{1,2})日?', raw)
                if m:
                    y = int(m.group(1)) if m.group(1) else today.year
                    m_val = int(m.group(2))
                    d_val = int(m.group(3))
                    clean_date = f"{y:04d}-{m_val:02d}-{d_val:02d}"

        res = google_calendar_reader.cancel_leave_event(member_name=member_name, date_str=clean_date)
        disp = res.get("display_name", member_name)
        res["suggestions"] = ["查詢今天誰請假", f"查詢 {disp} 近期請假紀錄", "查詢實驗室出勤規定"]
        return res
    except Exception as e:
        return {"status": "error", "message": f"取消請假失敗: {e}"}


# =========================================================================
# 實用延伸功能一：公用經費 380 筆真實帳本「年度/季度財務統計報表」
# =========================================================================
def query_funds_report(year_param=""):
    """
    依據 lab_funds_ledger.json 現存 380 筆真實收支流水帳進行純數學彙整統計。
    支援歷年總覽與特定年份 (如 2023 或 112) 各季/各月收支走勢與用途分類。
    """
    ledger = load_json('lab_funds_ledger.json') or []
    if not ledger:
        return {"status": "error", "message": "查無經費帳本資料庫"}

    import re
    from collections import defaultdict

    clean_y = str(year_param).strip()
    target_year = None
    if clean_y:
        m = re.search(r'(\d{2,4})', clean_y)
        if m:
            val = int(m.group(1))
            if val < 1900:  # 民國年轉西元
                val += 1911
            target_year = val

    # 解析所有紀錄之年份與月份
    records_by_year = defaultdict(list)
    unknown_records = []
    
    for r in ledger:
        d_str = r.get("日期")
        amt = float(r.get("收支金額(增減)", 0.0) or 0.0)
        bal = r.get("結餘", 0)
        memo = r.get("備註") or ""
        
        parsed_y = None
        parsed_m = None
        if d_str and isinstance(d_str, str):
            parts = d_str.split("-")
            if len(parts) >= 1 and parts[0].isdigit():
                parsed_y = int(parts[0])
                if len(parts) >= 2 and parts[1].isdigit():
                    parsed_m = int(parts[1])
                    
        if parsed_y:
            records_by_year[parsed_y].append({
                "date": d_str,
                "month": parsed_m,
                "amount": amt,
                "balance": bal,
                "memo": memo
            })
        else:
            unknown_records.append({
                "date": d_str,
                "amount": amt,
                "balance": bal,
                "memo": memo
            })

    # 若未指定年份或查無該年：產出歷年總覽
    if not target_year or target_year not in records_by_year:
        years_sorted = sorted(records_by_year.keys())
        table_lines = [
            "### 📊 實驗室公用經費歷年收支與結餘總覽報表",
            "",
            "| 會計年份 | 年度總收入 | 年度總支出 | 年度淨收支 | 年末結餘 | 交易筆數 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        
        grand_income = 0.0
        grand_expense = 0.0
        
        for y in years_sorted:
            y_recs = records_by_year[y]
            inc = sum(x["amount"] for x in y_recs if x["amount"] > 0)
            exp = sum(x["amount"] for x in y_recs if x["amount"] < 0)
            net = inc + exp
            end_bal = y_recs[-1]["balance"]
            cnt = len(y_recs)
            grand_income += inc
            grand_expense += exp
            table_lines.append(f"| {y} 年 (民國 {y-1911} 年) | +{int(inc):,} 元 | {int(exp):,} 元 | {int(net):+,} 元 | {end_bal:,} 元 | {cnt} 筆 |")
            
        latest_overall_balance = ledger[-1].get("結餘", 0) if ledger else 0
        latest_date = ledger[-1].get("日期", "")
        
        table_lines.extend([
            "",
            f"* **公用經費目前最新結餘**：**{latest_overall_balance:,} 元**（更新至 {latest_date}）",
            f"* **歷年累計總收入**：+{int(grand_income):,} 元",
            f"* **歷年累計總支出**：{int(grand_expense):,} 元",
            "",
            "### 💡 深入查詢建議",
            "* 查詢特定年份詳細季度與用途報表：`query funds_report <年份如 2023 或 2024>`",
            "* 查詢最近收支流水帳明細：`query funds 15`",
            "* 進行報帳合規防呆試算：`compliance <項目> <金額>`"
        ])
        
        return {
            "status": "success",
            "mode": "yearly_summary",
            "grand_income": grand_income,
            "grand_expense": grand_expense,
            "current_balance": latest_overall_balance,
            "report_markdown": "\n".join(table_lines),
            "suggestions": [
                "查詢 2023 年公用經費詳細收支報表",
                "查詢最近 15 筆公用經費流水帳明細",
                "查詢元智會計報帳審核法規與便當核銷標準"
            ]
        }
    else:
        # 指定特定年份詳細報表
        y_recs = records_by_year[target_year]
        total_inc = sum(x["amount"] for x in y_recs if x["amount"] > 0)
        total_exp = sum(x["amount"] for x in y_recs if x["amount"] < 0)
        net_val = total_inc + total_exp
        end_bal = y_recs[-1]["balance"]
        
        # 季度統計
        quarters = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
        for r in y_recs:
            m = r.get("month") or 1
            if m in (1, 2, 3):
                quarters["Q1"].append(r)
            elif m in (4, 5, 6):
                quarters["Q2"].append(r)
            elif m in (7, 8, 9):
                quarters["Q3"].append(r)
            else:
                quarters["Q4"].append(r)
                
        # 用途分類 (基於備註文字客觀聚合)
        cats = {
            "餐飲茶水點心": 0.0,
            "辦公耗材與設備": 0.0,
            "經費補助與罰款收入": 0.0,
            "其他公用支出": 0.0
        }
        for r in y_recs:
            amt = r["amount"]
            memo = r["memo"].lower()
            if amt > 0:
                cats["經費補助與罰款收入"] += amt
            else:
                cost = abs(amt)
                if any(k in memo for k in ["零食", "便當", "飲料", "點心", "披薩", "聚餐", "麥當勞", "飯", "茶"]):
                    cats["餐飲茶水點心"] += cost
                elif any(k in memo for k in ["紙", "筆", "影印", "鑰匙", "插座", "線", "清潔", "耗材", "文具"]):
                    cats["辦公耗材與設備"] += cost
                else:
                    cats["其他公用支出"] += cost

        report_lines = [
            f"### 📊 {target_year} 年（民國 {target_year-1911} 年）公用經費年度財務統計報表",
            "",
            f"* **年度總收入**：**+{int(total_inc):,} 元**",
            f"* **年度總支出**：**{int(total_exp):,} 元**",
            f"* **年度淨結存變動**：**{int(net_val):+,} 元**",
            f"* **年末結餘**：**{end_bal:,} 元**（總計交易 {len(y_recs)} 筆）",
            "",
            "### 🕒 季度收支走勢分佈",
            "",
            "| 季度 | 總收入 | 總支出 | 淨變動 | 筆數 |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]
        for q_name, q_list in quarters.items():
            q_inc = sum(x["amount"] for x in q_list if x["amount"] > 0)
            q_exp = sum(x["amount"] for x in q_list if x["amount"] < 0)
            report_lines.append(f"| {q_name} | +{int(q_inc):,} 元 | {int(q_exp):,} 元 | {int(q_inc + q_exp):+,} 元 | {len(q_list)} 筆 |")
            
        report_lines.extend([
            "",
            "### 🏷️ 支出用途分類統計",
            f"* 🍽️ **餐飲茶水點心支出**：約 {int(cats['餐飲茶水點心']):,} 元",
            f"* 🛠️ **辦公耗材與用品支出**：約 {int(cats['辦公耗材與設備']):,} 元",
            f"* 📦 **其他公用雜支**：約 {int(cats['其他公用支出']):,} 元",
            f"* 💰 **補助與收入總計**：約 {int(cats['經費補助與罰款收入']):,} 元"
        ])

        return {
            "status": "success",
            "year": target_year,
            "total_income": total_inc,
            "total_expense": total_exp,
            "net_change": net_val,
            "year_end_balance": end_bal,
            "report_markdown": "\n".join(report_lines),
            "suggestions": [
                "查詢歷年公用經費收支總覽報表",
                "查詢最近 15 筆公用經費流水帳明細",
                "查詢目前公用經費最新總結餘"
            ]
        }


# =========================================================================
# 實用延伸功能二：歷屆論文「真實關鍵字詞頻分佈與領域歸納清冊」
# =========================================================================
def query_thesis_topics(topic_param=""):
    """
    依據 thesis_index.json 42 篇真實碩士論文之 keywords 進行客觀詞頻統計與領域歸納。
    絕無主觀腦補演進優劣或捏造引用，純粹基於真實關鍵字與年代客觀呈現。
    """
    theses = load_json('thesis_index.json') or []
    if not theses:
        return {"status": "error", "message": "查無論文索引資料庫"}

    from collections import Counter
    
    # 統計所有論文的關鍵字詞頻
    all_kw = []
    stop_words = {"碩士論文", "論文", "碩士", "研究", "實作", "基於", "系統", "方法", "設計"}
    for t in theses:
        kws = t.get("keywords") or []
        for k in kws:
            k_clean = str(k).strip()
            # 排除作者本人姓名與過於泛化的詞
            if k_clean and k_clean != t.get("author") and len(k_clean) > 1 and k_clean not in stop_words:
                all_kw.append(k_clean)
                
    kw_counter = Counter(all_kw)
    clean_topic = str(topic_param).strip().lower()
    
    # 判斷是否為「主題總覽 / 主題清冊」請求（自動過濾修飾詞）
    meta_words = ["歷屆", "碩士", "論文", "研究", "主題", "領域", "清冊", "全部", "總覽", "列表", "清單", "topics", "domain", "all"]
    stripped = clean_topic
    for mw in meta_words:
        stripped = stripped.replace(mw, "")
    is_overview = (not clean_topic) or (not stripped.strip()) or any(clean_topic == m for m in meta_words)
    
    # 定義八大核心研究領域之標準比對規則（總表與單一領域查詢 100% 共用同一套規則，杜絕統計口徑不一致）
    defined_domains = [
        {
            "name": "物聯網與智慧感測 (IoT & Smart Sensing)",
            "short": "物聯網",
            "match": ["物聯網", "iot", "感測", "藍芽"],
            "aliases": ["物聯網", "iot", "感測", "智慧感測", "物聯網與智慧感測節能", "感測節能"]
        },
        {
            "name": "車聯網與車用通訊 (VANET & V2X)",
            "short": "車用網路",
            "match": ["車用網路", "車聯網", "vanet", "車輛", "rsu", "交通"],
            "aliases": ["車用網路", "車聯網", "vanet", "車用通訊", "車輛通訊"]
        },
        {
            "name": "邊緣運算與動態卸載 (Edge Computing)",
            "short": "邊緣運算",
            "match": ["邊緣運算", "edge"],
            "aliases": ["邊緣運算", "edge", "動態卸載"]
        },
        {
            "name": "M2M 家用閘道與智慧系統 (M2M Gateways)",
            "short": "m2m",
            "match": ["m2m", "家用閘道", "gateway", "數位家庭", "閘道"],
            "aliases": ["m2m", "家用閘道", "gateway", "數位家庭", "智慧閘道"]
        },
        {
            "name": "無線通訊與蜂巢資源分配 (LTE / MIMO)",
            "short": "無線通訊",
            "match": ["lte", "mimo", "射頻", "天線", "排程", "資源分配", "蜂巢", "通訊系統"],
            "aliases": ["lte", "mimo", "無線通訊", "射頻", "天線", "蜂巢資源分配"]
        },
        {
            "name": "360度視訊串流與虛擬實境 (360° VR Streaming)",
            "short": "360度視訊",
            "match": ["360", "vr", "虛擬實境", "視角預測", "視訊串流"],
            "aliases": ["360度", "360", "vr", "虛擬實境", "視訊串流", "視角預測"]
        },
        {
            "name": "無人機與無人載具協同 (UAV & Drones)",
            "short": "無人機",
            "match": ["無人機", "uav", "無人載具", "無人飛行"],
            "aliases": ["無人機", "uav", "無人載具", "無人飛行載具"]
        },
        {
            "name": "大型語言模型與社群平台 (LLM & Social AI)",
            "short": "大型語言模型",
            "match": ["llm", "社群平台", "社群網路", "自然語言", "回訊系統", "agent"],
            "aliases": ["llm", "社群平台", "社群", "自然語言", "回訊系統", "agent", "ai"]
        }
    ]

    # 為每個領域預先計算真實涵蓋的論文集合
    for d in defined_domains:
        d["theses"] = []
        for t in theses:
            searchable = f"{t.get('title', '')} {t.get('english_title', '')} {' '.join(t.get('keywords', []))}".lower()
            if any(m in searchable for m in d["match"]):
                d["theses"].append(t)
        # 依畢業年份由舊至新排序
        d["theses"].sort(key=lambda x: (x.get("year_roc", 0), x.get("month_roc", 0)))

    # 判斷是否為「主題總覽 / 主題清冊」請求
    meta_words = ["歷屆", "碩士", "論文", "研究", "主題", "領域", "清冊", "全部", "總覽", "列表", "清單", "topics", "domain", "all"]
    stripped = clean_topic
    for mw in meta_words:
        stripped = stripped.replace(mw, "")
    is_overview = (not clean_topic) or (not stripped.strip()) or any(clean_topic == m for m in meta_words)

    if is_overview:
        lines = [
            "### 🎓 智慧機器人實驗室 (IRL) 歷屆碩士論文核心研究領域總清冊 (共 42 篇)",
            "> 💡 **統計說明**：各領域篇數為該領域之實際完整研究成果。部分跨領域研究論文（例如《物聯網行動裝置之邊緣運算與傳輸節能方法》同時涵蓋【物聯網】與【邊緣運算】）會同時列入所屬領域，故各領域加總會大於 42 篇。",
            "",
            "| 核心研究領域 | 涵蓋篇數 | 年代跨度 | 代表研究成員（依年代先後） |",
            "| :--- | :--- | :--- | :--- |"
        ]

        for d in defined_domains:
            d_theses = d["theses"]
            cnt = len(d_theses)
            if cnt > 0:
                y_min = d_theses[0].get("year_roc", "")
                y_max = d_theses[-1].get("year_roc", "")
                y_span = f"民國 {y_min}～{y_max} 年" if y_min != y_max else f"民國 {y_min} 年"
                authors = "、".join([t.get("author", "") for t in d_theses[:4]])
                if cnt > 4:
                    authors += f" 等 {cnt} 位"
                lines.append(f"| **{d['name']}** | **{cnt} 篇** | {y_span} | {authors} |")

        lines.extend([
            "",
            "### 📚 各領域歷屆代表論文精選一覽",
            ""
        ])

        for d in defined_domains:
            d_theses = d["theses"]
            if d_theses:
                top_repr = d_theses[:2]
                lines.append(f"#### 🏷️ 【{d['name'].split(' (')[0]}】（共 {len(d_theses)} 篇）")
                for t in top_repr:
                    lines.append(f"* 民國 {t.get('year_roc')} 年｜**{t.get('author')}**：《{t.get('title')}》")
                if len(d_theses) > 2:
                    lines.append(f"* *(另有 {len(d_theses) - 2} 篇論文，輸入 `query thesis_topics {d['short']}` 可查看該領域全部 {len(d_theses)} 篇完整清單)*")
                lines.append("")

        lines.extend([
            "### 💡 主題檢索操作指引",
            "* 查詢特定主題之歷屆所有論文清冊：`query thesis_topics <主題名稱，如：物聯網、360度、邊緣運算、無人機>`",
            "* 查閱特定研究生之論文完整摘要與簡報：`query thesis <研究生姓名>`",
            "* 提取官方論文全文原檔：`nas open <研究生姓名> 論文`"
        ])

        return {
            "status": "success",
            "mode": "topic_ranking",
            "total_theses": len(theses),
            "domains": [{k: v for k, v in d.items() if k != "theses"} for d in defined_domains],
            "report_markdown": "\n".join(lines),
            "suggestions": [
                "檢索「物聯網」相關之歷屆碩士論文清冊",
                "檢索「360度」視訊相關之歷屆碩士論文清冊",
                "檢索「邊緣運算」相關之歷屆碩士論文清冊"
            ]
        }
    else:
        # 1. 優先檢查是否命中八大定義領域（完全精確對齊總表篇數）
        matched_domain = None
        for d in defined_domains:
            if clean_topic in [a.lower() for a in d["aliases"]] or any(a.lower() in clean_topic for a in d["aliases"]):
                matched_domain = d
                break

        if matched_domain:
            matched_theses = matched_domain["theses"]
            topic_label = matched_domain["name"]
        else:
            # 2. 一般自訂關鍵字搜尋
            matched_theses = []
            for t in theses:
                searchable = f"{t.get('title', '')} {t.get('english_title', '')} {' '.join(t.get('keywords', []))}".lower()
                if clean_topic in searchable:
                    matched_theses.append(t)
            matched_theses.sort(key=lambda x: (x.get("year_roc", 0), x.get("month_roc", 0)))
            topic_label = topic_param

        lines = [
            f"### 📌 歷屆相關碩士論文清冊：【{topic_label}】 (共 {len(matched_theses)} 篇)",
            "",
            "| 畢業年份 | 研究生 | 論文題目 | 指導教授 | 核心關鍵字 |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]
        
        if not matched_theses:
            lines.append(f"| 查無與「{topic_param}」直接相關之碩士論文紀錄 | - | - | - | - |")
        else:
            for t in matched_theses:
                kw_str = "、".join((t.get("keywords") or [])[:5])
                lines.append(f"| 民國 {t.get('year_roc')} 年 | **{t.get('author')}** | {t.get('title')} | {t.get('advisor')} 教授 | {kw_str} |")
                
        lines.extend([
            "",
            "### 💡 查閱完整官方論文與簡報",
            "* 凡需閱讀特定研究生之論文全文或口試投影片，請直接輸入：`nas open <研究生姓名> 論文`",
            "* 系統將自動從 NAS (`/IRLshare/畢業論文/`) 提取原檔，並於本地檢視器開啟。"
        ])
        
        return {
            "status": "success",
            "keyword": topic_param,
            "count": len(matched_theses),
            "theses": matched_theses,
            "report_markdown": "\n".join(lines),
            "suggestions": [
                f"由 NAS 提取 {matched_theses[0].get('author')} 的論文原檔" if matched_theses else "查看其他熱門研究主題",
                "查詢歷屆論文核心研究主題排行清單",
                "查詢歷屆已畢業校友名冊與聯絡方式"
            ]
        }


# =========================================================================
# 實用延伸功能三：財產清冊「個人名下設備對帳與 70640 實驗室盤點報表」
# =========================================================================
def query_property_inventory(target_param=""):
    """
    依據 lab_properties.json 52 筆真實列管設備，提供個人名下設備對帳或 70640 實驗室盤點報表。
    """
    props = load_json('lab_properties.json') or []
    if not props:
        return {"status": "error", "message": "查無財產清冊資料庫"}

    from collections import Counter
    clean_target = str(target_param).strip()
    
    # 判斷是否為特定成員查詢（檢查在現役成員、校友或設備使用者欄位中是否存在）
    active_names = ["邱子倫", "袁倫廣", "尹才彥", "林銘聖", "楊正宇", "蘇冠宇", "蕭宇傑"]
    is_person_query = False
    matched_person = None
    
    if clean_target and clean_target not in ("盤點", "70640", "全室", "清冊", "設備", "全部"):
        for name in active_names:
            if clean_target in name or name in clean_target:
                is_person_query = True
                matched_person = name
                break
        if not is_person_query:
            # 檢查是否為其他校友/使用者
            for p in props:
                u = p.get("使用者") or ""
                if clean_target in u:
                    is_person_query = True
                    matched_person = u
                    break

    if is_person_query and matched_person:
        # 個人保管設備對帳模式
        user_props = [p for p in props if matched_person in (p.get("使用者") or "")]
        lines = [
            f"### 🖥️ 成員個人名下保管設備對帳單：【{matched_person}】",
            "",
            "| 財產編號 | 設備類型 | 廠牌與型號 | 網路 IP 地址 | 存放位置 | 設備狀態 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        if not user_props:
            lines.append(f"| - | 查無 {matched_person} 名下登記之保管設備 | - | - | 70640 | - |")
        else:
            for p in user_props:
                p_id = p.get("財產編號") or "未編號"
                p_type = p.get("設備類型") or "設備"
                p_model = p.get("廠牌與型號") or "-"
                p_ip = p.get("網路IP") or "未設定/動態分配"
                p_loc = p.get("放置位置") or 70640
                p_status = p.get("設備狀態") or "正常使用中"
                lines.append(f"| `{p_id}` | **{p_type}** | {p_model} | `{p_ip}` | {p_loc} | {p_status} |")
                
        lines.extend([
            "",
            f"* **保管設備總計**：共 {len(user_props)} 件設備由 {matched_person} 保管使用。",
            "",
            "### 💡 後續操作建議",
            f"* 查詢 {matched_person} 之 360 度個人全景檔案：`query 360 {matched_person}`",
            "* 產出 70640 實驗室全體設備盤點報表：`query property_inventory 70640`",
            "* 查詢 70640 目前未指派或待處置之公用主機清冊"
        ])
        
        return {
            "status": "success",
            "mode": "personal_inventory",
            "person": matched_person,
            "count": len(user_props),
            "properties": user_props,
            "report_markdown": "\n".join(lines),
            "suggestions": [
                f"查詢 {matched_person} 的 360 度個人全景檔案",
                "產出 70640 實驗室全室設備盤點總表",
                "查詢 70640 目前未指派之公用設備清冊"
            ]
        }
    else:
        # 70640 實驗室全室盤點模式
        total_count = len(props)
        type_counts = Counter(p.get("設備類型", "其他設備") for p in props)
        unassigned = [p for p in props if not p.get("使用者")]
        assigned = [p for p in props if p.get("使用者")]
        
        lines = [
            "### 🏢 元智大學 70640 智慧機器人實驗室財產盤點總表",
            "",
            f"* **列管財產總數**：共 **{total_count} 件**",
            f"* **已指派使用設備**：**{len(assigned)} 件**",
            f"* **公用/未分配/待處置設備**：**{len(unassigned)} 件**",
            "",
            "### 📊 設備類型分類統計",
            "",
            "| 設備類型 | 登記件數 | 主要廠牌與代表型號 |",
            "| :--- | :--- | :--- |"
        ]
        
        for p_type, cnt in type_counts.most_common():
            sample_model = next((p.get("廠牌與型號") for p in props if p.get("設備類型") == p_type and p.get("廠牌與型號")), "-")
            lines.append(f"| **{p_type}** | {cnt} 件 | {sample_model} |")
            
        lines.extend([
            "",
            "### 👥 現役成員主機與設備分配對照",
            "",
            "| 保管成員 | 保管設備類型 | 廠牌與型號 | 網路 IP |",
            "| :--- | :--- | :--- | :--- |"
        ])
        for p in assigned:
            lines.append(f"| **{p.get('使用者')}** | {p.get('設備類型')} | {p.get('廠牌與型號') or '-'} | `{p.get('網路IP') or '動態'}` |")
            
        lines.extend([
            "",
            "### 💡 盤點操作建議",
            "* 查詢特定成員保管清冊：`query property_inventory <成員姓名，如：邱子倫、袁倫廣>`",
            "* 查詢特定型號或財產編號設備：`query property <關鍵字>`"
        ])
        
        return {
            "status": "success",
            "mode": "lab_inventory",
            "total_count": total_count,
            "type_counts": dict(type_counts),
            "unassigned_count": len(unassigned),
            "report_markdown": "\n".join(lines),
            "suggestions": [
                "查詢邱子倫名下保管之設備對帳單",
                "查詢袁倫廣名下保管之設備對帳單",
                "查詢 70640 實驗室主機清冊與 IP 分布"
            ]
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python query_service.py members|alumni|thesis|property|budget|funds_report|thesis_topics|property_inventory|rules|wiki|site|360|compliance|leaves|apply_leave|cancel_leave [參數...]")
        sys.exit(0)
        
    cmd = sys.argv[1]
    kw = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if cmd in ("members", "member"):
        res = query_members(kw)
    elif cmd == "alumni":
        res = query_alumni(kw)
    elif cmd == "thesis":
        res = query_thesis(kw)
    elif cmd == "property":
        res = query_properties(kw)
    elif cmd in ("budget", "funds"):
        res = query_budget(kw)
    elif cmd in ("funds_report", "budget_report", "funds_summary"):
        res = query_funds_report(kw)
    elif cmd in ("thesis_topics", "topics", "domain", "domains"):
        res = query_thesis_topics(kw)
    elif cmd in ("property_inventory", "inventory", "assets"):
        res = query_property_inventory(kw)
    elif cmd == "rules":
        res = query_accounting_rules(kw)
    elif cmd == "wiki":
        res = query_wiki(kw)
    elif cmd in ("site", "official", "web"):
        res = query_official_website(kw)
    elif cmd == "360":
        res = query_person_360(kw)
    elif cmd in ("leaves", "leave"):
        res = query_leaves(kw)
    elif cmd in ("apply_leave", "add_leave"):
        date_param = sys.argv[3] if len(sys.argv) > 3 else "今天"
        start_t = sys.argv[4] if len(sys.argv) > 4 else "10:00"
        end_t = sys.argv[5] if len(sys.argv) > 5 else "17:00"
        reason_t = sys.argv[6] if len(sys.argv) > 6 else ""
        res = apply_leave(member_name=kw, date_str=date_param, start_time=start_t, end_time=end_t, reason=reason_t)
    elif cmd in ("cancel_leave", "delete_leave"):
        date_param = sys.argv[3] if len(sys.argv) > 3 else None
        res = cancel_leave(member_name=kw, date_str=date_param)
    elif cmd == "compliance":
        amt = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        vendor = sys.argv[4] if len(sys.argv) > 4 else "國內"
        res = evaluate_expense_compliance(item_name=kw, amount=amt, vendor_type=vendor)
    elif cmd == "sync":
        sync_ok = check_and_auto_sync(force=True)
        res = {"status": "success" if sync_ok else "failed", "synced": sync_ok, "message": "已完成強制同步檢查"}
    else:
        res = {"status": "error", "message": f"未知的指令: {cmd}"}
        
    print(json.dumps(res, ensure_ascii=False, indent=2))





