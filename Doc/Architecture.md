# 系統架構設計文件 (System Architecture Document)

## 1. 系統整體模組架構

```
[React 前端 / 對話互動介面]
      ↕ (REST API / WebSocket)
[IRL Lab AI 核心中央協調系統]
      ├── 🧾【會計報帳子系統】(accounting/)
      │     ├── Flask REST API (accounting_backend/)
      │     ├── 元智 Portal 報帳自動化 (ai_filldata.py)
      │     └── 發票單據 OCR 辨識 (camera_receipt.py)
      │
      └── 🧠【智慧詢問與檢索模組】(lab_assistant/)
            ├── 🧠【核心查詢與協調服務】(lab_assistant/core/)
            │     └── 知識庫問答與 360° 全景聯查服務 (query_service.py)
            │           ➔ 🎓 論文：支援論文檢索、摘要預覽、真實關鍵字詞頻統計與歷屆研究主題領域清冊（query_thesis_topics）
            │           ➔ 📅 請假與 📜 報帳：精準分流請假、會計核銷與 Portal 操作流程；長流程全面禁用表格，改採純文字垂直結構化輸出
            │           ➔ 🖥️ 設備與 👥 成員：支援 70640 全室盤點分類統計與個人名下保管設備對帳單（query_property_inventory）
            │           ➔ 💰 經費帳本：直連 MediaWiki 與 380 筆真實收支流水帳，支援歷年與指定年份年度/季度財務統計報表（query_funds_report）
            │           ➔ 🤖 360° 全景速查：一鍵整合現役/校友、論文、財產、經費與官網資料
            │
            ├── 🔌【外部系統與雲端串接模組】(lab_assistant/connectors/)
            │     ├── NAS 極速檢索與串流引擎 (nas_reader.py)
            │     │     ➔ 串接 Synology FileStation REST API (yzuirl.synology.me:5001)
            │     │     ➔ 全域檢索三大核心目錄：/畢業論文/、/工作區/、/工具與資料/
            │     │     ➔ 支援高精準中英文摘要正文萃取與 IDE 本地檢視器無痕提取
            │     │
            │     ├── MediaWiki 實驗室維基百科整合引擎 (wiki_reader.py)
            │     │     ➔ 串接 yzuirl.synology.me/mediawiki/
            │     │     ➔ 💰【公用經費清單】直接檢索 Wiki 頁面與線上 Google 試算表
            │     │     ➔ 支援章節精準擷取、Wikitext 清洗、daemon 背景執行緒自動同步
            │     │
            │     ├── IRL 實驗室官網即時檢索引擎 (official_site_reader.py)
            │     │     ➔ 串接 https://irl.ee.yzu.edu.tw/
            │     │     ➔ 涵蓋簡介、指導教授、成員、校友、產學實績、聯絡方式、招募等 7 大單元
            │     │     ➔ 支援 12 小時快取與線上即時爬取
            │     │
            │     ├── Google Calendar 實驗室行事曆連動引擎 (google_calendar_reader.py)
            │     │     ➔ 串接 Google Calendar REST API (Service Account)
            │     │     ➔ 📅【成員請假與出勤】即時查詢今日請假、近期名冊、特定日期與時段，支援 AI 自然語言登記寫入與取消刪除
            │     │
            │     ├── Google Sheets 雲端即時雙向記帳引擎 (sheets_writer.py)
            │     │     ➔ 串接 Google Sheets REST API (Service Account 授權憑證)
            │     │     ➔ ✏️【公用經費自動記帳】支援收支新增 (append_transaction)、末筆/關鍵字撤回刪除 (delete_transaction)
            │     │     ➔ 線上試算表與本地 lab_funds_ledger.json 即時雙向同步並重算結餘
            │     │
            │     └── 臺灣電子發票 QR Code 解碼與合規檢核暨自動記帳引擎 (invoice_reader.py)
            │           ➔ 串接 OpenCV (cv2.QRCodeDetector) 與財政部二維條碼標準格式
            │           ➔ 100% 精準提取品項明細、數量、單價、統編、金額與合規防呆審核
            │           ➔ 支援 invoice bookkeep 一鍵連動 sheets_writer 自動寫入 Google Sheets 雲端公用經費帳本
            │
            └── 📁【結構化資料庫與憑證】(lab_assistant/data/ & credentials/)
                  ├── 歷屆論文索引庫 (thesis_index.json)
                  ├── 歷屆校友名冊 (lab_alumni.json)
                  ├── 實驗室設備財產清冊 (lab_properties.json)
                  ├── 計畫經費預算帳本 (lab_funds_ledger.json)
                  ├── 會計報帳審核規則 (accounting_rules.json)
                  ├── MediaWiki 頁面快取 (wiki_knowledge.json)
                  └── Google API 服務帳戶憑證 (credentials/service_account.json)

```

---

## 2. 專案目錄結構劃分

```
IRL_Lab_AI_agent/
├── AGENTS.md                                # 常駐規則與開發指南
├── Doc/                                     # 架構與規格說明文件
│   ├── Architecture.md                      # 系統架構文件
│   ├── FRD.md                               # 功能需求規格書
│   └── ChangeLog.txt                        # 版本更新紀錄
├── accounting/                              # 🧾【報帳自動化子系統】
│   ├── 113年報帳/                            # 報帳單據樣本與歷年資料
│   ├── accounting_backend/                  # 報帳 Flask API & 自動填表
│   └── accounting_frontend/                 # 報帳 React 前端介面
└── lab_assistant/                           # 🧠【智慧詢問與檢索模組】
    ├── .env                                 # NAS 連線憑證與 Google Calendar ID
    ├── credentials/                         # Google Service Account 授權金鑰目錄
    │   └── service_account.json             # Google Cloud 服務帳號金鑰
    ├── nas_reader.py                        # NAS 即時檢索、同音字拼音模糊比對、PDF/Word/PPTX 串流解析
    ├── query_service.py                     # 校友、經費帳本、財產清冊、報銷法規、請假智慧問答
    ├── wiki_reader.py                       # MediaWiki 串接、章節精準定位與快取同步
    ├── official_site_reader.py              # 實驗室官方網站 (https://irl.ee.yzu.edu.tw/) 7 大單元即時爬取與快取
    ├── google_calendar_reader.py            # Google Calendar REST API 行事曆請假與出勤連動
    ├── requirements.txt                     # 獨立依賴套件清單

    ├── README.md                            # 模組調用說明
    ├── scripts/                             # 維護與資料建置腳本
    │   ├── convert_wp_to_md.py              # WordPress 黑曼巴 10 大章節轉 Markdown 工具
    │   ├── full_indexer.py                  # 歷屆碩士論文全域建庫索引工具
    │   ├── verify_folders.py                # NAS 目錄完整性驗證工具
    │   ├── check_index.py                   # 索引庫健康檢查工具
    │   └── benchmark_query_service.py       # 本地知識庫查詢效能基準測試工具
    ├── data/                                # 實驗室結構化 JSON 資料庫
    │   ├── thesis_index.json                # 歷屆碩士畢業論文全域智慧索引庫 (42篇)
    │   ├── lab_alumni.json                  # 歷屆校友與成員名冊 (41位)
    │   ├── lab_properties.json              # 實驗室設備財產清冊 (52件，內含使用中設備所有者名冊)
    │   ├── lab_funds_ledger.json            # 計畫經費預算帳本 (380筆)
    │   ├── accounting_rules.json            # 會計報帳審核規則庫 (5大類)
    └── thesis_viewer/                       # 本機 IDE 暫存檢視目錄（依提問即時下載，支援無痕自動生命週期管理）
```

---

## 3. 模組職責說明

### 3.1 報帳自動化子系統 (`accounting/`)
- 提供發票拍照與 OCR 辨識。
- 透過 Playwright 進行元智 Portal 會計系統自動登入與填表。
- 提供 Web 前端介面進行手動審核與確認。

### 3.2 實驗室智慧詢問模組 (`lab_assistant/`)
- **NAS 檢索與下載引擎 (`nas_reader.py`)**：直接調用 Synology FileStation REST WebAPI 進行毫秒級檔案檢索與下載，捨棄高耗時瀏覽器模擬，響應時間縮短至 1 秒內。
- **無痕即時串流讀取**：記憶體中（`io.BytesIO`）即時解析 PDF/Word/PPTX 論文與文件，零硬碟殘留。
- **IDE 檢視器整合**：支援多檔案共存暫存至 `lab_assistant/thesis_viewer/`，以及指定成員/專案全部文件之一鍵批量提取下載，兼顧無痕管理與完整檢視需求。
- **實驗室知識庫 (`query_service.py`)**：結構化管理校友、財產、經費與法規，支援快速精準檢索；新增 **360 度跨庫全景聯查**、**情境式報帳合規防呆試算顧問** 與 **主動式智慧延伸推薦 (Follow-up)**。
- **MediaWiki 實驗室維基百科整合 (`wiki_reader.py`)**：串接 `https://yzuirl.synology.me/mediawiki/`，提供請假、報帳期程、外籍/約用助理、境外電商統編與畢業離校規範之即時檢索與章節級精準定位。
- **資料庫自動同步機制**：隨時保持本地 7 大 JSON 資料庫與線上 Wiki / NAS 之 100% 資料一致性。
