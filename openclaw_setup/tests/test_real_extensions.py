# -*- coding: utf-8 -*-
"""
真實延伸功能單元測試套件 (test_real_extensions.py)
嚴格基於實驗室真實資料庫，驗證四大功能之正確性與格式合規性。
"""

import sys
import os
import json
import re

# 加入路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_DIR = os.path.dirname(CURRENT_DIR)
LAB_DIR = os.path.join(SETUP_DIR, "..", "IRL_Lab_AI_ agent", "lab_assistant")
if not os.path.exists(LAB_DIR):
    LAB_DIR = os.path.join(SETUP_DIR, "..", "lab_assistant")

sys.path.insert(0, os.path.abspath(LAB_DIR))
sys.path.insert(0, os.path.abspath(SETUP_DIR))

import query_service
import invoice_reader

def check_formatting_compliance(text):
    """檢查排版規範：零阿拉伯數字編號條列、零 HTML 標籤"""
    errs = []
    # 檢查是否以 1. 2. 3. 做為條列開頭
    bad_numbered = re.findall(r'^\s*\d+\.\s+', text, re.MULTILINE)
    if bad_numbered:
        errs.append(f"發現阿拉伯數字開頭條列: {bad_numbered[:3]}")
    # 檢查是否含有 HTML 標籤
    html_tags = re.findall(r'</?(?:b|i|br|span|div|p|table|tr|td|th)>', text, re.IGNORECASE)
    if html_tags:
        errs.append(f"發現 HTML 標籤: {html_tags[:3]}")
    return len(errs) == 0, "; ".join(errs)

def run_tests():
    total = 0
    passed = 0
    failures = []

    def test(name, fn):
        nonlocal total, passed
        total += 1
        try:
            ok, msg = fn()
            if ok:
                passed += 1
                print(f"[PASS] {name}")
            else:
                failures.append((name, msg))
                print(f"[FAIL] {name}: {msg}")
        except Exception as e:
            failures.append((name, str(e)))
            print(f"[ERROR] {name}: {e}")

    print("======================================================================")
    print("🚀 IRL Lab AI Assistant - 真實延伸功能自動化驗證測試開始")
    print("======================================================================")

    # 1. 發票 QR 解析與會計防呆檢核
    def test_inv_parse():
        mock_qr = [
            "AB123456781130922123400000DAC00000DAC0096688012345678**品項A:1:1000:品項B:2:1250"
        ]
        res = invoice_reader.parse_taiwan_invoice_qr(mock_qr)
        if not res.get("success"):
            return False, "發票解析未回傳 success"
        info = res.get("invoice_info", {})
        if info.get("total_amount") != 3500:
            return False, f"總金額解析錯誤: {info.get('total_amount')}"
        comp = res.get("compliance", {})
        if not comp.get("yzu_ban_verified"):
            return False, "元智統編核驗失敗"
        return True, ""

    test("1. 發票 QR Code 辨識與合規防呆檢核", test_inv_parse)

    # 2. 公用經費歷年收支總覽報表
    def test_funds_summary():
        res = query_service.query_funds_report()
        if res.get("status") != "success":
            return False, "經費報表回傳非 success"
        md = res.get("report_markdown", "")
        if "實驗室公用經費歷年收支與結餘總覽報表" not in md:
            return False, "報表標題未正確呈現"
        comp_ok, comp_err = check_formatting_compliance(md)
        if not comp_ok:
            return False, f"排版不合規: {comp_err}"
        return True, ""

    test("2. 公用經費歷年收支總覽報表", test_funds_summary)

    # 3. 公用經費特定年份 (2023) 季度走勢與用途分類
    def test_funds_year():
        res = query_service.query_funds_report("2023")
        if res.get("status") != "success":
            return False, "2023 經費報表回傳非 success"
        if res.get("year") != 2023:
            return False, f"年份解析錯誤: {res.get('year')}"
        md = res.get("report_markdown", "")
        if "季度收支走勢分佈" not in md or "支出用途分類統計" not in md:
            return False, "缺少季度或用途分類區塊"
        comp_ok, comp_err = check_formatting_compliance(md)
        if not comp_ok:
            return False, f"排版不合規: {comp_err}"
        return True, ""

    test("3. 公用經費 2023 年季度與用途分類報表", test_funds_year)

    # 4. 論文歷屆研究主題排行榜
    def test_thesis_topics_ranking():
        res = query_service.query_thesis_topics()
        if res.get("status") != "success":
            return False, "論文主題排行回傳非 success"
        md = res.get("report_markdown", "")
        if "物聯網" not in md:
            return False, "預期核心主題物聯網未出現"
        comp_ok, comp_err = check_formatting_compliance(md)
        if not comp_ok:
            return False, f"排版不合規: {comp_err}"
        return True, ""

    test("4. 歷屆碩士論文核心研究主題排行榜", test_thesis_topics_ranking)

    # 5. 論文特定領域 (邊緣運算) 歷屆清冊
    def test_thesis_domain():
        res = query_service.query_thesis_topics("邊緣運算")
        if res.get("status") != "success":
            return False, "邊緣運算主題清冊回傳非 success"
        theses = res.get("theses", [])
        if len(theses) < 2:
            return False, f"邊緣運算論文篇數不足: {len(theses)}"
        # 驗證是否按年份遞增排序
        years = [t.get("year_roc", 0) for t in theses]
        if years != sorted(years):
            return False, f"論文排序未按年份由舊到新: {years}"
        md = res.get("report_markdown", "")
        comp_ok, comp_err = check_formatting_compliance(md)
        if not comp_ok:
            return False, f"排版不合規: {comp_err}"
        return True, ""

    test("5. 邊緣運算主題歷屆論文客觀清冊", test_thesis_domain)

    # 6. 70640 實驗室全室設備盤點報表
    def test_lab_inventory():
        res = query_service.query_property_inventory("70640")
        if res.get("status") != "success":
            return False, "70640 盤點報表回傳非 success"
        if res.get("total_count", 0) < 50:
            return False, f"設備總數異常: {res.get('total_count')}"
        md = res.get("report_markdown", "")
        if "設備類型分類統計" not in md:
            return False, "缺少設備類型分類統計"
        comp_ok, comp_err = check_formatting_compliance(md)
        if not comp_ok:
            return False, f"排版不合規: {comp_err}"
        return True, ""

    test("6. 70640 實驗室全室設備盤點總表", test_lab_inventory)

    # 7. 成員個人名下保管設備對帳單 (邱子倫)
    def test_person_inventory():
        res = query_service.query_property_inventory("邱子倫")
        if res.get("status") != "success":
            return False, "邱子倫設備對帳單回傳非 success"
        if res.get("count", 0) < 1:
            return False, "邱子倫名下未找到保管設備"
        md = res.get("report_markdown", "")
        if "EE11201301" not in md:
            return False, "未找到邱子倫的財產編號 EE11201301"
        comp_ok, comp_err = check_formatting_compliance(md)
        if not comp_ok:
            return False, f"排版不合規: {comp_err}"
        return True, ""

    test("7. 成員個人名下設備對帳單 (邱子倫)", test_person_inventory)

    print("======================================================================")
    print(f"📊 測試總計: 共 {total} 項測試 | 通過: {passed} 項 | 失敗: {len(failures)} 項")
    print(f"🎯 通過率: {(passed/total)*100:.1f}%")
    print("======================================================================")

    if failures:
        sys.exit(1)
    else:
        print("✅ 四大真實延伸功能全數通過驗證！")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
