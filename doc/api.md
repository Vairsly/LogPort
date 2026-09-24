# LogPort API 说明

Base：`/api`  
鉴权：会话 Cookie（`POST /api/login` 后生效）  
修改类接口需请求头 `X-CSRF-Token`（登录响应或 `GET /api/session` 返回）

错误响应统一：

```json
{ "error": "中文错误信息" }
```

## 认证

### POST /api/login

请求：

```json
{ "username": "admin", "password": "..." }
```

响应 `200`：

```json
{ "ok": true, "csrf_token": "..." }
```

失败 `401` / 限速 `429`。

### POST /api/logout

需 CSRF。清空会话。

### GET /api/session

未登录 `401`；已登录：

```json
{ "authenticated": true, "csrf_token": "..." }
```

## 服务器

### GET /api/servers

返回服务器数组（不含任何凭据字段）：

```json
[
  {
    "id": 1,
    "name": "生产一",
    "host": "10.0.0.1",
    "port": 22,
    "username": "ops",
    "auth_type": "password",
    "host_fingerprint": "SHA256:...",
    "containers": ["api", "worker"],
    "created_at": "...",
    "updated_at": "..."
  }
]
```

### POST /api/servers

```json
{
  "name": "生产一",
  "host": "10.0.0.1",
  "port": 22,
  "username": "ops",
  "auth_type": "password",
  "secret": "password-or-private-key",
  "key_passphrase": "",
  "containers": ["api"]
}
```

`auth_type`：`password` | `private_key`。创建时 `secret` 必填。

### PUT /api/servers/{id}

同创建；`secret` / `key_passphrase` 留空则保持原值。

### DELETE /api/servers/{id}

已有导出记录时 `409`。

### POST /api/servers/{id}/test

测试 SSH 与 Docker 权限。

- 首次无指纹：`409`，`{ "confirmation_required": true, "fingerprint": "SHA256:..." }`
- 确认信任后重试，body：`{ "confirm_fingerprint": true }`
- 成功：`{ "ok": true, "fingerprint": "...", "docker_version": "..." }`

## 导出任务

### POST /api/export-tasks

```json
{
  "server_id": 1,
  "container": "api",
  "start": "2024-01-01T00:00:00+08:00",
  "end": "2024-01-01T01:00:00+08:00"
}
```

约束：

- 容器必须在服务器白名单内
- 时间必须带时区；结束晚于开始
- 结束不晚于当前时间（+1 分钟容差）
- 跨度 ≤ 24 小时

响应 `201`：`{ "id": 12, "status": "queued" }`

### GET /api/export-tasks

最近 200 条任务，不含 `file_path` / `worker_id`。

### GET /api/export-tasks/{id}

单任务详情。

### GET /api/export-tasks/{id}/download

仅 `succeeded` 且文件仍在保留期内可下载 `.log`。

## 健康检查

### GET /api/health

`{ "status": "ok" }`

## 任务状态

| 状态 | 含义 |
|---|---|
| `queued` | 等待 Worker |
| `running` | 执行中 |
| `succeeded` | 成功，可下载 |
| `failed` | 失败，含 `error` |
| `expired` | 超过保留期，文件已删 |
| `cancelled` | 已取消 |
