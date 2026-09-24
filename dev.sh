#!/usr/bin/env bash
# 根目录快捷入口，等价于 ./scripts/dev.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/dev.sh" "$@"
