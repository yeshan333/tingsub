#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
if ! command -v uv >/dev/null; then
  echo '请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/'
  exit 1
fi
uv sync --frozen --python 3.12
uv run --frozen tingsub prepare
echo '安装完成。双击 start.command 启动字幕服务。'
