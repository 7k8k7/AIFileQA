# DocQA 项目架构与技术报告

## 1. 项目概述

**DocQA（智能文档问答助手）** 是一个面向文档知识检索场景的全栈智能问答系统。用户可以上传多种格式的文档（PDF、DOCX、TXT、MD），系统自动解析并建立向量索引，随后通过自然语言提问获取基于文档内容的准确回答。

**定位：** 可运行、可演示、可验收的 MVP，服务于课程项目、技术作业或内部演示场景。

---

## 2. 系统架构

### 2.1 整体架构

系统采用 **前后端分离 + 可选适配代理** 的三层架构：

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│   Frontend       │    │   Backend API    │    │   External AI        │
│   React + TS     │───▶│   FastAPI        │───▶│   OpenAI / Claude /  │
│   Vite + Nginx   │    │   SQLite + Chroma│    │   Compatible APIs    │
│   :8080          │    │   :8000          │    │                      │
└──────────────────┘    └──────────────────┘    └──────────────────────┘
                                │                         ▲
                                │                         │
                        ┌───────▼────────┐    ┌───────────┴──────────┐
                        │  Local Storage  │    │  Adapter Proxy       │
                        │  uploads/       │    │  (可选) :11435       │
                        │  data/chroma    │    │  HuggingFace TGI 等  │
                        │  data/docqa.db  │    └──────────────────────┘
                        └────────────────┘
```

### 2.2 逻辑分层

| 层级 | 职责 | 实现 |
|------|------|------|
| **表现层** | 页面交互、表单、消息流、状态反馈 | React + Ant Design |
| **接口层** | 路由、请求校验、统一响应和错误处理 | FastAPI Routers |
| **应用层** | 文档服务、问答服务、Provider 服务、任务调度 | Service 模块 |
| **领域层** | 文档、会话、消息、Provider、任务对象 | SQLAlchemy Models |
| **基础设施层** | 文件存储、数据库、Embedding、LLM 调用、文档解析 | ChromaDB / SQLite / httpx |

---

## 3. 技术栈总览

### 3.1 后端

| 组件 | 技术 | 选用原因 |
|------|------|----------|
| Web 框架 | **FastAPI 0.115+** | 原生 async/await，自带 OpenAPI 文档，性能优异 |
| 运行时 | **Uvicorn 0.34+** | ASGI 高性能服务器，与 FastAPI 天然配合 |
| ORM | **SQLAlchemy 2.0 (async)** | Python 生态最成熟的 ORM，2.0 版原生支持 async |
| 数据库 | **SQLite + aiosqlite** | 零运维、文件级数据库，MVP 阶段足够，避免引入额外基础设施 |
| 数据库迁移 | **Alembic 1.15+** | SQLAlchemy 官方迁移工具，版本化管理 schema 变更 |
| 向量数据库 | **ChromaDB 0.5+** | 嵌入式向量数据库，无需独立部署，API 简洁 |
| 文档解析 | **PyMuPDF 1.25+, python-docx 1.1+** | PDF 和 DOCX 的高质量文本提取 |
| HTTP 客户端 | **httpx 0.28+** | 支持 async 和流式响应，用于调用 LLM API |
| 配置管理 | **Pydantic Settings 2.7+** | 类型安全的环境变量管理，与 FastAPI 深度集成 |
| 加密 | **cryptography (Fernet)** | API 密钥加密存储 |

### 3.2 前端

| 组件 | 技术 | 选用原因 |
|------|------|----------|
| 框架 | **React 19.2+** | 生态最大、社区支持最广的前端框架 |
| 语言 | **TypeScript 5.9+** | 类型安全，减少运行时错误 |
| 构建工具 | **Vite 8** | 极快的 HMR 和构建速度 |
| 路由 | **React Router v7** | React 官方推荐路由方案 |
| UI 组件库 | **Ant Design v6.3+** | 企业级组件库，表单/表格/布局开箱即用 |
| 服务端状态 | **TanStack React Query 5.95+** | 自动缓存、重新获取、乐观更新 |
| 客户端状态 | **Zustand 5.0+** | 轻量、无 boilerplate 的状态管理 |
| HTTP 客户端 | **Axios 1.13+** | REST 请求；SSE 使用原生 fetch + ReadableStream |
| Markdown 渲染 | **react-markdown 10.1+ / rehype-sanitize** | 安全渲染 LLM 输出的 Markdown |
| 测试 | **Vitest 4.1+ / @testing-library/react** | 与 Vite 深度集成，运行速度快 |

### 3.3 Adapter Proxy（可选）

| 组件 | 技术 | 选用原因 |
|------|------|----------|
| 框架 | **FastAPI** | 与后端统一技术栈 |
| 模板 | **Jinja2 3.1+** | 灵活的请求/响应模板转换 |
| 配置 | **PyYAML 6.0+** | YAML 配置驱动，新增适配器无需改代码 |

### 3.4 DevOps

| 组件 | 技术 | 选用原因 |
|------|------|----------|
| 容器化 | **Docker + Docker Compose** | 一键启动全栈，环境一致性 |
| 前端部署 | **Nginx** | 静态文件 + 反向代理 |
| 数据持久化 | **Docker Volumes** | 数据库和上传文件的持久化 |

---

## 4. 核心功能模块

### 4.1 文档管理

- **上传：** 支持 `.txt`、`.md`、`.pdf`、`.docx`，最大 50MB
- **解析流水线：** 上传 → 文本提取 → 切片（500 字符/片，50 字符重叠）→ Embedding 生成 → 向量写入 ChromaDB
- **状态机：** `上传中` → `解析中` → `可用` / `失败`
- **后台任务：** `ProcessPoolExecutor`（2 工作进程）独立进程执行 CPU 密集型解析，不阻塞主事件循环
- **重试机制：** 最多 3 次重试，5 分钟超时检测僵死任务

### 4.2 RAG 问答

- **混合检索：** 向量语义搜索（权重 0.65）+ 关键词匹配（权重 0.35）
- **降级策略：** 向量+关键词 → 仅向量 → 仅关键词 → 无上下文提示
- **上下文管理：** 保留最近 8 条消息完整内容 + 更早消息摘要（1200 字符上限），总字符预算 3000
- **流式输出：** SSE 逐字推送，事件类型包括 `sources`（来源引用）、`token`（流式文本）、`done`（完成）、`error`（错误）
- **范围控制：** 支持"全部文档"或"指定文档"两种问答范围

### 4.3 Provider 管理

- **多 Provider 支持：** OpenAI、Claude、OpenAI 兼容 API（含通过 Adapter Proxy 接入的本地模型）
- **API 密钥安全：** Fernet 对称加密存储，日志中自动脱敏
- **连通性测试：** 发送极小请求验证配置可用性，自动适配不同 Provider 的参数差异
- **默认 Provider：** 全局唯一默认，新建会话自动绑定

### 4.4 Adapter Proxy

将非 OpenAI 兼容的推理服务翻译为标准 `/v1/chat/completions` 格式：

- **HuggingFace TGI 适配器：** 原生 TGI API 转换
- **Generic 适配器：** Jinja2 模板驱动，通过 YAML 配置接入任意 HTTP 推理服务，无需编写代码

---

## 5. 数据模型

```
documents                    document_chunks
├── id (d-xxxx)             ├── id (c-xxxx)
├── file_name               ├── document_id (FK)
├── file_ext                ├── chunk_index
├── file_size               ├── content
├── storage_path            ├── page_no
├── status                  ├── section_label
├── error_message           ├── embedding (JSON)
└── timestamps              └── created_at

chat_sessions               chat_messages
├── id (s-xxxx)             ├── id (m-xxxx)
├── title                   ├── session_id (FK)
├── scope_type              ├── role (user/assistant)
├── provider_id (FK)        ├── content
├── document_id(s)          ├── sources_json
└── timestamps              └── created_at

provider_configs            jobs
├── id (p-xxxx)             ├── id (j-xxxx)
├── provider_type           ├── job_type
├── base_url                ├── document_id (FK)
├── model_name              ├── status
├── _api_key_encrypted      ├── retry_count / max_retries
├── embedding_model         ├── error_message
├── enable_embedding        └── timestamps
├── is_default
└── timestamps
```

---

## 6. 关键数据流

### 6.1 文档上传与解析

```
用户选择文件 → POST /api/documents (multipart)
  → 校验格式 & 大小 → 文件落盘 → 创建 document 记录 (状态: 上传中)
  → 创建 Job (状态: pending)
  → 后台 Worker 认领 Job → document 状态: 解析中
  → ProcessPool 解析文本 → 切片 (500字符/50重叠)
  → 调用 Provider Embedding API → 向量写入 ChromaDB
  → document 状态: 可用 | 失败
```

### 6.2 问答流程（RAG）

```
用户输入问题 → POST /api/chat/sessions/{id}/messages
  → 保存用户消息 → 获取会话历史
  → 混合检索：
    ├── 向量检索 (ChromaDB, provider 隔离)
    └── 关键词检索 (SQLite LIKE)
    └── 加权合并 (0.65 向量 + 0.35 关键词)
  → 构建 RAG Prompt (系统提示 + 文档片段 + 历史上下文)
  → 流式调用 LLM API (SSE)
  → 前端逐字渲染 + 来源引用展示
  → 保存 assistant 消息 + sources
```

---

## 7. API 端点概览

| 模块 | 端点 | 说明 |
|------|------|------|
| 健康检查 | `GET /health` | 服务存活检测 |
| 文档管理 | `POST /api/documents` | 上传文档 |
|  | `GET /api/documents` | 查询列表（支持搜索/分页） |
|  | `GET /api/documents/{id}` | 查询详情 |
|  | `DELETE /api/documents/{id}` | 删除文档 |
| Provider | `POST /api/providers` | 创建配置 |
|  | `PUT /api/providers/{id}` | 更新配置 |
|  | `DELETE /api/providers/{id}` | 删除配置 |
|  | `POST /api/providers/{id}/test` | 测试连通性 |
|  | `POST /api/providers/{id}/set-default` | 设为默认 |
| 会话 | `POST /api/chat/sessions` | 创建会话 |
|  | `GET /api/chat/sessions` | 查询列表 |
|  | `DELETE /api/chat/sessions/{id}` | 删除会话 |
|  | `GET /api/chat/sessions/{id}/messages` | 查询历史消息 |
|  | `POST /api/chat/sessions/{id}/messages` | 发送消息 (SSE) |
| 检索 | `POST /api/retrieval/chunks` | 文档切片搜索 |

---

## 8. 项目结构

```
FileManagement/
├── docker-compose.yml           # 容器编排
├── docs/                        # 项目文档
│   ├── prd.md                   # 产品需求文档
│   ├── tech.md                  # 技术方案文档
│   ├── test.md                  # 测试策略
│   └── deployment.md            # 部署指南
│
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 应用入口、生命周期、路由注册
│   │   ├── core/                # 基础设施：配置、数据库、安全、日志
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── api/                 # FastAPI 路由（4 个模块）
│   │   └── services/            # 业务逻辑（11 个服务模块）
│   ├── alembic/                 # 数据库迁移脚本
│   ├── tests/                   # pytest 测试套件
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/                    # React TypeScript 前端
│   ├── src/
│   │   ├── main.tsx             # React 入口
│   │   ├── App.tsx              # 根组件 & 路由
│   │   ├── pages/               # 三大页面（Documents / Chat / Settings）
│   │   ├── services/            # API 客户端（Axios + SSE）
│   │   ├── hooks/               # React Query 自定义 Hook
│   │   ├── stores/              # Zustand 状态管理
│   │   ├── theme/               # Ant Design 主题配置
│   │   └── types/               # TypeScript 接口定义
│   ├── Dockerfile
│   └── package.json
│
├── adapter-proxy/               # 可选：非 OpenAI API 翻译代理
│   ├── main.py                  # FastAPI 服务
│   ├── adapters/                # 适配器（HuggingFace TGI / Generic）
│   ├── config.example.yaml      # 配置模板
│   └── Dockerfile
│
└── scripts/
    └── verify_stack.py          # 部署验证脚本
```

---

## 9. 技术选型理由总结

### 9.1 设计原则

1. **可运行优先：** 以最少依赖满足 MVP 交付，不引入消息队列、Redis、对象存储等额外基础设施
2. **失败可观测：** 所有失败路径有明确的状态、错误信息和日志
3. **架构可扩展：** 预留扩展能力但不为未来过度设计
4. **文档事实优先：** 问答结果严格基于已上传文档内容，减少幻觉

### 9.2 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据库 | SQLite | MVP 不需要并发写入，零运维，文件即数据库 |
| 向量库 | ChromaDB (嵌入式) | 无需独立进程，与应用同进程运行，API 简洁 |
| 任务队列 | ProcessPoolExecutor | 避免引入 Celery/Redis，CPU 密集型解析在独立进程执行 |
| 检索策略 | 混合检索 | 向量语义搜索覆盖语义相似度，关键词补充精确匹配 |
| Provider 隔离 | 向量 ID = provider::model::chunk | 不同 Provider 的 Embedding 维度不同，必须隔离 |
| SSE 流式 | Server-Sent Events | 单向推送足够，比 WebSocket 实现更简单 |
| API 密钥 | Fernet 加密 | 数据库中不存明文，密钥可通过环境变量或自动生成的文件管理 |
| 非兼容 API | 独立 Adapter Proxy | 后端和前端无需任何改动，代理层统一翻译 |

---

## 10. 部署方式

### Docker Compose（推荐）

```bash
docker compose up -d --build
# Frontend: http://localhost:8080
# Backend:  http://localhost:8000
```

### 本地开发

```bash
# 后端
cd backend && pip install -e ".[dev]" && alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && pnpm install && pnpm dev
# 访问 http://localhost:5173 (Vite dev server 代理 /api → :8000)
```

### 验证

```bash
python scripts/verify_stack.py
```

---

## 11. 测试覆盖

| 层级 | 工具 | 覆盖范围 |
|------|------|----------|
| 后端 API | pytest + pytest-asyncio | 文档/Provider/会话/消息端点 |
| 后端 Service | pytest | 解析器、Embedding、检索、LLM、向量存储、安全加密 |
| 后端集成 | pytest | 上传 → 解析 → 问答全流程 |
| 前端 Service | Vitest | HTTP 请求、错误处理 |
| 前端 Hook | Vitest + testing-library | React Query 缓存与数据获取 |
| 前端 Store | Vitest | Zustand 状态管理与流式处理 |
| 前端页面 | Vitest + testing-library | Documents / Chat / Settings 页面交互 |
| Adapter Proxy | pytest | 端点、适配器、配置加载 |
