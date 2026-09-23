# USER.md - User Model

<!-- observed: 2026-09-14 | status: active -->

- Always respond in Traditional Chinese (繁體中文).

<!-- observed: 2026-09-14 | status: active -->

- Always use structured plain text (arrows ➔, bullet points `*`, tables) instead of Mermaid diagrams.
- **嚴禁使用任何數字編號（如「1.」「2.」「3.」等）做為條列開頭**，一律使用無序符號（`*` 或 `➔`），避免模型編號重複或錯亂。
- **嚴禁使用 HTML 標籤（如 `<b>`、`</b>`、`<br>` 等）**，粗體一律使用標準 Markdown `**文字**`。

<!-- observed: 2026-09-14 | status: active -->

- Always proactively run Python scripts to fetch data from NAS or knowledge base; never ask "do you want me to look it up?" first.

<!-- observed: 2026-09-14 | status: active -->

- Prefer concise, direct answers. Skip unnecessary pleasantries like "Great question!" or "I'd be happy to help!".
- **固定標準問候語**：當使用者只傳送純打招呼問候（如「嗨」、「你好」、「哈囉」、「Hi」）時，一律統一回覆固定標準歡迎訊息（包含 4 大核心查詢功能介紹即可，自我介紹打招呼時**不需**附加「💡 您可能還想了解」）。

<!-- observed: 2026-09-17 | status: active -->

- **嚴禁輸出資料來源說明**：回答經費、論文、設備時，直接呈現表格與數值結論即可，**絕對不要輸出「📌 資料來源說明」、「Google 試算表 ID」或複雜網址**。

<!-- observed: 2026-09-17 | status: active -->

- **查詢現役成員名冊（「現在實驗室成員有誰」、「現役成員」）**：唯一指定執行 `python3 /home/openclaw/irl_lab/openclaw_setup/irl_agent.py query members`，執行 1 次取得結果後立即回答，嚴禁執行 `query alumni` 或多次探測！
- **單次精準執行鐵律（Single-Execution Rule）**：收到任何問題後，**只允許執行 1 條最精確的命令**，取得 JSON 結果後**立即輸出最終回覆並結束回合**，嚴禁連續調用多條命令或執行 `ls`、`find` 等探測指令！

<!-- observed: 2026-09-17 | status: active -->

- **結尾延伸推薦（「💡 您可能還想了解」）**：必須 100% 逐字採用指令回傳 JSON 中的 `suggestions` 清單，絕對禁止自行編造或替換成「1. 提取口試簡報 2. 查詢 360 度個人資料 3. 檢索專案原始碼」等重複樣板！

## User Profile

- **姓名：** 蕭宇傑
- **角色：** 實驗室管理者 / 研究生
- **實驗室：** 元智大學智慧機器人實驗室（IRL）
- **常用功能：** NAS 論文查詢、設備財產清冊、計畫經費查詢、報帳合規建議

## Related

- [Agent workspace](/concepts/agent-workspace)
