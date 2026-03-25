# DocQA

智能文档问答助手，包含：

- 文档管理：上传、查询、删除、状态跟踪
- Agent 问答：多轮对话、来源展示、重新生成
- 系统设置：OpenAI、Claude、本地兼容模型配置
- 适配代理：接入非 OpenAI 兼容接口的本地模型（HuggingFace TGI、自定义 API 等）

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

## 接入非兼容接口的本地模型

如果你的本地模型不提供 OpenAI 兼容接口（如 HuggingFace TGI、自建推理服务），可以通过 adapter-proxy 翻译成 OpenAI 格式：

```bash
# 1. 配置适配器
cp adapter-proxy/config.example.yaml adapter-proxy/config.yaml
# 编辑 config.yaml，填入模型服务地址

# 2. 启动代理（二选一）
# 独立运行：
cd adapter-proxy && pip install -r requirements.txt && uvicorn main:app --port 11435
# 或 Docker Compose（取消 docker-compose.yml 中 adapter-proxy 的注释）：
docker compose up -d adapter-proxy

# 3. 在 DocQA 设置页添加 OpenAI 兼容 provider
#    Base URL: http://localhost:11435（本地）或 http://adapter-proxy:11435（Docker）
#    模型名: config.yaml 中的 model_name
#    API Key: 留空
#    注意: 当前代理只覆盖聊天和模型列表，不覆盖 embedding
```

内置适配器：`huggingface_tgi`（HuggingFace TGI）、`generic`（HTTP JSON + Jinja2 模板配置）。
建议在 DocQA 里先把 Embedding 关掉，先验证聊天链路。
详见 [adapter-proxy/README.md](adapter-proxy/README.md)。

## 文档入口
- 测试说明：[docs/test.md](/docs/test.md)
- 产品需求：[docs/prd.md](/docs/prd.md)
- 技术方案：[docs/tech.md](/docs/tech.md)
- 后端说明：[backend/README.md](backend/README.md)
- 前端说明：[frontend/README.md](/frontend/README.md)
- 适配代理：[adapter-proxy/README.md](adapter-proxy/README.md)

## 常用命令

```bash
docker compose up -d --build          # 启动主服务
docker compose up -d adapter-proxy    # 启动适配代理（需先配置）
cd adapter-proxy && pip install -r requirements-dev.txt && pytest -q
docker compose ps
docker compose logs -f
docker compose down
python scripts/verify_stack.py
```
