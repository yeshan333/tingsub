#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
echo '把下面的配对码填入 Chrome 插件的「本机配对」：'
uv run --frozen tingsub pair
exec uv run --frozen tingsub serve
