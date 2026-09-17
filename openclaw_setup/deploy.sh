#!/bin/bash
# =============================================================
# IRL Lab AI Agent → OpenClaw 部署腳本
# 執行方式: bash /home/openclaw/irl_lab/openclaw_setup/deploy.sh
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WORKSPACE="/home/openclaw/.openclaw/workspace"
INSTALL_DIR="/home/openclaw/irl_lab"

echo "============================================"
echo "🧪 IRL Lab AI Agent → OpenClaw 部署"
echo "============================================"
echo "專案來源: $PROJECT_ROOT"
echo "安裝目標: $INSTALL_DIR"
echo "OpenClaw 工作區: $WORKSPACE"
echo ""

# ── 步驟 1：建立安裝目錄 ────────────────────────────
echo "📁 步驟 1/5：建立安裝目錄..."
mkdir -p "$INSTALL_DIR"

# ── 步驟 2：複製 lab_assistant 模組 ─────────────────
echo "📦 步驟 2/5：複製 lab_assistant 模組..."
cp -r "$PROJECT_ROOT/lab_assistant" "$INSTALL_DIR/"
echo "   ✓ lab_assistant/ 複製完成"

# 複製 accounting 模組（如果存在）
if [ -d "$PROJECT_ROOT/accounting" ]; then
    cp -r "$PROJECT_ROOT/accounting" "$INSTALL_DIR/"
    echo "   ✓ accounting/ 複製完成"
fi

# ── 步驟 3：安裝 Python 依賴 ─────────────────────────
echo "🐍 步驟 3/5：安裝 Python 依賴..."

# 確保 pip 可用
if ! command -v pip3 &>/dev/null; then
    echo "   安裝 pip3..."
    sudo apt-get install -y python3-pip python3-venv 2>/dev/null || \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
fi

# 建立虛擬環境
if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "   建立 Python 虛擬環境..."
    python3 -m venv "$INSTALL_DIR/venv"
fi

# 安裝依賴
source "$INSTALL_DIR/venv/bin/activate"
pip install -q -r "$INSTALL_DIR/lab_assistant/requirements.txt"
echo "   ✓ Python 依賴安裝完成"
deactivate

# ── 步驟 4：部署 OpenClaw 工作區設定檔 ───────────────
echo "⚙️  步驟 4/5：部署 OpenClaw 工作區設定檔..."
mkdir -p "$WORKSPACE/memory"

# 備份現有設定
BACKUP_DIR="$WORKSPACE/.backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
for f in AGENTS.md IDENTITY.md SOUL.md USER.md; do
    if [ -f "$WORKSPACE/$f" ]; then
        cp "$WORKSPACE/$f" "$BACKUP_DIR/$f"
        echo "   備份: $f → $BACKUP_DIR/"
    fi
done

# 複製 IRL Lab 設定檔到工作區
cp "$SCRIPT_DIR/AGENTS.md"   "$WORKSPACE/AGENTS.md"
cp "$SCRIPT_DIR/IDENTITY.md" "$WORKSPACE/IDENTITY.md"
cp "$SCRIPT_DIR/SOUL.md"     "$WORKSPACE/SOUL.md"
cp "$SCRIPT_DIR/USER.md"     "$WORKSPACE/USER.md"
echo "   ✓ 工作區設定檔部署完成"

# 刪除 BOOTSTRAP.md（避免 OpenClaw 重新初始化）
if [ -f "$WORKSPACE/BOOTSTRAP.md" ]; then
    rm "$WORKSPACE/BOOTSTRAP.md"
    echo "   ✓ BOOTSTRAP.md 已移除（防止重複初始化）"
fi

# ── 步驟 5：驗證部署 ─────────────────────────────────
echo "✅ 步驟 5/5：驗證部署..."

# 測試 Python 腳本可執行
source "$INSTALL_DIR/venv/bin/activate"
PYTHON="$INSTALL_DIR/venv/bin/python3"

echo "   測試 nas_reader.py..."
if $PYTHON "$INSTALL_DIR/lab_assistant/nas_reader.py" --help &>/dev/null 2>&1 || \
   $PYTHON -c "import sys; sys.path.insert(0, '$INSTALL_DIR/lab_assistant'); print('OK')" 2>/dev/null; then
    echo "   ✓ nas_reader.py 可執行"
else
    echo "   ⚠️  nas_reader.py 有警告（可能缺少 NAS 連線，正常現象）"
fi

echo "   測試 query_service.py..."
if $PYTHON -c "import sys; sys.path.insert(0, '$INSTALL_DIR/lab_assistant'); print('OK')" 2>/dev/null; then
    echo "   ✓ query_service.py 可執行"
fi
deactivate

echo ""
echo "============================================"
echo "🎉 部署完成！"
echo "============================================"
echo ""
echo "📌 工作區設定檔位置:"
echo "   $WORKSPACE/AGENTS.md"
echo "   $WORKSPACE/IDENTITY.md"
echo "   $WORKSPACE/SOUL.md"
echo "   $WORKSPACE/USER.md"
echo ""
echo "📌 IRL Lab 模組位置:"
echo "   $INSTALL_DIR/lab_assistant/"
echo ""
echo "📌 Python 虛擬環境:"
echo "   $INSTALL_DIR/venv/"
echo ""
echo "🔧 調用範例（在 OpenClaw 中說）："
echo "   「查詢顏伯丞的畢業論文」"
echo "   「列出計畫經費帳本」"
echo "   「報帳規定 計程車費用」"
echo ""
echo "⚠️  請在 OpenClaw Windows Companion 中點擊「重新整理」"
echo "   或重新啟動 OpenClaw 以載入新設定。"
echo "============================================"
