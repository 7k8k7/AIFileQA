# DocQA Backend

智能文档问答助手后端服务，基于 FastAPI + SQLAlchemy async + SQLite。

## 技术栈

| 层 | 选型 |
|-----|------|
| 框架 | FastAPI 0.115+ |
| 运行时 | Uvicorn (ASGI) |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | SQLite (aiosqlite) |
| 迁移 | Alembic |
| 配置 | Pydantic Settings + .env |
| HTTP 客户端 | httpx (async) |

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 按需修改 .env 中的配置
```

### 3. 执行数据库迁移

```bash
alembic upgrade head
```

### 4. 启动开发服务器

```bash
uvicorn app.main:app --reload --port 8000
```

服务启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 项目结构

```
backend/
├── app/
│   ├── main.py          # FastAPI 入口 + CORS + lifespan
│   ├── core/
│   │   ├── config.py    # Pydantic Settings 配置
│   │   └── database.py  # async engine + session
│   ├── models/          # SQLAlchemy ORM 模型
│   │   ├── document.py  # 文档表
│   │   ├── chat.py      # 会话 + 消息表
│   │   └── provider.py  # LLM 供应商配置表
│   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── common.py    # PaginatedResponse 通用分页
│   │   ├── document.py  # DocumentOut
│   │   ├── chat.py      # SessionCreate/Out, MessageOut/Send
│   │   └── provider.py  # ProviderCreate/Update/Out + mask_api_key
│   ├── api/             # 路由端点
│   │   ├── documents.py # /api/documents   CRUD + 上传
│   │   ├── providers.py # /api/providers   CRUD + 测试连接
│   │   └── chat.py      # /api/chat        会话 + 消息 + SSE 流式
│   └── services/        # 业务逻辑
│       ├── document_service.py  # 文档 CRUD + 文件存储
│       ├── provider_service.py  # 供应商 CRUD + 连接测试
│       ├── chat_service.py      # 会话/消息 CRUD
│       └── llm_service.py       # LLM 流式调用 (OpenAI + Claude)
├── alembic/             # 数据库迁移
├── uploads/             # 上传文件存储
├── .env.example         # 环境变量模板
└── pyproject.toml       # 依赖 + 构建配置
```

## 数据库模型

| 表 | 说明 |
|----|------|
| `documents` | 文档元信息 + 解析状态 |
| `chat_sessions` | 会话（支持全部/单文档检索范围） |
| `chat_messages` | 聊天消息（user / assistant） |
| `provider_configs` | LLM 供应商配置（API Key 加密存储） |

## 数据库迁移

```bash
# 生成新迁移
alembic revision --autogenerate -m "描述"

# 升级到最新
alembic upgrade head

# 回退一步
alembic downgrade -1
```

## API 端点

### 文档管理 `/api/documents`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/documents` | 分页列表，支持 `keyword` / `page` / `page_size` |
| GET | `/api/documents/{id}` | 单文档详情 |
| POST | `/api/documents` | 上传文件（multipart, 50MB 限制, PDF/DOCX/TXT/MD） |
| DELETE | `/api/documents/{id}` | 删除文档 + 磁盘文件 |

### 供应商配置 `/api/providers`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/providers` | 供应商列表（API Key 脱敏返回） |
| POST | `/api/providers` | 创建供应商（首个自动设为默认） |
| PUT | `/api/providers/{id}` | 更新供应商 |
| POST | `/api/providers/{id}/test` | 测试连接（OpenAI / Claude 双协议） |
| POST | `/api/providers/{id}/set-default` | 设为默认供应商 |
| DELETE | `/api/providers/{id}` | 删除（默认供应商禁止删除） |

### 智能问答 `/api/chat`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/chat/sessions` | 会话列表（按更新时间倒序） |
| POST | `/api/chat/sessions` | 创建会话（支持 all / single 范围） |
| DELETE | `/api/chat/sessions/{id}` | 删除会话（级联删除消息） |
| GET | `/api/chat/sessions/{id}/messages` | 消息历史 |
| POST | `/api/chat/sessions/{id}/messages` | 发送消息 → SSE 流式响应 |

SSE 事件格式：
```
data: {"type":"token","content":"你好"}
data: {"type":"done","message_id":"m-xxxx"}
data: {"type":"error","content":"错误信息"}
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_NAME` | DocQA | 应用名称 |
| `DEBUG` | true | 调试模式（开启 SQL 日志） |
| `DATABASE_URL` | sqlite+aiosqlite:///./data/docqa.db | 数据库连接串 |
| `UPLOAD_DIR` | ./uploads | 文件上传目录 |
| `MAX_UPLOAD_SIZE_MB` | 50 | 单文件最大体积 (MB) |
| `HOST` | 0.0.0.0 | 监听地址 |
| `PORT` | 8000 | 监听端口 |
