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
│   ├── api/             # 路由端点
│   └── services/        # 业务逻辑
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
