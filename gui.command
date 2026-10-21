#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
exec uv run --frozen tingsub gui
