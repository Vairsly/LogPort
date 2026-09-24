# LogPort 前端设计

技术栈：Vue 3 · Vue Router · Vite。生产构建产物由后端托管（也可用 Nginx 托管并反代 `/api`）。

## 设计原则

- 与运维控制台一致的侧栏 + 面卡片布局，便于长时间盯任务。
- 表单即时校验 + 服务端错误原文展示，避免二次猜测。
- 任务列表自动刷新（5s），命令可一键复制。
- 敏感操作（删除服务器、确认 SSH 指纹）使用确认对话框，不用原生 `alert` 链路打断主流程。

## 视觉规范

| Token | 值 | 用途 |
|---|---|---|
| `--bg` | `#f4f7fb` | 页面底 |
| `--panel` | `#ffffff` | 卡片 |
| `--ink` | `#172033` | 主文字 |
| `--muted` | `#697386` | 辅助文字 |
| `--primary` | `#5b5ce2` | 主操作 |
| `--primary2` | `#7374ee` | 主按钮渐变端 |
| `--danger` | `#c53030` | 错误 |
| `--success` | `#087f5b` | 成功 |

字体：`Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif`  
圆角：按钮/输入 `9px`，卡片 `12–16px`。

## 模块

```text
src/
├── main.js
├── App.vue
├── style.css
├── api/client.js       # fetch 封装 + CSRF
├── router/index.js     # 路由与登录守卫
├── views/
│   ├── LoginView.vue
│   └── DashboardView.vue
└── components/
    ├── ExportPanel.vue
    ├── TaskList.vue
    ├── ServerList.vue
    └── ToastHost.vue
```

## 交互要点

### 登录

- 成功后写入 CSRF，跳转 `/`。
- 失败展示服务端 `error`（含限速提示）。

### 导出

- 两种时间模式互斥切换：「最近一段时间」与「指定时间范围」。
- 服务器变更联动容器下拉（仅白名单）。
- 提交成功 toast 后跳转任务页。

### 任务

- 状态徽标映射中文；失败展示截断错误，悬停看全文。
- 成功任务提供下载按钮（同源 Cookie 鉴权）。

### 服务器

- 卡片列表 + 对话框编辑。
- 「测试连接」处理 409 指纹确认流：弹出指纹对话框 → 用户核对 → `confirm_fingerprint`。

## 本地开发

```bash
cd frontend
npm install
npm run dev
```

Vite 代理：`/api` → `http://127.0.0.1:9090`。

## 生产构建

```bash
npm run build   # → frontend/dist
```

后端默认读取 `FRONTEND_DIST=frontend/dist`；未构建时访问 `/` 返回 503 提示。
