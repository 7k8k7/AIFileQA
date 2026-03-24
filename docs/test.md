# Plan: 补充单元测试覆盖

## Context

对项目需求规格进行全面审计后，功能需求已全部完成，非功能需求中 Docker 和文档也已到位。**唯一缺口是单元测试**：

| 需求项 | 状态 |
|---|---|
| 文档管理（TXT/MD/PDF/Word） | ✅ 完成 |
| AI 问答（多轮/RAG/SSE 流式） | ✅ 完成 |
| Provider 配置（OpenAI/Claude/兼容） | ✅ 完成 |
| 前端三页面 | ✅ 完成 |
| Docker 镜像 | ✅ docker-compose + 双 Dockerfile |
| 文档（PRD/技术设计/README） | ✅ 完成 |
| **单元测试** | ❌ 后端仅 1 个集成测试文件；前端零测试 |

### 当前测试现状

- **后端**: `backend/tests/test_full_flow_api.py` — 7 个集成测试（全流程、provider 选择、API key 掩码等）。pytest + pytest-asyncio 已安装。
- **前端**: 无测试框架、无测试文件、package.json 无 test 脚本。

## 策略

优先后端单元测试（业务逻辑密集），再补前端测试（Vitest，覆盖核心 store 和 service）。

---

## Step 1: 后端 — 服务层单元测试

为 5 个核心 service 编写单元测试，用 mock 隔离外部依赖（DB、HTTP、ChromaDB）。

### 1.1 `test_parser_service.py`

**文件**: `backend/tests/test_parser_service.py`
**被测**: `backend/app/services/parser_service.py`

| 测试用例 | 说明 |
|---|---|
| `test_extract_text_utf8` | TXT 文件正确读取 UTF-8 内容 |
| `test_extract_markdown` | MD 文件按文本提取 |
| `test_chunk_splitting_size` | 500 字切片、50 字重叠 |
| `test_chunk_preserves_page_no` | PDF 切片保留页码信息 |
| `test_empty_document_returns_empty` | 空文件返回空列表 |
| `test_parse_document_dispatches_by_ext` | 根据扩展名选择正确 extractor |

### 1.2 `test_retrieval_service.py`

**文件**: `backend/tests/test_retrieval_service.py`
**被测**: `backend/app/services/retrieval_service.py`

| 测试用例 | 说明 |
|---|---|
| `test_keyword_retrieve_scores_by_frequency` | 关键词频率排序正确 |
| `test_keyword_retrieve_fallback_on_no_match` | 无匹配时返回前 top_k 个 chunk |
| `test_keyword_chinese_segmentation` | 中文关键词正则分词 |
| `test_get_candidate_doc_ids_scope_all` | scope=all 返回所有可用文档 |
| `test_get_candidate_doc_ids_scope_single` | scope=single 过滤指定文档 |
| `test_build_rag_prompt_with_chunks` | 有 chunk 时生成 RAG prompt |
| `test_build_rag_prompt_no_chunks` | 无 chunk 时返回 NO_CONTEXT |
| `test_retrieve_chunks_vector_then_keyword` | vector 失败后降级 keyword |

### 1.3 `test_embedding_service.py`

**文件**: `backend/tests/test_embedding_service.py`
**被测**: `backend/app/services/embedding_service.py`

| 测试用例 | 说明 |
|---|---|
| `test_can_use_embeddings_openai` | OpenAI provider 返回 True |
| `test_can_use_embeddings_claude` | Claude provider 返回 False |
| `test_get_embedding_model_default` | 默认 embedding model 正确 |
| `test_generate_embeddings_mock_api` | mock HTTP 调用验证返回格式 |
| `test_serialize_deserialize_embedding` | 序列化/反序列化保持精度 |

### 1.4 `test_llm_service.py`

**文件**: `backend/tests/test_llm_service.py`
**被测**: `backend/app/services/llm_service.py`

| 测试用例 | 说明 |
|---|---|
| `test_openai_payload_structure` | OpenAI 请求体含 system message |
| `test_claude_payload_structure` | Claude 请求体用 system 字段 |
| `test_stream_yields_tokens` | mock SSE 流正确 yield token |
| `test_history_formatting` | 历史消息正确转换为 API 格式 |

### 1.5 `test_vector_store_service.py`

**文件**: `backend/tests/test_vector_store_service.py`
**被测**: `backend/app/services/vector_store_service.py`

| 测试用例 | 说明 |
|---|---|
| `test_upsert_and_query` | upsert 后能查询到 |
| `test_delete_document_chunks` | 删除后查不到 |
| `test_find_missing_chunk_ids` | 正确识别缺失 chunk |
| `test_query_filters_by_document_ids` | document_ids 过滤生效 |

---

## Step 2: 后端 — API 层单元测试

### 2.1 `test_api_documents.py`

**文件**: `backend/tests/test_api_documents.py`
**被测**: `backend/app/api/documents.py`

| 测试用例 | 说明 |
|---|---|
| `test_upload_valid_file` | 上传 TXT 返回 201 |
| `test_upload_oversized_file` | 超限返回 413 |
| `test_upload_unsupported_extension` | 不支持格式返回 400 |
| `test_list_documents_pagination` | 分页参数正确 |
| `test_delete_document` | 删除返回 200，文件清理 |

### 2.2 `test_api_providers.py`

**文件**: `backend/tests/test_api_providers.py`
**被测**: `backend/app/api/providers.py`

| 测试用例 | 说明 |
|---|---|
| `test_create_provider` | 创建返回完整配置 |
| `test_list_providers_masks_key` | 列表接口 API key 已掩码 |
| `test_detail_returns_full_key` | 详情接口返回真实 key |
| `test_update_preserves_key_when_empty` | 空 key 更新不覆盖 |
| `test_set_default_provider` | 设为默认，旧默认取消 |
| `test_delete_provider` | 删除成功 |

### 2.3 `test_api_chat.py`

**文件**: `backend/tests/test_api_chat.py`
**被测**: `backend/app/api/chat.py`

| 测试用例 | 说明 |
|---|---|
| `test_create_session` | 创建会话返回 id |
| `test_send_message_sse_format` | SSE 流包含 sources → tokens → done |
| `test_regenerate_message` | 重新生成覆盖旧回复 |
| `test_delete_session` | 删除会话及其消息 |

---

## Step 3: 后端 — conftest.py

**文件**: `backend/tests/conftest.py`

共享 fixtures：
- `db` — 内存 SQLite async session（每个测试自动回滚）
- `client` — `httpx.AsyncClient` 绑定 FastAPI app
- `mock_provider` — 预创建 OpenAI provider
- `sample_document` — 预创建测试文档 + chunks

---

## Step 4: 前端 — 安装 Vitest + 配置

```bash
pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

**文件**: `frontend/vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
});
```

**文件**: `frontend/src/test/setup.ts` — import `@testing-library/jest-dom`

**package.json** 添加 `"test": "vitest run"`, `"test:watch": "vitest"`

---

## Step 5: 前端 — Store 测试

### 5.1 `chatStore.test.ts`

**文件**: `frontend/src/stores/__tests__/chatStore.test.ts`

| 测试用例 | 说明 |
|---|---|
| `startStreaming sets isStreaming` | 流式状态切换 |
| `appendStreamingContent accumulates text` | 流式内容累加 |
| `setStreamingSources stores sources` | 来源数据存储 |
| `stopStreaming preserves sources` | 停止流式后来源保留 |
| `addOptimisticUserMessage creates temp entry` | 乐观消息创建 |
| `commitOptimisticUserMessage replaces temp` | 确认后替换临时 ID |

---

## Step 6: 前端 — Service 测试

### 6.1 `api.test.ts`

**文件**: `frontend/src/services/__tests__/api.test.ts`

| 测试用例 | 说明 |
|---|---|
| `fetchDocuments calls correct endpoint` | 文档列表请求正确 |
| `uploadDocument sends FormData` | 上传用 multipart |
| `deleteDocument sends DELETE` | 删除请求方法正确 |

### 6.2 `chat.test.ts`

**文件**: `frontend/src/services/__tests__/chat.test.ts`

| 测试用例 | 说明 |
|---|---|
| `sendMessage posts to correct URL` | 消息发送 URL 正确 |
| `SSE parser handles sources event` | sources 事件触发回调 |
| `SSE parser handles token event` | token 事件触发回调 |

---

## 执行顺序

| 序号 | 内容 | 预估工作量 |
|---|---|---|
| 1 | Step 3: conftest.py | 小 |
| 2 | Step 1: 后端服务层测试（5 个文件） | 中 |
| 3 | Step 2: 后端 API 层测试（3 个文件） | 中 |
| 4 | Step 4: 前端 Vitest 配置 | 小 |
| 5 | Step 5 + 6: 前端 Store + Service 测试 | 中 |

## 验证

1. `cd backend && python -m pytest tests/ -v` — 所有后端测试通过
2. `cd frontend && pnpm test` — 所有前端测试通过
3. 现有集成测试 `test_full_flow_api.py` 仍然通过（不回归）
