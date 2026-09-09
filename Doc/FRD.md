# 系統功能需求規格書 (Functional Requirements Document - FRD)

## 1. 專案概觀
- **專案名稱**：IRL 實驗室智慧助理與報帳系統 (IRL Lab AI Agent & Accounting Platform)
- **目標使用者**：元智大學 IRL 實驗室成員、教授與研究團隊。
- **主要目的**：整合學校 Portal 會計報帳自動化、AI 發票辨識、計畫預算監控與實驗室 NAS 論文知識庫智慧問答。

---

## 2. 核心模組劃分

### 2.1 報帳自動化模組 (`accounting/`)
- **發票拍照與辨識**：支援相機拍照與圖片上傳發票辨識 (Ollama VLM / OpenCV / QR Code)。
- **Portal 自動填單**：Playwright 機器人自動登入元智 Portal 填報支出並擷取報銷單號。
- **全域單據追蹤大廳**：支援 Kanban 看板與條列清單切換，追蹤實體憑證審核與撥款進度。

### 2.2 實驗室智慧詢問模組 (`lab_assistant/`)
- **NAS 智慧檔案與論文檢索 (`nas_reader.py`)**：
  - 直接調用 Synology FileStation REST WebAPI (`yzuirl.synology.me:5001`) 進行毫秒級檔案檢索與下載，內建 HTTP 指數退避自動重試（Retry 3次）防網路抖動與逾時。
  - 支援 `/IRLshare/` 全域目錄智慧搜尋與同音字/拼音/模糊比對。
  - 支援 `.pdf`、`.docx`、`.pptx`、圖片等記憶體（`io.BytesIO`）即時無痕串流讀取，文字檔下載自動偵測 Big5 轉為標準 UTF-8。
  - IDE 檢視器整合（`lab_assistant/thesis_viewer/`）與生命週期管理：支援多檔案共存檢視，以及指定成員/專案全部重要檔案（論文、簡報、原始碼）之一鍵批量提取下載。

- **結構化知識庫問答服務 (`query_service.py`)**：
  - **多關鍵字複合分詞檢索 (Multi-keyword Token Search)**：校友、論文、財產、帳本、法規全面支援空格分詞 (AND) 複合查詢。
  - **歷屆論文索引庫** (`thesis_index.json`)：收錄歷屆論文題目、英文題目、關鍵字與作者，支援題目錯別字/同音字與主題關鍵字之毫秒級極速秒查。
  - **歷屆校友資料庫** (`lab_alumni.json`)：姓名、系所、專長領域與畢業年份查詢。
  - **設備財產清冊** (`lab_properties.json`)：財產編號、物品名稱、保管人與存放位置。
  - **計畫經費帳本** (`lab_funds_ledger.json`)：各計畫經費編號、預算分配與餘額追蹤。
  - **會計報銷法規** (`accounting_rules.json`)：元智大學各類費用報銷標準與規定檢索。
  - **360 度人物/專案全景速查 (`query_person_360`)**：一鍵聯查成員之學歷年份、畢業論文題目與簡報、保管設備清冊與經費收支紀錄。
  - **情境式報帳合規防呆試算顧問 (`evaluate_expense_compliance`)**：支援採購金額門檻（1萬以上財產列管/1家估價單、10萬以上比價）、便當餐費上限（100~120元）、元智大學統編（`00966880`）與境外電商（OpenAI, Grok, GitHub 等）5% 營業稅加計與必備單據檢核。
  - **主動式智慧延伸推薦 (Follow-up Suggestions)**：動態產生推薦探索問題，提升人機對話效率與引導深度。
- **MediaWiki 實驗室維基知識庫 (`wiki_reader.py`)**：
  - 串接 `https://yzuirl.synology.me/mediawiki/` API 進行即時維基頁面檢索與全文搜尋，內建自動重試適配器。
  - **章節級精準擷取與 Wikitext 清洗**：自動切分 Wiki 章節樹，支援單一子章節精準擷取並濾除粗體、內部連結與 HTML 雜訊。
  - 支援實驗室請假出勤規定、報帳完整期程/雜項/採購/零用金/國外差旅細則、境外電商統編（OpenAI、Grok、Google、GitHub 等）、研究助理約用標準、畢業交接流程與 BlackMamba 回訊系統說明。
  - **Wiki 來源防呆與資料庫自動同步**：明確對應設備與公用經費至「公用經費清單」試算表，並支援線上 Wiki / 試算表異動時自動同步更新本地 7 大結構化 JSON 資料庫。
