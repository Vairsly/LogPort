# LogPort 前端

Vue 3 + Vue Router + Vite 单页应用，对接 `backend` 的 REST API。

## 开发

```bash
cd frontend
npm install
npm run dev
```

开发服务器默认 `http://127.0.0.1:5173`，`/api` 代理到 `http://127.0.0.1:9090`。
请先启动后端：

```bash
cd backend
export DATA_DIR=/tmp/logport-data
export ADMIN_PASSWORD=development-password
export SECRET_KEY=development-secret
export CREDENTIAL_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
python log_server.py
```

## 构建

```bash
npm run build
```

产物输出到 `frontend/dist`。后端通过 `FRONTEND_DIST`（默认 `frontend/dist`）托管静态资源并提供 SPA 路由回退。
