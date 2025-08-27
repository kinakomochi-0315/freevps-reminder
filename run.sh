#!/usr/bin/env sh
# freevps-reminder 起動用のシンプルなランチャー
# - uv がインストールされているか確認
# - 仮想環境の作成／利用
# - 依存関係のインストール
# - Bot を起動
#
# 使い方:
#   ./run.sh
#
# 必要要件:
#   - POSIX シェル, curl（初回の uv インストール時に使用）
#   - Python（uv が仮想環境の作成を担当）

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

info() { printf "[INFO] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
err()  { printf "[ERROR] %s\n" "$*" >&2; }

# 1) uv が利用可能か確認
if command -v uv >/dev/null 2>&1; then
  UV_BIN=$(command -v uv)
  info "uv を検出しました: $UV_BIN"
else
  warn "uv が見つかりません。uv をインストールします..."
  if command -v curl >/dev/null 2>&1; then
    # 公式インストーラー: https://docs.astral.sh/uv/getting-started/installation/
    # デフォルトでは ~/.local/bin にインストールされます
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # インストールされた uv の場所を確認
    if [ -x "$HOME/.local/bin/uv" ]; then
      UV_BIN="$HOME/.local/bin/uv"
      info "uv をインストールしました: $UV_BIN"
    elif command -v uv >/dev/null 2>&1; then
      UV_BIN=$(command -v uv)
      info "uv をインストールしました: $UV_BIN"
    else
      err "uv のインストールは完了しましたが PATH で見つかりません。~/.local/bin を PATH に追加するかシェルを再起動してください。"
      err "例: export PATH=\"$HOME/.local/bin:$PATH\""
      exit 1
    fi
  else
    err "uv を自動インストールするには curl が必要です。curl をインストールするか、手動で uv をインストールしてください。"
    exit 1
  fi
fi

# 2) 依存関係の同期（仮想環境の作成含む）
info "uv で依存関係を同期しています..."
"${UV_BIN:-uv}" sync

# 3) アプリケーションを起動
# uv が管理する仮想環境を使用し、.env はコード側で読み込みます。
info "freevps-reminder を起動します..."
exec "${UV_BIN:-uv}" run python main.py
