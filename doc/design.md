# LogPort 设计文档

LogPort 是集中式 Docker 日志导出服务：管理员在浏览器选择服务器、容器与时间范围，Worker 通过 SSH 执行受控 `docker logs`，完成后提供下载。

## 1. 总体架构

```text
┌─────────────────────┐     HTTPS / HTTP      ┌──────────────────────┐
│  Vue 3 SPA (浏览器)  │ ───────────────────► │  Flask Web (gunicorn) │
│  frontend/          │   /api/* JSON + Cookie│  backend/log_exporter │
└─────────────────────┘                       └──────────┬───────────┘
                                                         │ SQLite
                                                         ▼
                                              ┌──────────────────────┐
                                              │  Worker (python -m)  │
                                              │  SSH → docker logs   │
                                              └──────────────────────┘
```

- **frontend/**：Vue 3 单页应用，负责登录、导出表单、任务列表、服务器管理。
- **backend/**：Flask 应用工厂 + REST API + SQLite + SSH/Worker；生产模式同时托管 `frontend/dist`。
- **数据卷**：SQLite 与导出文件写入 `DATA_DIR`（Compose 中为 `log-data`）。

## 2. 目录结构

```text
log-server/
├── frontend/          # Vue 3 + Vite SPA
├── backend/           # Flask API、Worker、测试
│   ├── log_exporter/
│   ├── log_server.py
│   └── tests/
├── doc/               # 设计文档
├── deploy.md          # 部署文档
├── docker-compose.yml
└── Dockerfile         # 多阶段：frontend build + backend runtime
```

## 3. 前端设计

### 3.1 技术选型

| 项 | 选择 | 说明 |
|---|---|---|
| 框架 | Vue 3 Composition API | 轻量、组件化，便于表单与列表拆分 |
| 路由 | vue-router (history) | `/login`、`/`、`/tasks`、`/servers` |
| 构建 | Vite | 开发代理 `/api`，生产输出 `dist` |
| 状态 | 组合式函数 + provide/inject | 不引入 Pinia，规模足够 |

### 3.2 页面与组件

| 路径 | 组件 | 职责 |
|---|---|---|
| `/login` | `LoginView` | 登录，写入 CSRF Token |
| `/` | `ExportPanel` | 创建导出任务（最近 N 分钟/小时 或指定范围） |
| `/tasks` | `TaskList` | 任务状态、命令复制、下载、5s 轮询 |
| `/servers` | `ServerList` | 服务器 CRUD、测试连接、指纹确认对话框 |

### 3.3 API 约定

- 内容类型 `application/json`。
- 会话 Cookie 鉴权；修改类请求头 `X-CSRF-Token`。
- 401 时前端跳转登录；错误信息统一 `data.error`。
- 时间输入使用浏览器本地时区，提交时转为带时区的 ISO 8601。

## 4. 后端设计

### 4.1 模块

| 模块 | 职责 |
|---|---|
| `log_exporter/__init__.py` | 应用工厂、配置、SPA 托管 |
| `auth.py` | 登录/登出/会话、登录限速 |
| `api.py` | 服务器、导出任务、下载、健康检查 |
| `security.py` | CSRF、登录守卫、凭据加密 |
| `ssh_client.py` | SSH 连接、指纹校验、受控 docker logs |
| `worker.py` | 任务领取、执行、过期清理 |
| `run_all.py` | 同容器启动 Web + Worker |
| `db.py` | SQLite schema 与初始化 |

### 4.2 异步任务流

1. Web 创建 `queued` 任务，校验白名单、时间跨度 ≤ 24h。
2. Worker 以 `BEGIN IMMEDIATE` 原子领取为 `running`。
3. SSH 流式写入 `task-{id}.part`，完成后 `os.replace` 为 `task-{id}.log`。
4. 成功记录 `expires_at`（默认 +24h）；维护循环删除过期文件并标记 `expired`。
5. Worker 重启后将卡住超过 1 小时的 `running` 标为 `failed`。

### 4.3 数据模型

- `users`：管理员（Argon2 密码哈希）。
- `servers`：SSH 目标、认证方式、加密凭据、主机指纹、容器白名单 JSON。
- `export_tasks`：任务状态机 `queued → running → succeeded|failed`，以及 `expired|cancelled`。

SSH 凭据仅存密文，查询接口永不返回 `secret` / `key_passphrase`。

## 5. 安全设计

- 初始管理员由环境变量引导创建；`SECRET_KEY`、`CREDENTIAL_KEY` 由环境注入。
- 凭据使用 Fernet（`CREDENTIAL_KEY`）加密入库。
- 写接口 CSRF；会话 `HttpOnly` + `SameSite=Lax`，HTTPS 下 `Secure`。
- 登录 IP 限速（5 分钟 10 次）。
- 导出命令参数 `shlex.quote`，禁止任意命令。
- SSH 主机指纹首次确认后锁定；变化则拒绝连接。
- 下载路径必须位于 `EXPORT_DIR` 之内，防路径穿越。

## 6. 扩展点

- 多 Worker：已用领取锁，可水平增加 Worker 进程/实例（共享数据卷）。
- PostgreSQL：替换 `db.py` 连接层即可。
- 统一登录 / 角色：在 `auth` 增加身份源与权限装饰器。
- 多容器批量导出：扩展任务表为一对多明细。

## 7. 验收要点

见 `deploy.md` 与根 `README.md`；单元测试覆盖登录/CSRF、凭据不外泄、时间与白名单校验、路径穿越拒绝、任务原子领取。
