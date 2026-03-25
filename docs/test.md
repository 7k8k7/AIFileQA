# 测试说明

## 测试现状

当前项目已经接入前后端测试。

| 模块 | 测试工具 | 现状 |
|---|---|---|
| 后端 | `pytest` | 已有 API、service、任务流程、安全、可观测性、全流程测试 |
| 前端 | `vitest` | 已有 service 和 store 测试，支持 `jsdom` 环境 |
| adapter-proxy | `pytest` | 已有主接口、配置加载、generic 适配器、TGI 适配器测试 |

## 后端测试

### 运行命令

```bash
cd backend
python -m pytest tests/ -v
```

### 关键入口

- `backend/tests/conftest.py`
- `backend/tests/test_api_chat.py`
- `backend/tests/test_api_documents.py`
- `backend/tests/test_api_providers.py`
- `backend/tests/test_embedding_service.py`
- `backend/tests/test_full_flow_api.py`
- `backend/tests/test_llm_service.py`
- `backend/tests/test_observability.py`
- `backend/tests/test_parser_service.py`
- `backend/tests/test_parsing_jobs.py`
- `backend/tests/test_retrieval_service.py`
- `backend/tests/test_security.py`
- `backend/tests/test_vector_store_service.py`

### 已覆盖内容

| 类别 | 说明 |
|---|---|
| API | 文档、Provider、问答接口的主要行为 |
| Service | 解析、检索、Embedding、LLM、向量存储等核心逻辑 |
| 后台任务 | 文档解析任务与相关状态流转 |
| 安全 | 关键安全逻辑的基础校验 |
| 可观测性 | 基础日志与观测行为 |
| 全流程 | 从配置到上传、问答的主要链路 |

## 前端测试

### 运行命令

```bash
cd frontend
pnpm test
```

本地开发时也可以使用：

```bash
cd frontend
pnpm test:watch
```

### 关键入口

- `frontend/vitest.config.ts`
- `frontend/src/test/setup.ts`
- `frontend/src/services/__tests__/api.test.ts`
- `frontend/src/services/__tests__/chat.test.ts`
- `frontend/src/stores/__tests__/chatStore.test.ts`

### 已覆盖内容

| 类别 | 说明 |
|---|---|
| Service | API 请求封装、聊天相关调用 |
| Store | 聊天流式状态、消息状态管理 |
| 测试环境 | 使用 `jsdom`，并加载 `@testing-library/jest-dom` |

## Adapter Proxy 测试

### 运行命令

```bash
cd adapter-proxy
pip install -r requirements-dev.txt
pytest -q
```

### 关键入口

- `adapter-proxy/tests/test_main.py`
- `adapter-proxy/tests/test_generic_adapter.py`
- `adapter-proxy/tests/test_huggingface_adapter.py`
- `adapter-proxy/tests/test_config.py`

### 已覆盖内容

| 类别 | 说明 |
|---|---|
| 主接口 | `/health`、`/v1/models`、`/v1/chat/completions` 的普通和流式返回 |
| 配置加载 | 合法配置加载、未知类型跳过、缺字段跳过 |
| Generic 适配器 | 请求模板渲染、JSON 响应提取、流式解析、非流式回退 |
| TGI 适配器 | `/generate`、`/generate_stream`、`/info` 失败降级 |

## 推荐验证方式

| 步骤 | 命令 |
|---|---|
| 后端测试 | `cd backend && python -m pytest tests/ -v` |
| 前端测试 | `cd frontend && pnpm test` |
| adapter-proxy 测试 | `cd adapter-proxy && pip install -r requirements-dev.txt && pytest -q` |
| 联调验收 | `python scripts/verify_stack.py` |

如果要做完整验收，建议再走一遍下面这条手工链路：

1. 在系统设置页新增一个可用 provider，并测试连接。
2. 在文档页上传一个 `txt`、`md`、`pdf` 或 `docx` 文件。
3. 等文档状态变成可用。
4. 在问答页创建新会话并提一个和文档内容直接相关的问题。
5. 确认回答正常返回，且来源面板能看到引用片段。

## 当前边界

| 项目 | 说明 |
|---|---|
| 前端覆盖范围 | 目前主要覆盖 service 和 store，页面交互测试还不多 |
| adapter-proxy 能力边界 | 当前只覆盖聊天和模型列表，不覆盖 `/v1/embeddings` |
| adapter-proxy 适配范围 | `generic` 目前只适合 `POST` + JSON 的 HTTP 接口，不是任意 REST API |
| 验证方式 | 复杂链路仍然建议配合 `verify_stack.py` 和手工验收一起看 |
| 文档维护原则 | 后续新增测试文件或测试命令时，需要同步更新本页 |
