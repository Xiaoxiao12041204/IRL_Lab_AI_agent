import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB_DIR = os.path.join(BASE_DIR, "..", "IRL_Lab_AI_ agent", "lab_assistant") if not os.path.exists("/home/openclaw/irl_lab/lab_assistant") else "/home/openclaw/irl_lab/lab_assistant"
for p in [LAB_DIR, os.path.join(LAB_DIR, "core"), os.path.join(LAB_DIR, "connectors")]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

import invoice_reader
import query_service

print("=== 1. 測試發票 QR 字串解析與記帳預覽 ===")
qr_data = ["AB123456781130920123400000300000003150096688012345678AAAAAAAAAAAAAAAAAAAAAAAA:**********:1:1:1:研討會便當:3:105"]
res = invoice_reader.parse_taiwan_invoice_qr(qr_data)
res["success"] = True
main_info = res.get("main_info", {})
date_str = main_info.get("invoice_date", "")
total_amt = main_info.get("total_amount", 0)
items = res.get("items", [])

items_summary = "研討會便當"
res["bookkeeping_preview"] = {
    "can_auto_bookkeep": True,
    "amount": -abs(total_amt),
    "date": date_str,
    "default_memo": f"發票報銷({items_summary})",
    "suggested_command": f"python3 /home/openclaw/irl_lab/openclaw_setup/irl_agent.py invoice bookkeep --memo \"發票報銷({items_summary})\""
}

print(json.dumps(res, ensure_ascii=False, indent=2))

print("\n=== 2. 測試手動/自動記帳寫入 ===")
import sheets_writer
add_res = sheets_writer.append_transaction(amount=-315, memo="測試發票自動記帳(研討會便當)", date_str="2024-09-20")
print("記帳結果:", json.dumps(add_res, ensure_ascii=False, indent=2))

print("\n=== 3. 測試刪除剛才的測試記帳 ===")
del_res = sheets_writer.delete_last_transaction()
print("刪除結果:", json.dumps(del_res, ensure_ascii=False, indent=2))

print("\n=== 4. 測試 CLI invoice --help 與 budget --help ===")
os.system("python3 /home/openclaw/irl_lab/openclaw_setup/irl_agent.py invoice --help")
os.system("python3 /home/openclaw/irl_lab/openclaw_setup/irl_agent.py budget --help")
