#!/usr/bin/env bash
# LogPort 本地开发 / 部署快捷脚本
#
# 用法:
#   ./scripts/dev.sh setup      一次性准备 venv、依赖、.env
#   ./scripts/dev.sh up         启动后端 + Worker + 前端（开发模式）
#   ./scripts/dev.sh down       停止 up 启动的进程
#   ./scripts/dev.sh backend    前台只跑后端
#   ./scripts/dev.sh worker     前台只跑 Worker
#   ./scripts/dev.sh frontend   前台只跑前端
#   ./scripts/dev.sh test       运行后端测试
#   ./scripts/dev.sh build      构建前端生产包 (frontend/dist)
#   ./scripts/dev.sh deploy     Docker Compose 一键部署
#   ./scripts/dev.sh status     查看开发进程
#   ./scripts/dev.sh logs       跟踪开发日志
#   ./scripts/dev.sh help       显示帮助

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV="$BACKEND_DIR/.venv"
PY="$VENV/bin/python"
ENV_FILE="$ROOT/.env"
DATA_DIR="${DATA_DIR:-$ROOT/.data}"
RUN_DIR="$ROOT/.dev-run"
LOG_DIR="$DATA_DIR/logs"

GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
DIM=$'\033[2m'
RESET=$'\033[0m'

info()  { echo "${GREEN}[logport]${RESET} $*"; }
warn()  { echo "${YELLOW}[logport]${RESET} $*"; }
error() { echo "${RED}[logport]${RESET} $*" >&2; }
die()   { error "$*"; exit 1; }

usage() {
  sed -n '2,15p' "$0" | sed 's/^# \?//'
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
  DATA_DIR="${DATA_DIR:-$ROOT/.data}"
  FRONTEND_DIST="${FRONTEND_DIST:-$FRONTEND_DIR/dist}"
  export DATA_DIR FRONTEND_DIST
}

write_default_env() {
  local secret
  secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > "$ENV_FILE" <<EOF
ADMIN_USERNAME=admin
ADMIN_PASSWORD=dev-admin-please-change
SECRET_KEY=$secret
CREDENTIAL_KEY=
COOKIE_SECURE=false
DATA_DIR=$DATA_DIR
FRONTEND_DIST=$FRONTEND_DIR/dist
EOF
  warn "已生成 $ENV_FILE"
  warn "开发默认密码: dev-admin-please-change（请勿用于生产）"
}

ensure_credential_key() {
  load_env
  if [[ -z "${CREDENTIAL_KEY:-}" ]]; then
    [[ -x "$PY" ]] || die "请先安装后端依赖（./scripts/dev.sh setup）"
    local key
    key="$("$PY" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
    if grep -q '^CREDENTIAL_KEY=' "$ENV_FILE" 2>/dev/null; then
      sed -i.bak "s|^CREDENTIAL_KEY=.*|CREDENTIAL_KEY=$key|" "$ENV_FILE"
      rm -f "$ENV_FILE.bak"
    else
      echo "CREDENTIAL_KEY=$key" >> "$ENV_FILE"
    fi
    export CREDENTIAL_KEY="$key"
    info "已生成 CREDENTIAL_KEY"
  fi
}

prepare_dirs() {
  mkdir -p "$DATA_DIR/exports" "$LOG_DIR" "$RUN_DIR"
}

check_sqlite() {
  local bin="${1:-python3}"
  if ! "$bin" -c 'import sqlite3' 2>/dev/null; then
    error "当前 Python 缺少 _sqlite3 模块（import sqlite3 失败）"
    error "  → 编译时未启用 sqlite，可执行: ./scripts/rebuild-python-sqlite.sh"
    error "  → 或改用系统 Python: sudo apt-get install -y python3 python3-venv libsqlite3-dev"
    die "请先修复 Python 的 sqlite3 支持"
  fi
}

setup() {
  need_cmd python3
  need_cmd npm
  check_sqlite python3

  info "准备 Python 虚拟环境…"
  if [[ ! -x "$PY" ]]; then
    python3 -m venv "$VENV"
  fi
  "$PY" -m pip install -q -U pip
  "$PY" -m pip install -q -r "$BACKEND_DIR/requirements.txt"

  if [[ ! -f "$ENV_FILE" ]]; then
    write_default_env
  fi
  ensure_credential_key

  info "准备前端依赖…"
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    (cd "$FRONTEND_DIR" && npm install)
  else
    (cd "$FRONTEND_DIR" && npm install --silent)
  fi

  prepare_dirs
  info "setup 完成"
  info "启动开发环境: ./scripts/dev.sh up"
}

spawn() {
  local name="$1"; shift
  local workdir="$1"; shift
  if is_running "$name"; then
    warn "$name 已在运行 (pid $(cat "$RUN_DIR/$name.pid"))"
    return 0
  fi
  info "启动 $name → ${LOG_DIR}/${name}.log"
  (
    cd "$workdir"
    exec "$@"
  ) >>"${LOG_DIR}/${name}.log" 2>&1 &
  echo $! > "$RUN_DIR/$name.pid"
}

is_running() {
  local pid_file="$RUN_DIR/$1.pid"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

kill_tree() {
  local pid="$1"
  local sig="${2:-TERM}"
  local child
  while read -r child; do
    [[ -n "$child" ]] && kill_tree "$child" "$sig"
  done < <(pgrep -P "$pid" 2>/dev/null || true)
  kill -s "$sig" "$pid" 2>/dev/null || true
}

stop_one() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"
  [[ -f "$pid_file" ]] || return 0
  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    info "停止 $name (pid $pid)"
    kill_tree "$pid" TERM
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill_tree "$pid" KILL
    fi
  fi
  rm -f "$pid_file"
}

cmd_up() {
  [[ -x "$PY" ]] || die "请先执行 ./scripts/dev.sh setup"
  [[ -d "$FRONTEND_DIR/node_modules" ]] || die "请先执行 ./scripts/dev.sh setup"
  ensure_credential_key
  prepare_dirs

  spawn backend "$BACKEND_DIR" "$PY" log_server.py
  spawn worker "$BACKEND_DIR" "$PY" -m log_exporter.worker
  spawn frontend "$FRONTEND_DIR" npm run dev

  sleep 1
  echo
  info "开发环境已启动"
  echo "  前端  ${GREEN}http://127.0.0.1:5173${RESET}  （日常开发用这个）"
  echo "  后端  ${GREEN}http://127.0.0.1:9090${RESET}  （API / 构建后的 SPA）"
  echo "  日志  $LOG_DIR/{backend,worker,frontend}.log"
  echo "  停止  ${DIM}./scripts/dev.sh down${RESET}"
  echo
  warn "开发账号: admin / dev-admin-please-change（见 .env）"
}

cmd_down() {
  stop_one frontend
  stop_one worker
  stop_one backend
  info "已停止开发进程"
}

cmd_status() {
  for name in backend worker frontend; do
    if is_running "$name"; then
      echo "  ${GREEN}●${RESET} $name  pid $(cat "$RUN_DIR/$name.pid")"
    else
      echo "  ${DIM}○${RESET} $name  未运行"
    fi
  done
}

cmd_logs() {
  prepare_dirs
  info "跟踪日志（Ctrl+C 退出）"
  tail -n 80 -f "$LOG_DIR"/backend.log "$LOG_DIR"/worker.log "$LOG_DIR"/frontend.log 2>/dev/null || true
}

cmd_backend() {
  [[ -x "$PY" ]] || die "请先执行 ./scripts/dev.sh setup"
  ensure_credential_key
  prepare_dirs
  cd "$BACKEND_DIR"
  exec "$PY" log_server.py
}

cmd_worker() {
  [[ -x "$PY" ]] || die "请先执行 ./scripts/dev.sh setup"
  ensure_credential_key
  prepare_dirs
  cd "$BACKEND_DIR"
  exec "$PY" -m log_exporter.worker
}

cmd_frontend() {
  [[ -d "$FRONTEND_DIR/node_modules" ]] || die "请先执行 ./scripts/dev.sh setup"
  cd "$FRONTEND_DIR"
  exec npm run dev
}

cmd_test() {
  [[ -x "$PY" ]] || die "请先执行 ./scripts/dev.sh setup"
  (cd "$BACKEND_DIR" && "$PY" -m pytest -q "$@")
}

cmd_build() {
  [[ -d "$FRONTEND_DIR/node_modules" ]] || die "请先执行 ./scripts/dev.sh setup"
  npm --prefix "$FRONTEND_DIR" run build
  info "前端已输出到 frontend/dist"
}

cmd_deploy() {
  need_cmd docker
  if docker compose version >/dev/null 2>&1; then
    (cd "$ROOT" && docker compose up -d --build)
  else
    (cd "$ROOT" && docker-compose up -d --build)
  fi
  info "Compose 已启动"
  info "健康检查: curl -s http://127.0.0.1:9090/api/health"
  info "查看容器: docker compose ps"
}

main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    setup)          setup "$@" ;;
    up)             cmd_up "$@" ;;
    down|stop)      cmd_down "$@" ;;
    backend)        cmd_backend "$@" ;;
    worker)         cmd_worker "$@" ;;
    frontend|web)   cmd_frontend "$@" ;;
    test)           cmd_test "$@" ;;
    build)          cmd_build "$@" ;;
    deploy|prod)    cmd_deploy "$@" ;;
    status|ps)      cmd_status "$@" ;;
    logs|log)       cmd_logs "$@" ;;
    help|-h|--help) usage ;;
    *) usage; die "未知命令: $cmd" ;;
  esac
}

main "$@"
