#!/usr/bin/env python3
"""
IRL Lab AI Assistant - 臺灣電子發票 QR Code 辨識與解碼模組
支援自動搜尋 OpenClaw 最新上傳圖檔、多層影像前處理、QR Code 幾何檢測與品項明細精準提取。
"""

import os
import sys
import glob
import re
import json

# 注入自訂套件路徑（以支援 pylib 中的 opencv 與 numpy）
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) in ('connectors', 'core') else CURRENT_DIR
PYLIB_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "pylib"))
if PYLIB_DIR not in sys.path:
    sys.path.insert(0, PYLIB_DIR)

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


def get_latest_inbound_image():
    """
    自動搜尋 OpenClaw 傳入媒體資料夾中的最新圖片
    """
    candidate_dirs = [
        os.path.expanduser("~/.openclaw/media/inbound"),
        "/home/openclaw/.openclaw/media/inbound",
        os.path.join(BASE_DIR, "media"),
        os.getcwd()
    ]
    
    image_extensions = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.PNG", "*.JPG", "*.JPEG", "*.WEBP")
    found_files = []
    
    for d in candidate_dirs:
        if os.path.exists(d):
            for ext in image_extensions:
                found_files.extend(glob.glob(os.path.join(d, ext)))
                
    if not found_files:
        return None
        
    # 按最後修改時間排序，最新的在最前面
    found_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return found_files[0]


def preprocess_image_variants(img):
    """
    產生不同影像前處理變形，以提高 QR Code 在不同光照、縮放與對比度下的檢出率
    """
    variants = [img]
    
    # 灰階版本
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    variants.append(gray)
    
    # 對比度增強 (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    variants.append(enhanced)
    
    # 二值化 (Otsu)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    variants.append(otsu)
    
    # 尺寸放大 (若原圖太小，例如寬度小於 800px)
    h, w = gray.shape[:2]
    if w < 1000:
        scale = 2.0 if w < 600 else 1.5
        resized = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        variants.append(resized)
        
    return variants


def scan_qr_codes(image_path):
    """
    使用 OpenCV QRCodeDetector 掃描影像中的所有 QR Code
    """
    if not CV2_AVAILABLE:
        return False, [], "環境中未安裝 OpenCV (cv2) 套件"
        
    if not os.path.exists(image_path):
        return False, [], f"找不到圖檔：{image_path}"
        
    img = cv2.imread(image_path)
    if img is None:
        return False, [], f"無法讀取圖檔內容：{image_path}"
        
    detector = cv2.QRCodeDetector()
    decoded_texts = set()
    
    variants = preprocess_image_variants(img)
    for v in variants:
        try:
            # 嘗試檢測多個 QR Code
            retval, decoded_info, points, straight_qrcode = detector.detectAndDecodeMulti(v)
            if retval and decoded_info:
                for text in decoded_info:
                    if text and text.strip():
                        decoded_texts.add(text.strip())
        except Exception:
            pass
            
        # 若已找到至少 1 個包含發票特徵的 QR Code，可提早退出
        if any(re.match(r"^[A-Z]{2}\d{8}", t) for t in decoded_texts):
            break
            
    # 如果 detectAndDecodeMulti 沒抓到，嘗試單一 detectAndDecode
    if not decoded_texts:
        for v in variants:
            try:
                text, points, _ = detector.detectAndDecode(v)
                if text and text.strip():
                    decoded_texts.add(text.strip())
                    if re.match(r"^[A-Z]{2}\d{8}", text.strip()):
                        break
            except Exception:
                pass

    return True, list(decoded_texts), ""


def parse_taiwan_invoice_qr(qr_texts):
    """
    深度解析臺灣電子發票 QR Code
    遵循財政部電子發票二維條碼規格
    """
    main_info = {}
    items = []
    
    for text in qr_texts:
        if not text:
            continue
        clean = text.strip()
        
        # 1. 檢驗是否為左側主條碼（支援有檢驗碼與無檢驗碼之變形格式）
        m = re.match(
            r"^([A-Z]{2}\d{8})"           # 1. 發票字軌號碼 (10碼)
            r"(\d{7})"                    # 2. 開立日期 民國年YYYMMDD (7碼)
            r"(\d{4})"                    # 3. 隨機碼 (4碼)
            r"([0-9a-fA-F]{8})"           # 4. 銷售額 16進位 (8碼)
            r"([0-9a-fA-F]{8})"           # 5. 總金額 16進位 (8碼)
            r"(\d{8})"                    # 6. 買方統編 (8碼)
            r"(\d{8})"                    # 7. 賣方統編 (8碼)
            r"([0-9a-zA-Z\+/=]{24})?"     # 8. 檢驗碼 (可選)
            r"(.*)$",                     # 9. 剩餘字串
            clean
        )
        if m:
            inv_num, inv_date_raw, rand_code, sales_hex, total_hex, buyer_ban, seller_ban, check_code, rest = m.groups()
            
            # 日期轉換（民國年 -> 西元年）
            try:
                y = int(inv_date_raw[:3]) + 1911
                m_month = int(inv_date_raw[3:5])
                d = int(inv_date_raw[5:7])
                date_str = f"{y:04d}-{m_month:02d}-{d:02d}"
            except Exception:
                date_str = inv_date_raw
                
            # 金額轉換（16 進位 -> 10 進位整數）
            try:
                sales_amt = int(sales_hex, 16)
                total_amt = int(total_hex, 16)
            except Exception:
                sales_amt = 0
                total_amt = 0
                
            main_info = {
                "invoice_number": f"{inv_num[:2]}-{inv_num[2:]}",
                "date": date_str,
                "random_code": rand_code,
                "sales_amount": sales_amt,
                "total_amount": total_amt,
                "buyer_ban": buyer_ban if buyer_ban != "00000000" else "無統編（個人消費）",
                "seller_ban": seller_ban,
                "check_code": check_code or "",
                "raw_header": clean[:53]
            }
            
            # 左條碼後方延伸的品項明細 (格式可能為 :**********:<總筆數>:<總項數>:<編碼>:<品名>:<數量>:<單價>...)
            if rest:
                if "**" in rest:
                    item_part = rest.split("**", 1)[1]
                    items.extend(parse_item_tokens(item_part))
                elif ":**********:" in rest:
                    item_part = rest.split(":**********:", 1)[1]
                    items.extend(parse_item_tokens(item_part))
                elif ":" in rest:
                    items.extend(parse_colon_items(rest))
                
        elif clean.startswith("**"):
            # 2. 右側副條碼（以 ** 開頭的商品品項明細）
            item_part = clean[2:]
            items.extend(parse_item_tokens(item_part))

    # 進行元智大學報帳合規防呆檢核
    compliance = audit_invoice_compliance(main_info, items)
    
    return {
        "success": bool(main_info),
        "qr_detected": bool(qr_texts),
        "raw_qr_count": len(qr_texts),
        "invoice_info": main_info,
        "items": items,
        "compliance": compliance
    }


def parse_item_tokens(item_str):
    """
    智慧解析以冒號分隔的品項資訊
    支援標準 3 欄式 (品名:數量:單價) 以及星號/數量相連 (品名★數量:單價) 之變形
    """
    items = []
    if item_str.startswith("**"):
        item_str = item_str[2:]
        
    parts = [p.strip() for p in item_str.split(":") if p.strip()]
    
    # 移除開頭所有純星號 token (如 :**********:)
    while parts and all(c == "*" for c in parts[0]):
        parts.pop(0)
        
    # 過濾前置的通用設定旗標（如 4:4:1 或 1:1:1 三項計數旗標）
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
        parts = parts[3:]
        
    while parts and parts[0].isdigit() and len(parts[0]) <= 2:
        parts.pop(0)
        
    idx = 0
    while idx < len(parts):
        token = parts[idx]
        if all(c == "*" for c in token):
            idx += 1
            continue
            
        # 情況 A: token 本身是「品名★數量」或「品名*數量」（例如「鮮蝦水餃★6」）且下一欄是單價
        m_name_qty = re.match(r"^(.*?)[★\*](\d+(?:\.\d+)?)$", token)
        if m_name_qty and idx + 1 < len(parts):
            name = m_name_qty.group(1).strip()
            qty_str = m_name_qty.group(2)
            qty_val = float(qty_str) if "." in qty_str else int(qty_str)
            price_str = parts[idx+1]
            try:
                price_val = float(price_str) if "." in price_str else int(price_str)
            except ValueError:
                price_val = price_str
            subtotal = qty_val * price_val if isinstance(qty_val, (int, float)) and isinstance(price_val, (int, float)) else None
            items.append({
                "name": name,
                "quantity": qty_val,
                "unit_price": price_val,
                "subtotal": subtotal
            })
            idx += 2
            continue
            
        # 情況 B: 標準 3 欄式 (品名:數量:單價)
        if idx + 2 < len(parts):
            name = parts[idx].rstrip("★*").strip()
            qty_str = parts[idx+1]
            price_str = parts[idx+2]
            try:
                qty_val = float(qty_str) if "." in qty_str else int(qty_str)
                price_val = float(price_str) if "." in price_str else int(price_str)
                subtotal = qty_val * price_val
                items.append({
                    "name": name,
                    "quantity": qty_val,
                    "unit_price": price_val,
                    "subtotal": subtotal
                })
                idx += 3
                continue
            except ValueError:
                pass
                
        idx += 1
        
    return items


def parse_colon_items(rest_str):
    """
    從冒號開頭的字串中解析品項
    """
    parts = [p.strip() for p in rest_str.split(":") if p.strip()]
    # 跳過開頭的星號遮罩或設定值
    filtered = []
    for p in parts:
        if all(c == "*" for c in p):
            continue
        filtered.append(p)
    return parse_item_tokens(":".join(filtered))


def audit_invoice_compliance(main_info, items):
    """
    依據元智大學與 IRL 實驗室會計報帳規章進行防呆檢核
    """
    if not main_info:
        return {}
        
    yzu_ban = "00966880"
    buyer_ban = main_info.get("buyer_ban", "")
    total_amt = main_info.get("total_amount", 0)
    
    # 1. 統一編號檢核
    is_yzu = (buyer_ban == yzu_ban)
    ban_status = "合格（已開立元智大學統編 00966880）" if is_yzu else f"⚠️ 未開立元智統編（目前為 {buyer_ban}，需向店家申請補打統編，或由經手人手寫補正元智統編並加蓋店家統一發票章）"
    
    # 2. 採購金額門檻
    if total_amt < 10000:
        threshold_rule = "未達 1 萬元，免附估價單，填具黏存單即可核銷。"
    elif 10000 <= total_amt < 100000:
        threshold_rule = "達 1 萬～10 萬元，需檢附 1 家估價單，且需至保管組登錄財產/物品標籤後方可報銷。"
    else:
        threshold_rule = "達 10 萬元以上，屬大額採購，需檢附 2 家以上廠商估價單進行比價程序。"
        
    # 3. 便當與會議餐費檢查
    has_meal = any(any(k in it.get("name", "") for k in ["便當", "餐", "飯", "麵", "飲料", "點心"]) for it in items)
    meal_rule = "若為會議便當餐費，每人核銷上限為 100～120 元，請務必檢附【會議簽到名冊】與【零用金單】。" if has_meal else "無特別餐飲標記，若屬會議性質請注意餐費上限。"
    
    # 4. 核銷期程規範
    deadline_rule = "發票開立日起算 4 個月內須完成送會計室審核，逾期需填寫延遲說明書並由計畫主持人郭文興老師蓋章。"
    
    return {
        "yzu_ban_verified": is_yzu,
        "ban_note": ban_status,
        "procurement_threshold": threshold_rule,
        "meal_compliance": meal_rule,
        "deadline_note": deadline_rule
    }


def decode_invoice(image_path=None):
    """
    主要執行函數：讀取發票圖檔、解碼 QR Code 並輸出結構化數據
    """
    if not image_path:
        image_path = get_latest_inbound_image()
        
    if not image_path:
        return {
            "success": False,
            "qr_detected": False,
            "message": "未指定圖片路徑，且未在媒體資料夾中找到任何傳入圖片。"
        }
        
    read_ok, qr_texts, err_msg = scan_qr_codes(image_path)
    if not read_ok:
        return {
            "success": False,
            "qr_detected": False,
            "image_path": image_path,
            "message": err_msg
        }
        
    if not qr_texts:
        return {
            "success": False,
            "qr_detected": False,
            "image_path": image_path,
            "message": "在圖片中未檢測到清晰的 QR Code（可能由於解析度過低、反光、皺摺或屬於傳統長條/手開發票）。建議改用視覺多模態 OCR 模型直接辨識。"
        }
        
    parse_result = parse_taiwan_invoice_qr(qr_texts)
    parse_result["image_path"] = image_path
    
    if not parse_result.get("success"):
        parse_result["message"] = "有檢測到 QR Code，但格式不符合臺灣電子發票標準規格。"
    else:
        inv_info = parse_result.get("invoice_info", {})
        date_str = inv_info.get("date", "")
        total_amt = inv_info.get("total_amount", 0)
        items = parse_result.get("items", [])
        
        # 如果 total_amount 為 0，嘗試從 items 計算
        if total_amt == 0 and items:
            total_amt = sum(it.get("subtotal", 0) for it in items if isinstance(it.get("subtotal"), (int, float)))
            
        # 產生品項精簡摘要
        if items:
            item_names = [it.get("name", "") for it in items if it.get("name")]
            items_summary = "、".join(item_names[:3])
            if len(item_names) > 3:
                items_summary += f" 等 {len(item_names)} 項"
        else:
            items_summary = "發票品項採購"
            
        inv_num = inv_info.get("invoice_number", "")
        default_memo = f"發票報銷({items_summary})" if items_summary else f"發票報銷({inv_num})"
        
        parse_result["bookkeeping_preview"] = {
            "can_auto_bookkeep": True,
            "amount": -abs(total_amt),
            "date": date_str,
            "default_memo": default_memo,
            "suggested_command": f"python3 /home/openclaw/irl_lab/openclaw_setup/irl_agent.py invoice bookkeep --memo \"{default_memo}\""
        }
        
    return parse_result


def bookkeep_invoice(image_path=None, memo_override=None):
    """
    辨識發票內容並直接調用 sheets_writer.append_transaction 自動寫入 Google Sheets 帳本
    """
    decode_res = decode_invoice(image_path)
    if not decode_res.get("success"):
        return {
            "success": False,
            "invoice_decode": decode_res,
            "message": f"發票辨識失敗，無法自動記帳：{decode_res.get('message')}"
        }
        
    inv_info = decode_res.get("invoice_info", {})
    total_amt = inv_info.get("total_amount", 0)
    items = decode_res.get("items", [])
    if total_amt == 0 and items:
        total_amt = sum(it.get("subtotal", 0) for it in items if isinstance(it.get("subtotal"), (int, float)))
        
    date_str = inv_info.get("date")
    bk_preview = decode_res.get("bookkeeping_preview", {})
    memo = memo_override or bk_preview.get("default_memo") or "發票自動記帳"
    
    # 調用 sheets_writer 記帳
    try:
        import sheets_writer
        budget_res = sheets_writer.append_transaction(
            amount=-abs(total_amt),
            memo=memo,
            date_str=date_str
        )
        return {
            "success": True,
            "invoice_decode": decode_res,
            "bookkeeping_result": budget_res,
            "message": f"已成功依發票辨識結果完成公用經費記帳（支出 NT$ {total_amt} 元，備註：{memo}）！"
        }
    except Exception as e:
        return {
            "success": False,
            "invoice_decode": decode_res,
            "message": f"發票辨識成功，但寫入帳本時發生錯誤：{str(e)}"
        }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    res = decode_invoice(target)
    print(json.dumps(res, ensure_ascii=False, indent=2))


