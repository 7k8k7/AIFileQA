# DocQA Backend

智能文档问答助手后端，基于 FastAPI + SQLAlchemy async + SQLite + ChromaDB。

项目级启动和验收入口见：

- [README.md](/d:/documentD/works/AgenticEngineering/FileManagement/README.md)
- [docs/deployment.md](/d:/documentD/works/AgenticEngineering/FileManagement/docs/deployment.md)

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
- 非兼容接口适配：通过 adapter-proxy 将 HuggingFace TGI 等非兼容 API 翻译为 OpenAI 格式，后端无需改动（详见 [adapter-proxy/README.md](/adapter-proxy/README.md)）
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

## Docker 运行

项目根目录已经提供 `docker-compose.yml`，会同时启动前端和后端。

```bash
docker compose up -d --build
```

容器启动后可访问：
- 前端：`http://localhost:8080`
- 后端 API：`http://localhost:8000`
- 后端文档：`http://localhost:8000/docs`

说明：
- 后端容器启动时会自动执行 `alembic upgrade head`
- SQLite 数据和 ChromaDB 向量库保存在 Docker volume 中
- 如需停止：

```bash
docker compose down
```

## 测试

后端已经包含三层测试：
- 服务层单元测试：`parser / embedding / retrieval / llm / vector store`
- API 层测试：`documents / providers / chat`
- 集成测试：上传文档、解析、会话、SSE、provider 选择、多文档范围等全链路

运行命令：

```bash
cd backend
python -m pytest tests -q
```

说明：
- `backend/tests/conftest.py` 会在测试时覆盖本机的 `DEBUG` 环境变量，避免 Windows 全局环境变量影响 pytest 收集
- 测试使用临时 SQLite 和临时 Chroma 目录，不会污染正式数据
- 项目级前端页面交互测试说明见 [docs/test.md](/d:/documentD/works/AgenticEngineering/FileManagement/docs/test.md) 和 [frontend/README.md](/d:/documentD/works/AgenticEngineering/FileManagement/frontend/README.md)

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` | `DocQA` | 应用名称 |
| `DEBUG` | `true` | 调试模式；建议只填 `true/false` |
| `LOG_LEVEL` | `INFO` | 日志级别，例如 `DEBUG / INFO / WARNING` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/docqa.db` | 数据库连接串 |
| `PROVIDER_SECRET_KEY` | 空 | Provider 密钥加密所用的 Fernet 主密钥；生产环境建议显式配置 |
| `PROVIDER_SECRET_FILE` | `./data/provider_secret.key` | 未配置 `PROVIDER_SECRET_KEY` 时，本地自动生成并持久化的密钥文件 |
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
- `上传中 -> 解析中 -> 可用`
- 失败时为 `失败`

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
- adapter-proxy（接入非兼容本地模型时）：`http://localhost:11435` 或 `http://adapter-proxy:11435`

Provider 配置补充说明：
- `model_name` 用于聊天生成
- `embedding_model` 用于 `/v1/embeddings`
- `enable_embedding=true` 且 provider 支持 embedding 时，系统会优先使用该 provider 做向量检索
- `claude` 当前不走 embedding，会自动退回关键词检索
- `openai_compatible` 适配本地模型时，只有本地服务真的支持 `/v1/embeddings` 才能走 embedding
- 如果本地模型不提供 OpenAI 兼容接口，可通过 adapter-proxy 翻译后再用 `openai_compatible` 接入

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

### 可观测性

当前后端已经补充了基础运行日志，默认会记录：

- 启动和关闭
- provider 创建、更新、设为默认、连通性测试
- 文档解析和 embedding 生成
- 检索命中的文档片段摘要、检索方式、回退原因
- 聊天流开始、结束、保存失败、重新生成

说明：
- 日志里不会输出完整 `api_key`
- 可通过 `LOG_LEVEL=DEBUG` 提高排查细节

### 数据安全

当前版本已经对 provider 的 `api_key` 做了存储加密：

- 写入数据库前会自动加密
- 读取时会自动解密，上层业务代码无需手动处理
- 旧的明文数据仍可兼容读取，避免升级后立即失效
- 日志中不会打印完整 `api_key`

建议：

- 本地开发可直接使用自动生成的 `PROVIDER_SECRET_FILE`
- 生产或演示环境建议显式配置固定的 `PROVIDER_SECRET_KEY`
- 如果更换了主密钥，旧数据将无法解密，因此不要随意变更

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
- Provider 更新时如果传入空 `api_key`，后端会保留旧 key，不会误清空。
