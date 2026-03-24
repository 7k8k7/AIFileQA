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

### 3.2 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

默认地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

## 4. 一键自检

项目根目录已提供一个部署自检脚本：

```bash
python scripts/verify_stack.py
```

默认检查 Docker 场景下的：

1. 后端 `/health`
2. 前端首页 `/`
3. 前端代理 `/health`
4. 前端代理 `/api/providers`

如果你在本地开发模式下运行前后端，可执行：

```bash
python scripts/verify_stack.py --frontend-url http://localhost:5173 --backend-url http://localhost:8000
```

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
| 聊天返回但没有来源 | 当前未命中文档片段，或检索退回关键词仍未命中 | 检查文档内容、提问方式和文档状态 |
