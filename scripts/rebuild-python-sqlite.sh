#!/usr/bin/env bash
# 修复 /usr/local 自编译 Python 3.12 缺少 _sqlite3 的问题（方案 B）
#
# 做的事：
#   1. 安装 libsqlite3-dev 及完整编译依赖
#   2. 下载与本机匹配的 CPython 3.12 源码
#   3. 重新 configure / make / install 到 /usr/local
#   4. 重建 backend/.venv 并安装依赖
#   5. 验证 import sqlite3
#
# 用法（在 WSL / Linux 中执行）:
#   ./scripts/rebuild-python-sqlite.sh
#   PY_VERSION=3.12.8 ./scripts/rebuild-python-sqlite.sh   # 指定小版本
#   PREFIX=/usr/local ./scripts/rebuild-python-sqlite.sh    # 安装前缀

set -euo pipefail

PREFIX="${PREFIX:-/usr/local}"
PY_BIN="${PY_BIN:-$PREFIX/bin/python3.12}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-/tmp/cpython-rebuild}"

info() { echo -e "\033[32m[rebuild]\033[0m $*"; }
warn() { echo -e "\033[33m[rebuild]\033[0m $*"; }
die()  { echo -e "\033[31m[rebuild]\033[0m $*" >&2; exit 1; }

# ---- 0. 解析目标版本 -------------------------------------------------------
if [[ -z "${PY_VERSION:-}" ]]; then
  if [[ -x "$PY_BIN" ]]; then
    PY_VERSION="$("$PY_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  else
    PY_VERSION="3.12.8"
  fi
fi
info "目标 CPython: $PY_VERSION → $PREFIX"

# ---- 1. 安装编译依赖（含 libsqlite3-dev） ------------------------------------
info "安装编译依赖…"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential \
  pkg-config \
  wget \
  ca-certificates \
  xz-utils \
  libsqlite3-dev \
  zlib1g-dev \
  libffi-dev \
  libssl-dev \
  libbz2-dev \
  libreadline-dev \
  libncursesw5-dev \
  libgdbm-dev \
  liblzma-dev \
  uuid-dev \
  tk-dev

# 确认开发头文件在
[[ -f /usr/include/sqlite3.h || -f /usr/include/x86_64-linux-gnu/sqlite3.h ]] \
  || die "仍未找到 sqlite3.h，请确认 libsqlite3-dev 安装成功"

# ---- 2. 下载源码 -----------------------------------------------------------
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
TARBALL="Python-${PY_VERSION}.tar.xz"
URL="https://www.python.org/ftp/python/${PY_VERSION}/${TARBALL}"

if [[ ! -d "Python-${PY_VERSION}" ]]; then
  info "下载 $URL"
  wget -q --show-progress -O "$TARBALL" "$URL" || die "下载失败，请检查网络或指定正确 PY_VERSION"
  tar -xf "$TARBALL"
fi
cd "Python-${PY_VERSION}"

# ---- 3. 编译安装 -----------------------------------------------------------
info "configure（务必能启用 _sqlite3）…"
# 清掉旧构建缓存
make distclean >/dev/null 2>&1 || true

./configure \
  --prefix="$PREFIX" \
  --enable-optimizations \
  --with-ensurepip=install \
  --enable-shared \
  LDFLAGS="-Wl,-rpath,$PREFIX/lib"

# 编译前自检：Makefile 里应包含 _sqlite3
if ! grep -q '_sqlite3' Makefile && ! grep -qi 'sqlite' Modules/Setup 2>/dev/null; then
  warn "Makefile 未明确列出 _sqlite3，继续编译，结束后以 import 验证为准"
fi

info "make -j$(nproc)…"
make -j"$(nproc)"

info "install 到 $PREFIX…"
sudo make altinstall

# 共享库路径
if [[ -d "$PREFIX/lib" ]]; then
  echo "$PREFIX/lib" | sudo tee /etc/ld.so.conf.d/python${PY_VERSION%.*}.conf >/dev/null
  sudo ldconfig
fi

NEW_PY="$PREFIX/bin/python3.12"
[[ -x "$NEW_PY" ]] || die "安装后未找到 $NEW_PY"

# ---- 4. 验证 sqlite3 -------------------------------------------------------
info "验证 import sqlite3…"
if ! "$NEW_PY" -c 'import sqlite3; print("sqlite3 ok:", sqlite3.sqlite_version)'; then
  die "仍然无法 import sqlite3。请把 configure 完整输出发出来以便排查。"
fi

# ---- 5. 重建项目 venv ------------------------------------------------------
info "重建 backend/.venv…"
cd "$ROOT"
rm -rf backend/.venv
"$NEW_PY" -m venv backend/.venv
backend/.venv/bin/python -m pip install -q -U pip
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt

info "项目内验证…"
(
  cd "$ROOT/backend"
  ./.venv/bin/python -c 'import sqlite3, flask, paramiko; print("backend deps ok")'
  ./.venv/bin/python -m pytest -q
)

cat <<EOF

\033[32m[rebuild] 完成\033[0m

  Python: $($NEW_PY -V)
  sqlite: $($NEW_PY -c 'import sqlite3; print(sqlite3.sqlite_version)')
  venv:   $ROOT/backend/.venv

下一步:
  ./dev.sh up

EOF
