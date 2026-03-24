# DocQA

智能文档问答助手，包含：

- 文档管理：上传、查询、删除、状态跟踪
- Agent 问答：多轮对话、来源展示、重新生成
- 系统设置：OpenAI、Claude、本地兼容模型配置

## 最快启动

### Docker 一条命令启动

```bash
docker compose up -d --build
```

启动后访问：

- 前端：`http://localhost:8080`
- 后端：`http://localhost:8000`
- 后端文档：`http://localhost:8000/docs`

### Docker 一条命令验收

```bash
python scripts/verify_stack.py
```

如果全部通过，你会看到：

- 后端健康检查正常
- 前端首页可访问
- 前端代理到后端的 `/health` 正常
- 前端代理到后端的 `/api/providers` 正常

## 本地开发最短路径

### 1. 启动后端

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

本地开发地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

### 3. 本地开发验收

```bash
python scripts/verify_stack.py --frontend-url http://localhost:5173 --backend-url http://localhost:8000
```

## 最短手工验收路径

无论是 Docker 还是本地开发，都建议按下面这条链路做最后验收：

1. 打开系统设置页，添加一个可用 provider
2. 测试连接成功，并确认默认 provider 已设置
3. 打开文档页，上传一个 `txt`、`md`、`pdf` 或 `docx`
4. 等文档状态变成 `可用`
5. 打开问答页，创建一个新会话
6. 发送一个和文档内容直接相关的问题
7. 确认回答能返回，且来源面板能展开查看片段

## 文档入口

- 总体优化建议：[docs/optimization.md](/d:/documentD/works/AgenticEngineering/FileManagement/docs/optimization.md)
- 测试说明：[docs/test.md](/d:/documentD/works/AgenticEngineering/FileManagement/docs/test.md)
- 产品需求：[docs/prd.md](/d:/documentD/works/AgenticEngineering/FileManagement/docs/prd.md)
- 技术方案：[docs/tech.md](/d:/documentD/works/AgenticEngineering/FileManagement/docs/tech.md)
- 后端说明：[backend/README.md](/d:/documentD/works/AgenticEngineering/FileManagement/backend/README.md)
- 前端说明：[frontend/README.md](/d:/documentD/works/AgenticEngineering/FileManagement/frontend/README.md)

## 常用命令

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
docker compose down
python scripts/verify_stack.py
```
