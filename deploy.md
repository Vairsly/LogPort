# LogPort 部署文档

适用于单机 Docker / Docker Compose 部署。默认只绑定回环地址，生产环境请用 Nginx 或 Caddy 做 HTTPS 反向代理。

## 1. 环境要求

- Linux/amd64
- Docker 20+ 与 Docker Compose v2（或单独 `docker run`）
- 目标服务器可被 Worker 通过 SSH 访问，并允许执行 `docker version`、`docker logs`

## 2. 配置

```bash
cp .env.example .env
```

| 变量 | 说明 |
|---|---|
| `ADMIN_USERNAME` | 初始管理员用户名（默认 `admin`） |
| `ADMIN_PASSWORD` | 初始密码，**务必改为强随机**；仅首次启动创建账号时生效 |
| `SECRET_KEY` | Flask 会话密钥，长随机串 |
| `CREDENTIAL_KEY` | Fernet 密钥，用于加密 SSH 凭据；**部署后不可随意更换** |
| `COOKIE_SECURE` | HTTPS 部署设为 `true` |
| `DATA_DIR` | 容器内数据目录，默认 `/data` |
| `FRONTEND_DIST` | 可选，前端静态目录，默认 `frontend/dist` |

生成密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

备份时必须同时保存数据卷与 `CREDENTIAL_KEY`，两者缺一不可。

## 3. Docker Compose（推荐）

```bash
docker compose up -d --build
curl -s http://127.0.0.1:9090/api/health
```

浏览器访问 `http://127.0.0.1:9090`。

Compose 启动两个服务并共享 `log-data` 卷：

| 服务 | 命令 | 说明 |
|---|---|---|
| `web` | gunicorn | 提供 API 与 Vue 静态资源 |
| `worker` | `python -m log_exporter.worker` | SSH 导出与清理 |

## 4. 单容器（Web + Worker）

```bash
docker build -t log-server:latest .
sudo mkdir -p /opt/logport-data/exports
sudo chown -R 10001:10001 /opt/logport-data

docker run -d \
  --name log-server \
  --restart unless-stopped \
  --env-file .env \
  -p 127.0.0.1:9090:9090 \
  -v /opt/logport-data:/data \
  --health-cmd='python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:9090/api/health\")"' \
  --health-interval=30s \
  --health-timeout=5s \
  --health-retries=3 \
  log-server:latest \
  python -m log_exporter.run_all
```

任一进程退出都会让容器退出，由 `--restart unless-stopped` 拉起。

## 5. 双容器隔离

```bash
docker run -d --name log-server-web \
  --restart unless-stopped --env-file .env \
  -p 127.0.0.1:9090:9090 \
  -v /opt/logport-data:/data \
  --health-cmd='python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:9090/api/health\")"' \
  --health-interval=30s --health-timeout=5s --health-retries=3 \
  log-server:latest

docker run -d --name log-server-worker \
  --restart unless-stopped --env-file .env \
  -v /opt/logport-data:/data \
  log-server:latest \
  python -m log_exporter.worker
```

## 6. 离线部署

构建机：

```bash
docker build -t log-server:latest .
docker save -o log-server-latest.tar log-server:latest
sha256sum log-server-latest.tar > log-server-latest.tar.sha256
```

将镜像包、校验文件与单独配置好的 `.env`（勿走公开渠道）拷到目标机：

```bash
sha256sum -c log-server-latest.tar.sha256
docker load -i log-server-latest.tar
sudo mkdir -p /opt/logport-data/exports
sudo chown -R 10001:10001 /opt/logport-data
docker run -d --name log-server --restart unless-stopped \
  --env-file .env -p 127.0.0.1:9090:9090 \
  -v /opt/logport-data:/data \
  log-server:latest python -m log_exporter.run_all
```

## 7. HTTPS 反向代理（Nginx 示例）

```nginx
server {
  listen 443 ssl;
  server_name logport.example.internal;
  ssl_certificate     /etc/ssl/certs/logport.pem;
  ssl_certificate_key /etc/ssl/private/logport.key;

  client_max_body_size 2m;

  location / {
    proxy_pass http://127.0.0.1:9090;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
  }
}
```

`.env` 中设置 `COOKIE_SECURE=true`。

## 8. 本地开发

推荐使用脚本（一条命令搞定依赖与三进程）：

```bash
./dev.sh setup
./dev.sh up
# 浏览器打开 http://127.0.0.1:5173
./dev.sh down
```

脚本会自动：创建 `backend/.venv`、安装 Python/前端依赖、生成开发用 `.env`（含 `CREDENTIAL_KEY`）、准备 `.data/` 目录，并后台启动后端、Worker、前端。

手动等价步骤：

```bash
# 后端
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATA_DIR=../.data
export ADMIN_PASSWORD=dev-admin-please-change
export SECRET_KEY=development-secret
export CREDENTIAL_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
python log_server.py

# Worker（另一终端，backend 目录）
python -m log_exporter.worker

# 前端（另一终端）
cd frontend
npm install
npm run dev
```

测试与构建：

```bash
./dev.sh test    # 或 cd backend && pytest -q
./dev.sh build   # 产出 frontend/dist
```

## 9. 运维注意

- SQLite 仅适合单机；不要把数据卷同时挂到多台宿主机。
- 修改 `ADMIN_PASSWORD` 不会覆盖已建账号；重置需走维护流程更新密码哈希。
- SSH 指纹变化会立即拒绝连接。确认是重装或密钥轮换后，再走维护流程更新指纹，不要盲目信任新指纹。
- 目标机 SSH 用户建议最小权限专用账号 + 密钥，避免 root。
- 导出文件默认保留 24 小时；单次导出时间跨度最长 24 小时。

## 10. 停止与清理

```bash
docker compose down          # Compose
docker rm -f log-server      # 单容器
docker rm -f log-server-web log-server-worker
```

数据保留在 `log-data` 卷或 `/opt/logport-data`。
