# DocQA Frontend

智能文档问答助手前端，基于 React + Vite + Ant Design，已接入真实后端 API。

## 技术栈

| 层 | 技术 |
|---|---|
| 框架 | React 19 + TypeScript |
| 构建 | Vite 8 |
| 路由 | React Router v7 |
| UI | Ant Design v5 |
| 服务端状态 | TanStack Query |
| 本地状态 | Zustand |
| HTTP | Axios |
| 流式 | 原生 `fetch` + `ReadableStream` |

## 当前能力

- 文档管理：列表、搜索、上传、删除
- 系统设置：供应商创建、编辑、测试连接、设为默认、删除
- Provider 高级配置：支持单独配置 `embedding_model`、`enable_embedding`，编辑时会回显真实 `api_key`，但默认隐藏显示
- 智能问答：会话创建、消息历史、SSE 流式回答、重新生成、来源展示
- 前后端联调：开发模式默认通过 Vite 代理访问后端

## 启动

```bash
cd frontend
pnpm install
pnpm dev
```

默认地址：
- 前端：`http://localhost:5173`
- 后端开发服务建议启动在：`http://localhost:8000`

## Docker 运行

项目根目录已经提供整套容器配置：

```bash
docker compose up -d --build
```

启动后访问：
- 前端：`http://localhost:8080`
- 后端 API：`http://localhost:8000`

说明：
- 前端容器使用 `nginx` 提供静态资源
- `nginx` 会把 `/api/*` 反向代理到后端容器，因此浏览器里仍然走同源 `/api`
- SSE 流式接口同样通过这个反向代理工作

停止命令：

```bash
docker compose down
```

## 构建

```bash
pnpm build
pnpm preview
```

## 测试

前端已经接入 Vitest + jsdom，覆盖了两类核心测试：
- Zustand store：流式状态、来源状态、乐观消息
- Service 层：文档请求、SSE 解析、聊天发送与重新生成 URL

运行命令：

```bash
cd frontend
pnpm test
```

持续监听：

```bash
pnpm test:watch
```

## 联调方式

开发环境默认已经配置了代理：

- `frontend/vite.config.ts` 会把 `/api` 代理到 `http://localhost:8000`
- 前端 services 默认以 `/api` 作为 base URL

联调时同时启动：

```bash
# terminal 1
cd backend
uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
pnpm dev
```

## 环境变量

前端默认不需要额外配置即可联调。

如果要自定义接口地址，可设置：

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

注意：
- 这里应包含 `/api`
- 如果只写成 `http://localhost:8000`，当前 services 会请求到错误路径

## API 接入说明

### 文档服务

- `src/services/documents.ts`
- 使用 Axios 调真实接口
- 文件上传使用 `multipart/form-data`

### 供应商服务

- `src/services/providers.ts`
- 已接入真实 CRUD、详情、测试连接、设为默认接口
- Provider 表单同时支持聊天模型和 embedding 模型分开配置
- `openai` / `claude` 的 `api_key` 必填；`openai_compatible` 连接本地模型时可留空
- `claude` 的 embedding 开关会自动禁用

### 聊天服务

- `src/services/chat.ts`
- `sendMessage(sessionId, content, callbacks)` 签名保持不变
- SSE 由 `src/services/api.ts` 里的 `sseStream()` 负责
- 因为 Axios 不支持 `ReadableStream`，这里改用原生 `fetch`
- 新建会话时可选择 provider，并把该 provider 绑定到会话
- 单文档范围支持选择多个文档；头部默认只显示第一个文件名摘要，点击后可查看完整列表
- provider 更新为空 key 时，前端可以安全提交，后端会保留原 key

SSE 事件约定：

```text
data: {"type":"sources","retrieval_method":"vector","chunks":[...]}
data: {"type":"token","content":"..."}
data: {"type":"done","message_id":"..."}
data: {"type":"error","content":"..."}
```

说明：
- `sources` 会先于 token 到达，用于展示本次回答参考了哪些文档片段
- assistant 消息的来源会跟消息一起持久化，刷新后仍可查看历史来源
- 重新生成会显式告诉模型“用户对上一条回答不满意”，而不是单纯随机重试

## 目录结构

```text
src/
├── main.tsx
├── App.tsx
├── global.css
├── theme/
├── types/
├── layouts/
├── pages/
│   ├── Documents/
│   ├── Chat/
│   └── Settings/
├── components/
├── hooks/
├── services/
│   ├── api.ts
│   ├── documents.ts
│   ├── providers.ts
│   └── chat.ts
├── test/
├── stores/__tests__/
└── services/__tests__/
```

## 页面说明

- `Documents`：文档上传、列表、搜索、删除
- `Chat`：会话管理、provider 选择、多文档范围选择、流式对话、来源查看、重新生成
- `Settings`：供应商管理、连接测试、聊天模型 / Embedding 模型分开配置

## 设计

视觉规范定义在项目根目录的 `DESIGN.md`。
