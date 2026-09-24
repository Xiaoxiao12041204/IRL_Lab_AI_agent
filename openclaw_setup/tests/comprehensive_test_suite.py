#!/usr/bin/env python3
"""
IRL Lab AI Assistant - Full Comprehensive Test Suite
驗證全系統 10 大查詢路徑在真實環境下的數據完整性、排版欄位、延伸建議品質與無痕自動提取功能。
"""
import os
import sys
import json
import time

# 動態支援本機 Windows 與 WSL Linux 路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_DIR = os.path.dirname(CURRENT_DIR)
IRL_ROOT = os.path.dirname(SETUP_DIR)

for cand in [
    os.path.join(IRL_ROOT, "lab_assistant"),
    os.path.join(IRL_ROOT, "lab_assistant", "core"),
    os.path.join(IRL_ROOT, "lab_assistant", "connectors"),
    os.path.join(IRL_ROOT, "IRL_Lab_AI_ agent", "lab_assistant"),
    os.path.join(IRL_ROOT, "IRL_Lab_AI_ agent", "lab_assistant", "core"),
    os.path.join(IRL_ROOT, "IRL_Lab_AI_ agent", "lab_assistant", "connectors"),
    os.path.join(IRL_ROOT, "pylib"),
    SETUP_DIR
]:
    if os.path.exists(cand) and cand not in sys.path:
        sys.path.insert(0, cand)

import query_service
import nas_reader
import official_site_reader
import wiki_reader

test_results = []

def run_test(category, test_name, func, args=(), kwargs=None, validator=None):
    if kwargs is None:
        kwargs = {}
    t0 = time.perf_counter()
    status = "PASS"
    error_msg = ""
    payload = None
    try:
        payload = func(*args, **kwargs)
        if isinstance(payload, dict):
            if payload.get("status") == "error":
                status = "FAIL"
                error_msg = payload.get("message", "Status returned error")
        if validator and status == "PASS":
            valid_ok, valid_err = validator(payload)
            if not valid_ok:
                status = "FAIL"
                error_msg = valid_err
    except Exception as e:
        status = "FAIL"
        error_msg = str(e)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    
    res_entry = {
        "category": category,
        "test_name": test_name,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "error": error_msg,
        "suggestions": payload.get("suggestions") if isinstance(payload, dict) else []
    }
    test_results.append(res_entry)
    print(f"[{status}] {category} - {test_name} ({elapsed_ms}ms) {error_msg}")
    return status == "PASS"

def main():
    print("=" * 70)
    print("🚀 IRL Lab AI Assistant - 全功能端到端深度驗證測試開始")
    print("=" * 70)

    # 1. 現役成員查詢驗證 (query_members)
    def val_members_all(res):
        items = res.get("items", [])
        if len(items) < 6:
            return False, f"現役成員數過少: {len(items)}"
        names = [x.get("中文姓名") for x in items]
        if "邱子倫" not in names or "蕭宇傑" not in names:
            return False, f"缺少核心現役成員: {names}"
        # 檢查延伸建議是否無冗餘
        suggs = res.get("suggestions", [])
        if any("70640 實驗室成員名單" in s for s in suggs):
            return False, "建議中包含冗餘的查詢成員名單"
        return True, ""

    run_test("1. 現役成員名冊", "全體現役成員查詢 (無關鍵字)", query_service.query_members, (), validator=val_members_all)
    run_test("1. 現役成員名冊", "單一成員查詢 (邱子倫)", query_service.query_members, ("邱子倫",),
             validator=lambda r: (r.get("count", 0) >= 1, "未找到邱子倫"))

    # 2. 歷屆校友名冊驗證 (query_alumni)
    run_test("2. 歷屆畢業校友", "全體校友名冊概覽", query_service.query_alumni, (),
             validator=lambda r: (len(r.get("items", [])) >= 40, "校友總數低於 40 位"))
    run_test("2. 歷屆畢業校友", "特定年份校友 (112年)", query_service.query_alumni, ("112",),
             validator=lambda r: (r.get("count", 0) >= 1, "未找到 112 年校友"))
    run_test("2. 歷屆畢業校友", "特定姓名校友 (唐嘉鋒)", query_service.query_alumni, ("唐嘉鋒",),
             validator=lambda r: (r.get("count", 0) == 1, "唐嘉鋒校友筆數異常"))

    # 3. 設備財產清冊驗證 (query_properties)
    run_test("3. 設備與財產清冊", "全體設備清冊查詢", query_service.query_properties, (),
             validator=lambda r: (len(r.get("data", [])) >= 50 if isinstance(r.get("data"), list) else len(r.get("data", {}).get("財產列表", [])) >= 50, "設備總數低於 50 件"))
    run_test("3. 設備與財產清冊", "特定位置設備 (70640)", query_service.query_properties, ("70640",),
             validator=lambda r: (r.get("count", 0) >= 1, "未找到 70640 設備"))
    run_test("3. 設備與財產清冊", "特定主機/GPU (RTX)", query_service.query_properties, ("RTX",),
             validator=lambda r: (r.get("count", 0) >= 1, "未找到 RTX 相關設備"))

    # 4. 經費與帳本收支驗證 (query_funds / query_budget)
    def val_funds_numeric(res):
        suggs = res.get("suggestions", [])
        if any("『10』" in s or "『5』" in s for s in suggs):
            return False, f"建議中包含純數字字串模板錯誤: {suggs}"
        if len(res.get("ledger_details", [])) < 5:
            return False, "回傳帳本筆數不足"
        return True, ""

    run_test("4. 經費收支與帳本", "最近 10 筆經費紀錄查詢 ('10')", query_service.query_budget, ("10",), validator=val_funds_numeric)
    run_test("4. 經費收支與帳本", "全域經費結餘查詢 (空字串)", query_service.query_budget, ("",),
             validator=lambda r: (r.get("current_balance") is not None, "未回傳當前結餘"))
    run_test("4. 經費收支與帳本", "特定項目收支查詢 ('零食')", query_service.query_budget, ("零食",),
             validator=lambda r: (r.get("matched_ledger_count", 0) >= 1, "未找到零食相關紀錄"))

    # 5. 會計報帳規章驗證 (query_accounting_rules)
    def val_rules_general(res):
        if not res.get("is_general_overview") and "快速啟動步驟" in res.get("results", [{}])[0].get("主類別", ""):
            if len(res.get("results", [])) <= 1:
                return False, "全域報帳查詢僅回傳快速啟動步驟，缺少四大核心規章資料！"
        data = res.get("data") or res.get("results")
        if not data:
            return False, "報帳規章資料為空"
        return True, ""

    run_test("5. 會計報帳規章", "通用報帳規定查詢 ('報帳規定')", query_service.query_accounting_rules, ("報帳規定",), validator=val_rules_general)
    run_test("5. 會計報帳規章", "通用報帳查詢 ('報帳')", query_service.query_accounting_rules, ("報帳",), validator=val_rules_general)
    run_test("5. 會計報帳規章", "特定項目規章查詢 ('便當')", query_service.query_accounting_rules, ("便當",),
             validator=lambda r: (len(r.get("results", [])) >= 1, "未找到便當核銷規範"))
    run_test("5. 會計報帳規章", "特定項目規章查詢 ('國外勞務')", query_service.query_accounting_rules, ("國外勞務",),
             validator=lambda r: (len(r.get("results", [])) >= 1, "未找到國外勞務/API核銷規範"))
    run_test("5. 會計報帳規章", "特定項目規章查詢 ('差旅費')", query_service.query_accounting_rules, ("差旅",),
             validator=lambda r: (len(r.get("results", [])) >= 1, "未找到差旅費核銷規範"))

    # 6. 碩士畢業論文與摘要解讀驗證 (query_thesis)
    def val_thesis_detail(res):
        results = res.get("results", [])
        if not results:
            return False, "未回傳論文結果"
        first = results[0]
        if not first.get("title"):
            return False, "論文題目缺失"
        if not first.get("abstract_preview"):
            return False, "論文摘要預覽 (abstract_preview) 缺失"
        if len(first.get("abstract_preview", "")) < 100:
            return False, f"論文摘要長度過短: {len(first.get('abstract_preview', ''))}"
        # 檢查是否已提取檔案
        if not first.get("auto_extracted_file"):
            return False, "未自動提取檔案至 thesis_viewer"
        return True, ""

    run_test("6. 歷屆碩士論文", "張浚暢 論文檢索與自動提取", query_service.query_thesis, ("張浚暢",), validator=val_thesis_detail)
    run_test("6. 歷屆碩士論文", "易子杰 論文檢索與自動提取 (防外文干擾)", query_service.query_thesis, ("易子杰",), validator=val_thesis_detail)
    run_test("6. 歷屆碩士論文", "林威諭 論文檢索與自動提取 (防講稿干擾)", query_service.query_thesis, ("林威諭",), validator=val_thesis_detail)
    run_test("6. 歷屆碩士論文", "向禮勤 論文檢索與自動提取", query_service.query_thesis, ("向禮勤",), validator=val_thesis_detail)

    # 7. 360 度成員全景速查驗證 (query_person_360)
    def val_360(res):
        data = res.get("data", {})
        summary = data.get("summary", {})
        if not summary.get("name"):
            return False, "360 摘要姓名缺失"
        if not summary.get("dept_and_year"):
            return False, "身分或系所年度缺失"
        suggs = res.get("suggestions", [])
        if any("0 件設備" in s for s in suggs):
            return False, f"建議中包含 '0 件設備' 瑕疵: {suggs}"
        return True, ""

    run_test("7. 360度人物全景", "現役成員全景速查 (蕭宇傑)", query_service.query_person_360, ("蕭宇傑",), validator=val_360)
    run_test("7. 360度人物全景", "現役助理全景速查 (邱子倫)", query_service.query_person_360, ("邱子倫",), validator=val_360)
    run_test("7. 360度人物全景", "已畢業校友全景速查 (顏伯丞)", query_service.query_person_360, ("顏伯丞",), validator=val_360)

    # 8. 官網即時爬取檢索驗證 (official_site_reader)
    run_test("8. 實驗室官網", "官網成員名冊 (member)", official_site_reader.query_official_site, ("member",),
             validator=lambda r: (r.get("matched_count", 0) >= 1, "官網成員頁面抓取失敗"))
    run_test("8. 實驗室官網", "官網產學合作 (cooperation)", official_site_reader.query_official_site, ("cooperation",),
             validator=lambda r: (r.get("matched_count", 0) >= 1, "官網產學合作頁面抓取失敗"))
    run_test("8. 實驗室官網", "官網誠徵新成員 (recruits)", official_site_reader.query_official_site, ("recruits",),
             validator=lambda r: (r.get("matched_count", 0) >= 1, "官網誠徵新成員頁面抓取失敗"))

    # 9. MediaWiki 實驗室維基檢索 (wiki_reader)
    run_test("9. MediaWiki 百科", "維基公用經費檢索 ('經費')", wiki_reader.wiki_search, ("經費",),
             validator=lambda r: (r.get("count", 0) >= 1, "Wiki 經費頁面檢索失敗"))
    run_test("9. MediaWiki 百科", "維基報帳規定檢索 ('報帳')", wiki_reader.wiki_search, ("報帳",),
             validator=lambda r: (r.get("count", 0) >= 1, "Wiki 報帳頁面檢索失敗"))

    # 10. 報帳合規防呆試算 (evaluate_expense_compliance)
    run_test("10. 報帳合規防呆試算", "國內小額採購 (5,000元)", query_service.evaluate_expense_compliance, ("耗材", 5000),
             validator=lambda r: (r.get("status") == "success" and r.get("tax_calculation", {}).get("total_payable") == 5000.0, "小額試算金額異常"))
    run_test("10. 報帳合規防呆試算", "大額設備採購需比價 (150,000元)", query_service.evaluate_expense_compliance, ("伺服器", 150000),
             validator=lambda r: (any("比價" in d.get("detail", "") or "招標" in d.get("detail", "") for d in r.get("compliance_checklist", [])), "未提示比價要求"))
    run_test("10. 報帳合規防呆試算", "國外勞務 OpenAI 試算 (1,000元外加5%稅)", query_service.evaluate_expense_compliance, ("OpenAI API", 1000, "境外", True),
             validator=lambda r: (r.get("tax_calculation", {}).get("estimated_tax") == 50.0 and r.get("tax_calculation", {}).get("total_payable") == 1050.0, "境外稅額計算錯誤"))

    # 11. Google 日曆請假查詢 (query_leaves)
    run_test("11. Google日曆請假查詢", "今日請假名冊查詢 ('今天')", query_service.query_leaves, ("今天",),
             validator=lambda r: (r.get("status") == "success" and "leaves" in r, "今日請假查詢失敗"))
    run_test("11. Google日曆請假查詢", "特定成員請假歷史 ('倫廣')", query_service.query_leaves, ("倫廣",),
             validator=lambda r: (r.get("status") == "success" and "history_leaves" in r, "成員請假查詢失敗"))
    run_test("11. Google日曆請假查詢", "特定日期請假檢索 ('2026-09-14')", query_service.query_leaves, ("2026-09-14",),
             validator=lambda r: (r.get("status") == "success" and "leaves" in r, "特定日期請假查詢失敗"))
    run_test("11. Google日曆請假查詢", "單週請假查詢 ('這禮拜有誰請假')", query_service.query_leaves, ("這禮拜有誰請假",),
             validator=lambda r: (r.get("status") == "success" and r.get("query_type") == "week_range" and " ~ " in r.get("range", ""), "單週請假查詢失敗"))
    run_test("11. Google日曆請假查詢", "相對月份請假查詢 ('上個月呢')", query_service.query_leaves, ("上個月呢",),
             validator=lambda r: (r.get("status") == "success" and r.get("query_type") == "month_range" and r.get("count", 0) > 0, "上個月請假查詢失敗"))
    run_test("11. Google日曆請假查詢", "特定月份請假查詢 ('8月份')", query_service.query_leaves, ("8月份",),
             validator=lambda r: (r.get("status") == "success" and r.get("query_type") == "month_range" and r.get("count", 0) == 10, "8月份請假查詢失敗"))
    run_test("11. Google日曆請假查詢", "成員錯字自動校正查詢 ('林銘璽')", query_service.query_leaves, ("林銘璽",),
             validator=lambda r: (r.get("status") == "success" and r.get("member") == "銘聖", "錯字校正查詢失敗"))
    import google_calendar_reader
    run_test("11. Google日曆請假查詢", "姓名標準化函數驗證 ('政宇')", google_calendar_reader.normalize_member_name, ("政宇",),
             validator=lambda r: (r.get("display_name") == "正宇" and r.get("was_corrected") == True, "標準化函數失敗"))

    print("=" * 70)
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r["status"] == "PASS")
    failed_tests = total_tests - passed_tests
    print(f"📊 測試總計: 共 {total_tests} 項測試 | 通過: {passed_tests} 項 | 失敗: {failed_tests} 項")
    print(f"🎯 綜合通過率: {round(passed_tests / total_tests * 100, 2)}%")
    print("=" * 70)

    if failed_tests > 0:
        print("❌ 失敗項目列表:")
        for r in test_results:
            if r["status"] == "FAIL":
                print(f"  - [{r['category']}] {r['test_name']}: {r['error']}")
        sys.exit(1)
    else:
        print("✅ 全項目端到端驗證 100% 通過！")

if __name__ == "__main__":
    main()
