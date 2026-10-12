# LogPort 多服务器日志导出工具

LogPort 是集中式 Docker 日志导出服务。管理员在浏览器选择服务器、容器及时间范围，Worker 通过 SSH 执行受控的 `docker logs`，完成后提供日志下载。

## 项目结构

```text
frontend/   Vue 3 + Vite 单页应用
backend/    Flask API、Worker、测试
doc/        设计文档（架构 / API / 前端 / 版本发布）
deploy.md   部署文档
```

## 快速开始

### 本地开发（推荐脚本）

```bash
./dev.sh setup   # 首次：venv + 依赖 + .env
./dev.sh up      # 同时启动 后端 + Worker + 前端
```

浏览器打开 `http://127.0.0.1:5173`。停止：`./dev.sh down`。

| 命令 | 说明 |
|---|---|
| `./dev.sh setup` | 一次性准备环境 |
| `./dev.sh up` / `down` | 启停开发三件套 |
| `./dev.sh status` / `logs` | 状态 / 日志 |
| `./dev.sh test` | 后端测试 |
| `./dev.sh build` | 构建前端生产包 |
| `./dev.sh deploy` | Docker Compose 部署 |

### 生产部署

```bash
cp .env.example .env
# 编辑 .env，设置强随机 ADMIN_PASSWORD / SECRET_KEY / CREDENTIAL_KEY
./dev.sh deploy
# 或: docker compose up -d --build
```

浏览器访问 `http://127.0.0.1:9090`。Compose、离线安装与 HTTPS 反代见 **[deploy.md](deploy.md)**。

## 文档

| 文档 | 内容 |
|---|---|
| [doc/design.md](doc/design.md) | 总体架构、模块、安全与扩展 |
| [doc/api.md](doc/api.md) | REST 接口说明 |
| [doc/frontend.md](doc/frontend.md) | 前端设计与开发 |
| [doc/RELEASE.md](doc/RELEASE.md) | 版本发布记录 |
| [deploy.md](deploy.md) | 部署、配置、运维 |

## 使用流程

1. 在「服务器管理」中添加 SSH 地址、认证凭据和容器白名单，点击「测试连接」。
2. 首次连接会显示 SSH SHA-256 指纹，必须与目标服务器管理员核对后确认。
3. 在「日志导出」创建任务；在「任务记录」查看进度并下载。

目标 SSH 用户需要登录权限及执行 `docker version`、`docker logs` 的权限。建议使用权限最小化的专用用户与 SSH 密钥。

任务最长覆盖 24 小时。日志生成后保留 24 小时，Worker 自动删除过期文件。任务失败时页面展示脱敏错误摘要。

## 本地开发与测试

详见 [deploy.md](deploy.md#8-本地开发)。测试：

```bash
cd backend && pytest -q
```

## 运维提示

- 备份时同时保存数据卷和 `CREDENTIAL_KEY`，两者缺一不可。
- SQLite 适用于单机部署，不应同时挂载到多台宿主机。
- 修改 `ADMIN_PASSWORD` 不会覆盖已创建账号。
- 服务器指纹变化会立即阻止连接；确认变更原因后再更新指纹。
