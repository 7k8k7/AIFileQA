# 部署与验收说明

## 1. 文档目标

本文档用于给出本项目最短的启动路径、健康检查路径和手工验收路径，方便本地开发、Docker 演示和交付验收时快速确认系统状态。

## 2. Docker 部署

### 2.1 启动

在项目根目录执行：

```bash
docker compose up -d --build
```

启动后默认地址：

- 前端：`http://localhost:8080`
- 后端：`http://localhost:8000`
- 后端文档：`http://localhost:8000/docs`

如需接入非 OpenAI 兼容的本地模型（如 HuggingFace TGI），还可启动 adapter-proxy：

```bash
# 1. 配置适配器
cp adapter-proxy/config.example.yaml adapter-proxy/config.yaml
# 2. 取消 docker-compose.yml 中 adapter-proxy 的注释，然后：
docker compose up -d adapter-proxy
```

说明：

- `adapter-proxy/config.example.yaml` 默认按 Docker 场景填写成 `host.docker.internal`
- 如果代理本地直接运行，可把目标模型地址改成 `localhost`
- Linux 下如果代理容器要访问宿主机服务，请把 `docker-compose.yml` 里 `extra_hosts` 一起取消注释

启动后在 DocQA 设置页添加 `OpenAI 兼容` provider：

- 这里填的是 DocQA 后端访问代理的地址，不是浏览器地址
- 如果 DocQA 后端和 `adapter-proxy` 都在同一个 Compose 网络里，Base URL 填 `http://adapter-proxy:11435`
- 如果 DocQA 后端和 `adapter-proxy` 都是本地进程，Base URL 填 `http://localhost:11435`

### 2.2 查看状态

```bash
docker compose ps
```

说明：

- `backend` 和 `frontend` 都应处于运行状态
- Compose 已补充健康检查，前端会等待后端健康后再启动

### 2.3 查看日志

```bash
docker compose logs -f
```

### 2.4 停止

```bash
docker compose down
```

## 3. 本地开发部署

### 3.1 启动后端

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

说明：

- 后端环境变量现在统一使用 `DOCQA_` 前缀
- 如果你本机、CI 或部署平台还保留旧变量名 `DEBUG`、`DATABASE_URL`、`PROVIDER_SECRET_KEY`，请改成 `DOCQA_DEBUG`、`DOCQA_DATABASE_URL`、`DOCQA_PROVIDER_SECRET_KEY`
- 本地可直接使用 `backend/.env` 或从 `backend/.env.example` 复制生成

### 3.2 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

默认地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

## 4. 部署自检

### 4.1 宿主机有 Python 时

项目根目录已提供一个部署自检脚本：

```bash
python scripts/verify_stack.py
```

这条命令依赖宿主机 Python 3，本身不是在容器里跑。

默认检查 Docker 场景下的：

1. 后端 `/health`
2. 前端首页 `/`
3. 前端代理 `/health`
4. 前端代理 `/api/providers`

如果你在本地开发模式下运行前后端，可执行：

```bash
python scripts/verify_stack.py --frontend-url http://localhost:5173 --backend-url http://localhost:8000
```

### 4.2 宿主机没 Python 时

如果当前机器只装了 Docker，也可以直接用容器内命令完成验收：

| 检查项 | 命令或动作 | 期望结果 |
| --- | --- | --- |
| 服务状态 | `docker compose ps` | `backend` 和 `frontend` 都是 `Up`，最好带 `healthy` |
| 后端健康 | `docker compose exec backend python -c "import json, urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')))"` | 输出里包含 `status: ok` |
| 前端代理健康 | `docker compose exec frontend wget -qO- http://127.0.0.1/health` | 返回 `{"status":"ok","app":"DocQA"}` |
| 前端代理 API | `docker compose exec frontend wget -qO- http://127.0.0.1/api/providers` | 返回 `[]` 或 provider 列表 JSON |
| 前端首页 | 浏览器打开 `http://localhost:8080` | 页面能正常打开，不是空白页或 502 |

## 5. 最短手工验收路径

推荐按以下顺序手工验收：

1. 打开设置页，创建一个 provider
2. 点击测试连接，确认连接成功
3. 上传一个文档，确认状态变为 `可用`
4. 创建一个问答会话
5. 提一个和文档内容直接相关的问题
6. 确认回答正常返回
7. 确认来源面板可展开查看引用片段

## 6. 验收结果判断

可视为部署成功的最低标准：

- 前端可打开
- 后端健康检查正常
- 前端代理 API 可正常转发
- 文档上传成功
- provider 测试连接成功
- 聊天回答和来源面板可正常工作

## 7. 常见问题

| 问题 | 原因 | 处理方式 |
| --- | --- | --- |
| 前端能打开，但接口 404 | 前端未通过 `/api` 代理访问后端 | 检查 Vite 代理或 nginx 反向代理配置 |
| 后端启动失败 | 数据库迁移未执行或环境变量不完整 | 先执行 `alembic upgrade head`，再检查 `.env` |
| provider 测试失败 | Base URL、API Key、模型名或网络不可达 | 到设置页重新核对配置 |
| adapter-proxy 连接失败 | 代理未启动或 config.yaml 配置有误 | 检查代理是否运行，确认 config.yaml 中 base_url 可达 |
| 聊天返回但没有来源 | 当前未命中文档片段，或检索退回关键词仍未命中 | 检查文档内容、提问方式和文档状态 |
