# -*- coding: utf-8 -*-
"""
徹底清理 OpenClaw Agent 記憶庫與 Session 污染
"""
import sqlite3
import os
import subprocess

def main():
    print("正在停止 openclaw-gateway 服務...")
    subprocess.run(["systemctl", "--user", "stop", "openclaw-gateway.service"], check=False)

    db_path = "/home/openclaw/.openclaw/agents/main/agent/openclaw-agent.sqlite"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # 1. 找出所有含有 GPU 或感測器污染的 session_id
        cur.execute("SELECT DISTINCT session_id FROM transcript_events WHERE event_json LIKE '%GPU%' OR event_json LIKE '%感測器%' OR event_json LIKE '%LiDAR%' OR event_json LIKE '%主題研究清冊%'")
        bad_sessions = [r[0] for r in cur.fetchall()]
        print(f"發現受污染 Session 數量: {len(bad_sessions)}")

        # 2. 徹底刪除受污染 Session 的事件與節點
        for sid in bad_sessions:
            cur.execute("DELETE FROM transcript_events WHERE session_id = ?", (sid,))
            cur.execute("DELETE FROM session_transcript_active_events WHERE session_id = ?", (sid,))
            cur.execute("DELETE FROM session_nodes WHERE current_session_id = ?", (sid,))

        # 3. 清空記憶 Chunks 與 Embeddings（系統會根據最新 SOUL.md 自動重新索引）
        cur.execute("DELETE FROM memory_index_chunks")
        cur.execute("DELETE FROM memory_embedding_cache")

        conn.commit()
        conn.close()
        print(f"清理成果：已徹底清除受污染的 Session，並重設 Agent 記憶庫。")

    # 清理 memory dreaming 快取
    import glob
    dreaming_files = glob.glob("/home/openclaw/.openclaw/workspace/memory/dreaming/*")
    for f in dreaming_files:
        try:
            os.remove(f)
        except Exception:
            pass
    print(f"已清理 {len(dreaming_files)} 個 dreaming 臨時快取檔案。")

    print("重新啟動 openclaw-gateway 服務...")
    subprocess.run(["systemctl", "--user", "restart", "openclaw-gateway.service"], check=False)
    print("完成！已徹底清空污染快取並重啟。")

if __name__ == "__main__":
    main()
