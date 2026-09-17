# IRL Lab AI Assistant Guidelines

## 1. 語言與溝通
- 全面使用繁體中文。
- 所有流程、架構與步驟一律採用**純文字結構化排版（如箭頭 `➔`、層級條列、表格）**呈現，避免使用 Mermaid 程式碼區塊。
- **直接回答問題**，嚴禁在標題或內文中加上多餘的自我說明或格式備註括號（例如「（純文字結構化版）」、「（純文字版）」等）。

## 2. 實驗室智慧詢問模組規範 (`lab_assistant/`)
- 所有與實驗室成員、論文、NAS 檢索、經費、財產、法規相關之功能與資料庫均統整於 `lab_assistant/`：
  1. **NAS 全域檔案檢索與即時閱讀 (`lab_assistant/nas_reader.py`)**：
     - 自動讀取 `lab_assistant/.env` 內的 NAS 帳密（`NAS_USERNAME='蕭宇傑'`, `NAS_PASSWORD='Xiao921204@'`）連線至 `yzuirl.synology.me:5001`。
     - **支援 `/IRLshare/` 全域三大核心目錄及所有子資料夾**：
       - 🎓 **畢業論文**（`/IRLshare/畢業論文/`）：歷屆碩士畢業論文（PDF/Word）、投影片與同音字模糊比對。
       - 📑 **工作區**（`/IRLshare/工作區(報告、投影片等文件)/`）：產學計畫、中科院計畫、科技部成果發表、無人機、VRMIMO、物聯網閘道等專案報告與投影片。
       - 🛠️ **工具與資料**（`/IRLshare/工具與資料/`）：口試流程、報帳範本、開發文件 (IoT/MongoDB/Git)、Meeting 投影片、LOGO 與模板。
     - **嚴禁在使用者本機留存任何實體檔案或截圖（包含 `*.png`, `*.jpg`, 下載檔案等），所有檢索過程與讀取完全無痕，僅於對話框與 Artifact 呈現。**
     - 支援 `.pdf`、`.docx`、`.pptx`、`.txt`、圖片等即時串流文字解析。
     - **IDE 檢視器與自動生命週期管理**：使用者詢問論文或成員時，**直接主動提取該成員之「論文檔案（PDF/Word）」與「口試簡報（PPTX/投影片）」**至 `lab_assistant/thesis_viewer/`，並於回答中直接提供可點擊之本機檔案連結，於次輪提問時自動清除暫存維護無痕原則。
  2. **實驗室知識庫分工與檢索規範**：
     - 🎓 **畢業論文與歷屆索引**：維持使用結構化 JSON (`thesis_index.json`) 與 NAS (`nas_reader.py`) 即時無痕串流解析。
     - 🖥️ **財產與設備清冊**：維持使用結構化 JSON (`lab_properties.json`) 進行即時精準檢索。
     - 💰 **經費與公用經費查詢**：**全面改為直接連線 MediaWiki 知識庫 (`wiki_reader.py`) 檢索**（優先取得「公用經費清單」頁面與 Google 試算表 `1un-VyqNpeIMiQvHZSW51Koo7_WZI-XwQdxs_mTc7O2w/#gid=9`，並整合線上報帳與經費規章，本地帳本作為結構化補充明細）。
     - 👥 **360 度人物/專案全景速查 (`query_person_360`)**：一鍵聯查成員之學歷年份 (JSON)、畢業論文題目與簡報 (JSON/NAS)、保管設備清冊 (JSON) 與 Wiki 經費收支來源。
     - ⚖️ **情境式報帳合規防呆試算顧問 (`evaluate_expense_compliance`)**：支援採購金額門檻（1萬以上財產列管/1家估價單、10萬以上比價）、便當餐費上限（100~120元）、元智大學統編（`00966880`）與境外電商（OpenAI, Grok, GitHub 等）5% 營業稅加計與必備單據檢核。
     - 💡 **主動式智慧延伸推薦 (Follow-up Suggestions)**：每次回答結尾主動提供 3 個精準相關的「💡 您可能還想了解」延伸推薦項目供使用者快速探索。
  3. **MediaWiki 實驗室維基百科整合 (`lab_assistant/wiki_reader.py`)**：
     - 自動串接 `https://yzuirl.synology.me/mediawiki/`。
     - 支援實驗室公用經費、請假規則、報帳期程與細則、各類國外勞務身分統編（OpenAI、Grok、Google、GitHub 等）、助理約用、畢業離校規範及 BlackMamba 系統之即時與快取查詢。
     - **Wiki 資料來源防呆對應**：Wiki 上的「設備清單」頁面誤植為校友試算表；**真正的「設備清單」與「公用經費」皆收錄於 Wiki 的「公用經費清單」頁面（Google 試算表 `1un-VyqNpeIMiQvHZSW51Koo7_WZI-XwQdxs_mTc7O2w`）**。
  4. **IRL 實驗室官方網站即時檢索 (`lab_assistant/official_site_reader.py`)**：
     - 自動串接 `https://irl.ee.yzu.edu.tw/`。
     - 涵蓋 7 大核心單元：`Introduction 實驗室簡介`、`Advisor 指導教授`、`Member 成員`、`Alumni 校友`、`Cooperation 產學合作與實績`、`Contact Us 聯絡方式`、`Recruits 誠徵新成員`。
     - 支援 12 小時自動快取與即時線上爬取，無需仰賴本地靜態檔案，隨問隨抓。
  5. **MediaWiki 與結構化 JSON 資料庫自動同步機制**：
     - 若 MediaWiki 頁面（或其對應之公用經費/設備/校友試算表）內容有任何異動，系統應自動同步並更新 `lab_assistant/data/` 內對應之 JSON 檔案（`wiki_knowledge.json`、`accounting_rules.json`、`lab_properties.json`、`lab_funds_ledger.json` 等），隨時維持本地資料庫與線上 Wiki 100% 一致性。

## 3. 專案開發規範
- 後端：Python (Flask / Playwright)。
- 前端：React。
- 專案架構劃分：
  - `accounting/`：專責報帳自動化與 Portal 填表。
  - `lab_assistant/`：專責實驗室智慧詢問、官網、NAS 與 Wiki 知識庫檢索。
- 修改後同步更新 `Doc/` 相關文件（ChangeLog.txt, FRD.md, Architecture.md）。

