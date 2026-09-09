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
            ├── NAS 極速檢索與串流引擎 (nas_reader.py)
            │     ➔ 串接 Synology FileStation REST API (yzuirl.synology.me:5001)
            │     ➔ 全域檢索三大核心目錄：/畢業論文/、/工作區/、/工具與資料/
            │
            ├── 知識庫問答與 360° 全景聯查服務 (query_service.py)
            │     ➔ 支援多詞複合檢索、合規試算防呆與延伸推薦
            │
            ├── MediaWiki 實驗室維基百科整合引擎 (wiki_reader.py)
            │     ➔ 串接 yzuirl.synology.me/mediawiki/
            │     ➔ 支援章節精準擷取、Wikitext 清洗與資料庫自動同步
            │
            └── 結構化資料庫 (lab_assistant/data/)
                  ├── 歷屆論文索引庫 (thesis_index.json)
                  ├── 歷屆校友名冊 (lab_alumni.json)
                  ├── 實驗室設備財產清冊 (lab_properties.json)
                  ├── 計畫經費預算帳本 (lab_funds_ledger.json)
                  ├── 會計報帳審核規則 (accounting_rules.json)
                  └── MediaWiki 頁面快取 (wiki_knowledge.json)
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
    ├── .env                                 # NAS 連線憑證
    ├── nas_reader.py                        # NAS 即時檢索、同音字拼音模糊比對、PDF/Word/PPTX 串流解析
    ├── query_service.py                     # 校友、經費帳本、財產清冊、報銷法規智慧問答
    ├── wiki_reader.py                       # MediaWiki 串接、章節精準定位與快取同步
    ├── requirements.txt                     # 獨立依賴套件清單
    ├── README.md                            # 模組調用說明
    ├── scripts/                             # 維護與資料建置腳本
    │   ├── convert_wp_to_md.py              # WordPress 黑曼巴 10 大章節轉 Markdown 工具
    │   ├── full_indexer.py                  # 歷屆碩士論文全域建庫索引工具
    │   ├── verify_folders.py                # NAS 目錄完整性驗證工具
    │   └── check_index.py                   # 索引庫健康檢查工具
    ├── data/                                # 實驗室結構化 JSON 資料庫
    │   ├── thesis_index.json                # 歷屆碩士畢業論文全域智慧索引庫 (42篇)
    │   ├── lab_alumni.json                  # 歷屆校友與成員名冊 (41位)
    │   ├── lab_properties.json              # 實驗室設備財產清冊 (52件)
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
