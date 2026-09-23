#!/usr/bin/env python3
"""
IRL Lab AI Agent - OpenClaw 啟動入口
自動設定 sys.path 以使用 /home/openclaw/irl_lab/pylib 中的依賴套件
"""
import sys
import os

# 注入自訂套件路徑（無需 root 或 venv）
PYLIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pylib")
if PYLIB not in sys.path:
    sys.path.insert(0, os.path.abspath(PYLIB))

# 設定 lab_assistant 與子模組路徑
LAB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lab_assistant")
for p in [LAB_DIR, os.path.join(LAB_DIR, "core"), os.path.join(LAB_DIR, "connectors")]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, os.path.abspath(p))

import argparse
import json
import re

def _clean_html_tags(obj):
    if isinstance(obj, str):
        # 將 <br>, <br/>, </br> 轉為換行
        text = re.sub(r'<\s*/?\s*br\s*/?>', '\n', obj, flags=re.IGNORECASE)
        # 去除 HTML 標籤
        text = re.sub(r'<\s*/?\s*(?:b|strong|div|span|p|tr|td|th|table|tbody|thead)\b[^>]*>', '', text, flags=re.IGNORECASE)
        return text
    elif isinstance(obj, list):
        return [_clean_html_tags(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: _clean_html_tags(v) for k, v in obj.items()}
    return obj

def safe_output(res):
    cleaned = _clean_html_tags(res)
    print(json.dumps(cleaned, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="IRL Lab AI Agent CLI")
    subparsers = parser.add_subparsers(dest="module", help="模組選擇")

    # NAS 檔案檢索
    nas_p = subparsers.add_parser("nas", help="NAS 論文與檔案檢索")
    nas_p.add_argument("action", choices=["match", "list", "read", "open"], help="操作類型")
    nas_p.add_argument("target", help="搜尋關鍵字或路徑")
    nas_p.add_argument("filename", nargs="?", help="檔案名稱（read/open 用）")

    # 知識庫問答
    query_p = subparsers.add_parser("query", help="實驗室知識庫問答")
    query_p.add_argument("action", choices=["members", "alumni", "property", "budget", "funds", "funds_report", "rules", "thesis", "thesis_topics", "property_inventory", "site", "360", "compliance", "leaves"], help="查詢類型")
    query_p.add_argument("keyword", nargs="?", default="", help="查詢關鍵字")

    # 發票辨識與自動記帳
    invoice_p = subparsers.add_parser("invoice", help="臺灣電子發票辨識、合規檢核與自動記帳")
    invoice_p.add_argument("action", choices=["decode", "bookkeep"], default="decode", nargs="?", help="發票解碼(decode)或自動記帳(bookkeep)")
    invoice_p.add_argument("image_path", nargs="?", default="", help="發票圖檔路徑（選填，預設最新媒體）")
    invoice_p.add_argument("--memo", default="", help="記帳備註（選填，bookkeep 用，若未提供則使用發票品項摘要）")

    # 公用經費記帳 (Google Sheets 雲端連動)
    budget_p = subparsers.add_parser("budget", help="Google Sheets 公用經費自動記帳與刪除")
    budget_p.add_argument("action", choices=["add", "delete", "recent"], help="記帳操作 (add/delete/recent)")
    budget_p.add_argument("--amount", type=float, default=0.0, help="收支金額（正數為收入，負數為支出）")
    budget_p.add_argument("--memo", default="", help="記帳備註")
    budget_p.add_argument("--date", default=None, help="記帳日期 (YYYY-MM-DD，選填，預設今天)")
    budget_p.add_argument("--index", type=int, default=None, help="刪除指定索引（-1 為最後一筆）")
    budget_p.add_argument("--n", type=int, default=10, help="查詢筆數")

    # 請假連動
    leave_p = subparsers.add_parser("leave", help="Google 行事曆請假連動")
    leave_p.add_argument("action", choices=["add", "cancel", "query"], help="登記、取消或查詢")
    leave_p.add_argument("member", nargs="?", default="", help="成員姓名")
    leave_p.add_argument("date", nargs="?", default="今天", help="請假日期")
    leave_p.add_argument("--start", default="10:00", help="開始時間")
    leave_p.add_argument("--end", default="17:00", help="結束時間")
    leave_p.add_argument("--reason", default="", help="事由")

    # Wiki 查詢
    wiki_p = subparsers.add_parser("wiki", help="MediaWiki 實驗室百科查詢")
    wiki_p.add_argument("topic", help="查詢主題")

    # 官網查詢
    site_p = subparsers.add_parser("site", help="IRL 實驗室官網查詢 (https://irl.ee.yzu.edu.tw/)")
    site_p.add_argument("topic", nargs="?", default="", help="官網單元關鍵字 (intro/advisor/cooperation/member/alumni/contact/recruits)")

    args = parser.parse_args()

    if args.module == "nas":
        import nas_reader
        if args.action == "match":
            res = nas_reader.fuzzy_find_student(args.target)
            safe_output(res)
        elif args.action == "list":
            res = nas_reader.nas_list(args.target)
            safe_output(res)
        elif args.action == "read":
            kw = args.filename if args.filename else "論文"
            folder = args.target
            if not folder.startswith("/"):
                m = nas_reader.fuzzy_find_student(folder)
                folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
            res = nas_reader.nas_read_file(folder, kw)
            safe_output(res)
        elif args.action == "open":
            kw = args.filename if args.filename else "論文"
            folder = args.target
            if not folder.startswith("/"):
                m = nas_reader.fuzzy_find_student(folder)
                folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
            res = nas_reader.nas_download_file_for_viewing(folder, kw, kw)
            safe_output(res)

    elif args.module == "query":
        import query_service
        kw = args.keyword or ""
        if args.action == "360":
            res = query_service.query_person_360(kw)
            safe_output(res)
        elif args.action in ("members", "member"):
            res = query_service.query_members(kw)
            safe_output(res)
        elif args.action == "alumni":
            res = query_service.query_alumni(kw)
            safe_output(res)
        elif args.action == "thesis":
            res = query_service.query_thesis(kw)
            safe_output(res)
        elif args.action == "thesis_topics":
            res = query_service.query_thesis_topics(kw)
            safe_output(res)
        elif args.action == "property":
            res = query_service.query_properties(kw)
            safe_output(res)
        elif args.action == "property_inventory":
            res = query_service.query_property_inventory(kw)
            safe_output(res)
        elif args.action in ("budget", "funds"):
            res = query_service.query_budget(kw)
            safe_output(res)
        elif args.action == "funds_report":
            res = query_service.query_funds_report(kw)
            safe_output(res)
        elif args.action == "rules":
            res = query_service.query_accounting_rules(kw)
            safe_output(res)
        elif args.action == "site":
            res = query_service.query_official_website(kw)
            safe_output(res)
        elif args.action == "leaves":
            res = query_service.query_leaves(kw)
            safe_output(res)
        elif args.action == "compliance":
            import re
            amt = 0
            name = kw
            num_match = re.search(r'(\d+(?:\.\d+)?)', kw)
            if num_match:
                try:
                    amt = float(num_match.group(1))
                except Exception:
                    amt = 0
                name = re.sub(r'(\d+(?:\.\d+)?)', '', kw).strip()
            res = query_service.evaluate_expense_compliance(item_name=name or "未指定品項", amount=amt)
            safe_output(res)

    elif args.module == "invoice":
        import invoice_reader
        img = args.image_path if args.image_path else None
        if args.action == "bookkeep":
            memo = args.memo if args.memo else None
            res = invoice_reader.bookkeep_invoice(image_path=img, memo_override=memo)
            safe_output(res)
        else:
            res = invoice_reader.decode_invoice(image_path=img)
            safe_output(res)

    elif args.module == "budget":
        import sheets_writer
        if args.action == "add":
            res = sheets_writer.append_transaction(amount=args.amount, memo=args.memo, date_str=args.date)
            safe_output(res)
        elif args.action == "delete":
            if args.index is not None and args.index == -1:
                res = sheets_writer.delete_last_transaction()
            elif args.memo:
                res = sheets_writer.delete_transaction_by_keyword(args.memo)
            else:
                res = sheets_writer.delete_last_transaction()
            safe_output(res)
        elif args.action == "recent":
            res = sheets_writer.read_recent_transactions(n=args.n)
            safe_output(res)

    elif args.module == "leave":
        import query_service
        if args.action == "add":
            res = query_service.apply_leave(
                member_name=args.member,
                date_str=args.date,
                start_time=args.start,
                end_time=args.end,
                reason=args.reason
            )
            safe_output(res)
        elif args.action == "cancel":
            res = query_service.cancel_leave(
                member_name=args.member,
                date_str=args.date if args.date != "今天" else None
            )
            safe_output(res)
        else:
            res = query_service.query_leaves(args.member or args.date)
            safe_output(res)

    elif args.module == "wiki":
        import wiki_reader
        res = wiki_reader.wiki_search(args.topic)
        safe_output(res)

    elif args.module == "site":
        import official_site_reader
        res = official_site_reader.query_official_site(args.topic)
        safe_output(res)

    else:
        parser.print_help()
        print("\n範例:")
        print("  python3 irl_agent.py nas match 顏伯丞")
        print("  python3 irl_agent.py nas list /IRLshare/畢業論文/")
        print("  python3 irl_agent.py query 360 顏伯丞")
        print("  python3 irl_agent.py wiki 報帳規定")
        print("  python3 irl_agent.py site cooperation")

if __name__ == "__main__":
    main()


