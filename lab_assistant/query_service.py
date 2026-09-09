"""
實驗室智慧問答與知識庫檢索服務 (Lab Assistant Query Service)
支援：校友名冊、經費預算帳本、財產清冊、會計報銷法規、360度人物全景聯查、智慧延伸推薦與報帳合規防呆試算。
"""

import os
import sys
import json
import difflib

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, 'data')

def load_json(filename):
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

def query_alumni(keyword=""):
    data = load_json('lab_alumni.json')
    if not data:
        return {"status": "error", "message": "找不到校友資料庫", "suggestions": []}
    
    if not keyword:
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
        
        if _match_tokens_all(full_str, keyword):
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
    
    if not keyword:
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
        full_prop_str = f"{name} {custodian} {loc} {sn} {spec}"
        
        if _match_tokens_all(full_prop_str, keyword):
            matches.append(item)
            
    suggestions = []
    if matches:
        first_item = matches[0]
        c = first_item.get("保管人") or first_item.get("使用者")
        if c:
            suggestions.append(f"查詢保管人 {c} 名下的所有實驗室設備")
        suggestions.append("查詢報帳法規中『1萬元以上財產列管與登錄流程』")
        suggestions.append("查詢放置位置之其他周邊設備清冊")
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
    data = load_json('lab_funds_ledger.json')
    if not data:
        return {"status": "error", "message": "找不到經費帳本資料庫", "suggestions": []}
    
    if not isinstance(data, list):
        return {"status": "success", "data": data, "suggestions": []}

    latest = data[-1] if data else {}
    latest_balance = latest.get("結餘", 0)
    latest_date = latest.get("日期", "")

    if not keyword:
        return {
            "status": "success",
            "total_transactions": len(data),
            "latest_balance": latest_balance,
            "latest_update_date": latest_date,
            "recent_transactions": data[-15:],
            "suggestions": [
                "查詢近期差旅與便當費用支出",
                "進行單筆報帳合規防呆試算 (如 35000元設備採購)",
                "查詢境外電商 (OpenAI/Grok) 報帳細則"
            ]
        }
    
    matches = []
    total_change = 0.0
    for entry in data:
        note = str(entry.get("備註", "") or "")
        date_str = str(entry.get("日期", "") or "")
        item_str = str(entry.get("項目", "") or "")
        full_entry_str = f"{note} {date_str} {item_str}"
        
        if _match_tokens_all(full_entry_str, keyword):
            matches.append(entry)
            amt = entry.get("收支金額(增減)")
            if amt is not None:
                try:
                    total_change += float(amt)
                except Exception:
                    pass

    return {
        "status": "success",
        "keyword": keyword,
        "matched_count": len(matches),
        "total_amount_change": total_change,
        "current_balance": latest_balance,
        "results": matches,
        "suggestions": [
            f"查看『{keyword}』相關會計報銷法規與核銷標準",
            "試算該筆支出的估價單要求與統編防呆",
            "查看實驗室目前最新總結餘與近期流水帳"
        ]
    }

def query_accounting_rules(question=""):
    data = load_json('accounting_rules.json')
    if not data:
        return {"status": "error", "message": "找不到報帳法規資料庫", "suggestions": []}
    
    if not question:
        return {
            "status": "success",
            "data": data,
            "suggestions": ["查詢便當餐費與會議核銷上限", "查詢 1萬元以上設備採購規範", "查詢境外電商統編與 5%營業稅試算"]
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
            
    return {
        "status": "success",
        "question": question,
        "count": len(matches),
        "results": matches,
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
    
    if not keyword:
        return {
            "status": "success",
            "total": len(data),
            "items": data,
            "suggestions": ["搜尋無人機相關畢業論文", "搜尋物聯網與定位演算法論文", "依作者姓名查詢歷屆論文"]
        }
        
    kw = keyword.strip().lower()
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
        if _match_tokens_all(full_text, keyword):
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
            
    matches.sort(key=lambda x: x["score"], reverse=True)
    results = [m["thesis"] for m in matches]
    
    suggestions = []
    if results:
        first_t = results[0]
        auth = first_t.get("author", "")
        suggestions.append(f"提取並檢視 {auth} 的口試簡報 (PPTX)")
        suggestions.append(f"查詢 {auth} 的 360度全景個人資料")
        suggestions.append(f"檢索 NAS 上與「{first_t.get('title', '')[:10]}...」相關的產學報告")
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
    一鍵跨 4 大資料庫 (校友名冊、論文索引、設備清冊、經費帳本) 聯查個人 360 度全景資訊。
    """
    name = person_name.strip()
    if not name:
        return {"status": "error", "message": "請提供欲查詢之成員姓名", "suggestions": []}

    profile = {
        "query_name": name,
        "basic_info": None,
        "thesis_info": [],
        "managed_properties": [],
        "budget_records": [],
        "summary": {}
    }

    # 1. 查校友/基本資料庫
    alumni_res = query_alumni(name)
    if alumni_res.get("status") == "success" and alumni_res.get("results"):
        profile["basic_info"] = alumni_res["results"][0]
        profile["all_matched_alumni"] = alumni_res["results"]

    # 2. 查論文資料庫 (過濾為該作者的論文)
    thesis_res = query_thesis(name)
    if thesis_res.get("status") == "success" and thesis_res.get("results"):
        exact_author_theses = [t for t in thesis_res["results"] if name.lower() in t.get("author", "").lower() or name.lower() in t.get("english_author", "").lower()]
        profile["thesis_info"] = exact_author_theses if exact_author_theses else thesis_res["results"][:3]

    # 3. 查財產清冊
    prop_res = query_properties(name)
    if prop_res.get("status") == "success" and prop_res.get("results"):
        profile["managed_properties"] = prop_res["results"]

    # 4. 查經費帳本 (是否在備註出現)
    budget_res = query_budget(name)
    if budget_res.get("status") == "success" and budget_res.get("results"):
        profile["budget_records"] = budget_res["results"]

    # 彙總摘要
    cname = profile["basic_info"].get("中文姓名") if profile["basic_info"] else name
    grad_year = profile["basic_info"].get("畢業年份(民國)") or profile["basic_info"].get("畢業年度") if profile["basic_info"] else None
    dept = profile["basic_info"].get("系所", "") if profile["basic_info"] else ""
    thesis_title = profile["thesis_info"][0].get("title") if profile["thesis_info"] else "無登錄論文"
    prop_count = len(profile["managed_properties"])
    budget_count = len(profile["budget_records"])

    profile["summary"] = {
        "name": cname,
        "dept_and_year": f"{dept} (民國 {grad_year} 年畢業)" if grad_year else ("在學/未註明畢業年份" if profile["basic_info"] else "非名冊登錄校友或在學成員"),
        "thesis_title": thesis_title,
        "property_count": f"名下保管 {prop_count} 件實驗室財產設備",
        "budget_activity_count": f"經費帳本相關收支紀錄共 {budget_count} 筆"
    }

    # 動態產生精準建議
    suggestions = [
        f"提取並檢視 {cname} 的碩士口試簡報 (PPTX)",
        f"查看 {cname} 保管的 {prop_count} 件設備詳細清單與放置地點",
        f"查詢與 {cname} 同屆或相同研究主題之歷屆論文"
    ]

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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python query_service.py alumni|thesis|property|budget|rules|wiki|360|compliance [參數...]")
        sys.exit(0)
        
    cmd = sys.argv[1]
    kw = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if cmd == "alumni":
        res = query_alumni(kw)
    elif cmd == "thesis":
        res = query_thesis(kw)
    elif cmd == "property":
        res = query_properties(kw)
    elif cmd == "budget":
        res = query_budget(kw)
    elif cmd == "rules":
        res = query_accounting_rules(kw)
    elif cmd == "wiki":
        res = query_wiki(kw)
    elif cmd == "360":
        res = query_person_360(kw)
    elif cmd == "compliance":
        amt = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        vendor = sys.argv[4] if len(sys.argv) > 4 else "國內"
        res = evaluate_expense_compliance(item_name=kw, amount=amt, vendor_type=vendor)
    else:
        res = {"status": "error", "message": f"未知的指令: {cmd}"}
        
    print(json.dumps(res, ensure_ascii=False, indent=2))
