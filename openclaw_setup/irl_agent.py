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

# 設定 lab_assistant 路徑
LAB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lab_assistant")
if LAB_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(LAB_DIR))

import argparse

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
    query_p.add_argument("action", choices=["alumni", "property", "budget", "funds", "rules", "thesis", "site", "360", "compliance"], help="查詢類型")
    query_p.add_argument("keyword", nargs="?", default="", help="查詢關鍵字")

    # Wiki 查詢
    wiki_p = subparsers.add_parser("wiki", help="MediaWiki 實驗室百科查詢")
    wiki_p.add_argument("topic", help="查詢主題")

    # 官網查詢
    site_p = subparsers.add_parser("site", help="IRL 實驗室官網查詢 (https://irl.ee.yzu.edu.tw/)")
    site_p.add_argument("topic", nargs="?", default="", help="官網單元關鍵字 (intro/advisor/cooperation/member/alumni/contact/recruits)")

    args = parser.parse_args()

    if args.module == "nas":
        import nas_reader
        import json
        if args.action == "match":
            res = nas_reader.fuzzy_find_student(args.target)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "list":
            res = nas_reader.nas_list(args.target)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "read":
            kw = args.filename if args.filename else "論文"
            folder = args.target
            if not folder.startswith("/"):
                m = nas_reader.fuzzy_find_student(folder)
                folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
            res = nas_reader.nas_read_file(folder, kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "open":
            kw = args.filename if args.filename else "論文"
            folder = args.target
            if not folder.startswith("/"):
                m = nas_reader.fuzzy_find_student(folder)
                folder = m.get("path", f"/IRLshare/畢業論文/{folder}/")
            res = nas_reader.nas_download_file_for_viewing(folder, kw, kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))

    elif args.module == "query":
        import query_service
        import json
        kw = args.keyword or ""
        if args.action == "360":
            res = query_service.query_person_360(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "alumni":
            res = query_service.query_alumni(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "thesis":
            res = query_service.query_thesis(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "property":
            res = query_service.query_properties(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action in ("budget", "funds"):
            res = query_service.query_budget(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "rules":
            res = query_service.query_accounting_rules(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "site":
            res = query_service.query_official_website(kw)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif args.action == "compliance":
            res = query_service.evaluate_expense_compliance(item_name=kw, amount=10000)
            print(json.dumps(res, ensure_ascii=False, indent=2))

    elif args.module == "wiki":
        import wiki_reader
        import json
        res = wiki_reader.wiki_search(args.topic)
        print(json.dumps(res, ensure_ascii=False, indent=2))

    elif args.module == "site":
        import official_site_reader
        import json
        res = official_site_reader.query_official_site(args.topic)
        print(json.dumps(res, ensure_ascii=False, indent=2))

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


