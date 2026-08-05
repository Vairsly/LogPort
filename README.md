# LogPort 多服务器日志导出工具

LogPort 是一个集中式 Docker 日志导出服务。管理员在浏览器中选择服务器、容器及时间范围，Worker 通过 SSH 执行受控的 `docker logs`，完成后提供日志下载。

## 快速部署

1. 复制配置：`cp .env.example .env`。
2. 设置强随机 `ADMIN_PASSWORD`、`SECRET_KEY` 和 `CREDENTIAL_KEY`。加密密钥可按 `.env.example` 中的命令生成，部署后不得随意更换，否则已有 SSH 凭据无法解密。
3. 启动：`docker compose up -d --build`。
4. 浏览器访问 `http://127.0.0.1:9090`，首次启动自动创建管理员。
5. 生产环境由 Nginx 或 Caddy 反向代理并启用 HTTPS，同时设置 `COOKIE_SECURE=true`。

服务默认仅绑定宿主机回环地址。Web 和 Worker 共享 `log-data` 数据卷，其中包含 SQLite 数据库与导出文件。

## 使用流程

在“服务器管理”中添加 SSH 地址、认证凭据和容器白名单，然后点击“测试连接”。首次连接会显示 SSH SHA-256 指纹，必须与目标服务器管理员核对后确认。验证成功后即可创建日志任务。

目标 SSH 用户需要登录权限及执行 `docker version`、`docker logs` 的权限。建议创建权限最小化的专用用户与 SSH 密钥，不使用 root 或日常账号。

任务最长覆盖 24 小时。日志生成后保留 24 小时，Worker 自动删除过期文件。任务执行失败时页面会展示脱敏后的错误摘要。

## 本地开发与测试

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
export DATA_DIR=/tmp/logport-data
export ADMIN_PASSWORD=development-password
export SECRET_KEY=development-secret
export CREDENTIAL_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
flask --app log_server run --port 9090
```

另一个终端运行 `python -m log_exporter.worker`。测试命令为 `pytest -q`。

## 运维说明

- 备份时同时保存数据卷和 `CREDENTIAL_KEY`，两者缺一不可。
- SQLite 适用于当前单机部署，不应同时挂载到多台宿主机。
- 修改 `ADMIN_PASSWORD` 不会覆盖已创建账号；需要重置时应通过维护流程更新密码哈希。
- 服务器指纹变化会立即阻止连接。确认是主机重装或密钥轮换后，重新保存服务器并按维护流程更新指纹；不要未经核对直接信任新指纹。
