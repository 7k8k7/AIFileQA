# DocQA Backend

智能文档问答助手后端，基于 FastAPI + SQLAlchemy async + SQLite + ChromaDB。

## 技术栈

| 层 | 选型 |
|---|---|
| Web | FastAPI 0.115+ |
| 运行 | Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| 数据库 | SQLite (`aiosqlite`) |
| 迁移 | Alembic |
| 向量存储 | ChromaDB |
| 文档解析 | PyMuPDF、python-docx |
| 配置 | Pydantic Settings + `.env` |
| HTTP 客户端 | httpx |

## 当前能力

- 供应商配置：支持 OpenAI / 兼容接口 / Claude 的基础 CRUD、测试连接、设为默认
- Embedding 配置：每个 provider 可单独配置 `embedding_model` 与 `enable_embedding`
- 文档管理：支持上传 `pdf/docx/doc/txt/md/markdown`，异步解析、分块、状态流转
- 向量检索：解析完成后会尝试按默认 provider 生成 embedding；聊天检索时优先按会话绑定 provider 的 embedding 配置补齐并查询
- 检索接口：支持根据 query 返回 top-k 相关分块
- 聊天问答：支持会话、消息历史、RAG prompt 构造、SSE 流式回答

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

### 3. 执行数据库迁移

```bash
alembic upgrade head
```

### 4. 启动开发服务器

```bash
uvicorn app.main:app --reload --port 8000
```

启动后可访问：
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` | `DocQA` | 应用名称 |
| `DEBUG` | `true` | 调试模式；建议只填 `true/false` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/docqa.db` | 数据库连接串 |
| `UPLOAD_DIR` | `./uploads` | 上传文件目录 |
| `VECTOR_STORE_DIR` | `./data/chroma` | ChromaDB 本地存储目录 |
| `MAX_UPLOAD_SIZE_MB` | `50` | 单文件大小限制 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |

## 项目结构

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   ├── document.py
│   │   ├── chat.py
│   │   └── provider.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── document.py
│   │   ├── chat.py
│   │   ├── provider.py
│   │   └── retrieval.py
│   ├── api/
│   │   ├── documents.py
│   │   ├── providers.py
│   │   ├── retrieval.py
│   │   └── chat.py
│   └── services/
│       ├── document_service.py
│       ├── parser_service.py
│       ├── parsing_task.py
│       ├── embedding_service.py
│       ├── vector_store_service.py
│       ├── retrieval_service.py
│       ├── provider_service.py
│       ├── provider_url.py
│       ├── chat_service.py
│       └── llm_service.py
├── alembic/
├── uploads/
├── .env.example
└── pyproject.toml
```

## 数据模型

| 表 | 说明 |
|---|---|
| `documents` | 文档元信息、解析状态、错误信息 |
| `document_chunks` | 文档分块、页码、embedding 快照 |
| `chat_sessions` | 会话范围（全部文档 / 单文档） |
| `chat_messages` | user / assistant 消息 |
| `provider_configs` | 模型供应商配置 |

## API 概览

### 文档 `/api/documents`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/documents` | 分页列表，支持 `keyword/page/page_size` |
| `GET` | `/api/documents/{id}` | 单文档详情 |
| `POST` | `/api/documents` | 上传文件，后台自动解析 + 向量化 |
| `DELETE` | `/api/documents/{id}` | 删除文档、磁盘文件和向量数据 |

文档状态流转：
- `上传成功 -> 解析中 -> 可用`
- 失败时为 `解析失败`

### 供应商 `/api/providers`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/providers` | 列表，`api_key` 脱敏返回 |
| `GET` | `/api/providers/{id}` | 明细，返回完整配置和完整 `api_key` |
| `POST` | `/api/providers` | 创建供应商 |
| `PUT` | `/api/providers/{id}` | 更新供应商 |
| `POST` | `/api/providers/{id}/test` | 测试连接 |
| `POST` | `/api/providers/{id}/set-default` | 设为默认供应商 |
| `DELETE` | `/api/providers/{id}` | 删除供应商 |

`base_url` 建议填写供应商根地址，不要手动再拼接口路径。

示例：
- OpenAI：`https://api.openai.com`
- Anthropic：`https://api.anthropic.com`

Provider 配置补充说明：
- `model_name` 用于聊天生成
- `embedding_model` 用于 `/v1/embeddings`
- `enable_embedding=true` 且 provider 支持 embedding 时，系统会优先使用该 provider 做向量检索
- `claude` 当前不走 embedding，会自动退回关键词检索
- `openai_compatible` 适配本地模型时，只有本地服务真的支持 `/v1/embeddings` 才能走 embedding

### 检索 `/api/retrieval`

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/retrieval/chunks` | 根据 query 返回 top-k 相关分块 |

请求体示例：

```json
{
  "query": "alpha question",
  "provider_id": "p-xxxx",
  "scope_type": "single",
  "document_ids": ["d-xxxx", "d-yyyy"],
  "top_k": 6
}
```

说明：
- `provider_id` 可选；传入后会优先使用该 provider 的 embedding 配置
- `single` 范围可传 `document_id` 或 `document_ids`
- 如果 provider 未开启 embedding、当前 provider 不支持 embedding，或向量化失败，会自动退回关键词检索

### 聊天 `/api/chat`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/chat/sessions` | 会话列表 |
| `POST` | `/api/chat/sessions` | 创建会话，可绑定 provider 和多个文档 |
| `DELETE` | `/api/chat/sessions/{id}` | 删除会话 |
| `GET` | `/api/chat/sessions/{id}/messages` | 消息历史 |
| `POST` | `/api/chat/sessions/{id}/messages` | 发送消息，SSE 流式返回 |
| `POST` | `/api/chat/sessions/{id}/messages/{message_id}/regenerate` | 重新生成最后一条助手回复 |

SSE 事件格式：

```text
data: {"type":"sources","retrieval_method":"vector","chunks":[...]}
data: {"type":"token","content":"你好"}
data: {"type":"done","message_id":"m-xxxx"}
data: {"type":"error","content":"错误信息"}
```

## 开发说明

- 应用启动时会执行 `Base.metadata.create_all()` 作为开发期兜底，但正式建表仍建议以 `alembic upgrade head` 为准。
- 检索优先走“当前会话 provider 对应 embedding 空间”的 ChromaDB 向量搜索；如果该 provider 没开 embedding、不支持 embedding，或当前向量不存在，会回退到关键词匹配。
- 向量库按 `provider_id + embedding_model + chunk_id` 隔离，避免不同 provider / 不同 embedding 模型的向量混用。
- 解析任务使用后台异步任务 + 进程池，上传接口会先返回，再继续处理文档。
