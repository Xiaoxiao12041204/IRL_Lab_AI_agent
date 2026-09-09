# 🧠 IRL Lab AI Assistant - 智慧詢問與檢索模組

本模組專門負責實驗室各種資訊的智慧檢索、同音字模糊辨識、NAS 論文與文件即時讀取，以及結構化知識庫問答。

---

## 📂 目錄結構

```
lab_assistant/
├── .env                  # NAS 帳號與密碼配置
├── nas_reader.py         # Synology NAS 檔案檢索與無痕串流讀取模組
├── query_service.py      # 校友名冊、經費帳本、財產清冊、會計法規問答服務
├── requirements.txt      # Python 依賴清單
└── data/                 # 實驗室知識庫資料庫
    ├── lab_alumni.json       # 歷屆校友與成員名冊
    ├── lab_properties.json   # 實驗室設備與財產清冊
    ├── lab_funds_ledger.json # 產學與科技部計畫經費帳本
    └── accounting_rules.json # 會計報帳審核法規庫
```

---

## 🚀 核心功能與調用方式

### 1. NAS 畢業論文與檔案檢索 (`nas_reader.py`)

```bash
# 智慧搜尋與同音字/錯別字比對
python nas_reader.py match "堂家風"

# 列出指定路徑下的檔案
python nas_reader.py list "/IRLshare/畢業論文/顏伯丞/"

# 即時串流讀取論文文字內容（支援 PDF / Word）
python nas_reader.py read "/IRLshare/畢業論文/林詠軒/" "論文"

# 載入檔案至 IDE 檢視器（支援 PDF / Word / PPTX / 圖片）
python nas_reader.py open "/IRLshare/畢業論文/唐嘉鋒/" "論文電子檔_唐嘉鋒_最終版.docx"
```

### 2. 實驗室知識庫問答服務 (`query_service.py`)

```bash
# 查詢校友資訊
python query_service.py alumni "顏伯丞"

# 查詢實驗室財產與設備保管人
python query_service.py property "伺服器"

# 查詢計畫經費帳本與餘額
python query_service.py budget "高階"

# 查詢會計報銷法規
python query_service.py rules "計程車"
```
