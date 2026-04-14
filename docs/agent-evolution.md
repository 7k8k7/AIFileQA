# Agent 演进设计方案

## 1. 现状与问题

### 1.1 当前管道结构

系统目前采用固定的 RAG 管道，执行流程如下：

```
用户问题
  → [代码] 根据 scope_type 过滤文档
  → [代码] 生成查询向量，执行混合检索（Top-K）
  → [代码] 拼装系统 Prompt（检索结果 + 对话历史）
  → LLM（被动接收，生成回答）
  → SSE 流式输出
```

核心入口：`backend/app/api/chat.py`，调用链为 `build_rag_prompt()` → `stream_chat_completion()`。

### 1.2 核心限制

1. **检索策略由代码写死**：查询词直接使用用户原始问题，检索 Top-K 固定，LLM 无法决定要检索什么、检索几次、用什么关键词。

2. **单次 LLM 调用，无法补充信息**：检索结果不充分时，LLM 只能在有限上下文中"凑答案"，而无法触发第二次检索。

3. **LLM 无法感知自身回答质量**：回答生成后直接输出，不存在评估和重试机制；用户只能手动点击"重新生成"。

---

## 2. 演进目标

将系统从固定 RAG 管道演进为具备自主决策能力的 Agent，使 LLM 能够：

- 自主决定是否检索、检索什么内容（工具调用）
- 多轮推理，在信息不足时继续行动（ReAct 循环）
- 将复杂问题拆解为子任务分步执行（规划）
- 对自身输出打分并在必要时重试（自我反思）

---

## 3. Stage 1：工具调用（Function Calling）

### 3.1 目标

让 LLM 从被动接收者变为主动决策者。LLM 决定是否调用工具、调用哪个工具，而不是代码强制执行固定检索步骤。

### 3.2 工具定义

定义三个核心工具，schema 放在新增的 `backend/app/schemas/agent.py` 中：

**工具 1：文档语义搜索**
```python
search_documents(
    query: str,           # LLM 自主构造的搜索词，可与用户原问题不同
    doc_ids: list[str] | None = None,  # 可限定文档范围，None 表示全部
    top_k: int = 5
) -> list[ChunkResult]
```

**工具 2：读取文档片段**
```python
read_document(
    doc_id: str,
    page: int | None = None  # 可选，指定页码；None 表示读取全文摘要
) -> str
```

**工具 3：向用户追问**
```python
request_clarification(
    question: str  # LLM 认为问题不明确时，主动向用户发起追问
) -> str
```

### 3.3 流程变化

```
用户问题
  → LLM（携带工具列表）
  → LLM 返回 tool_call：search_documents("关键词", doc_ids=[...])
  → [代码] 执行 retrieve_chunks()，返回检索结果
  → 将结果作为 tool 消息追加到上下文
  → LLM 基于检索结果生成最终回答
```

### 3.4 关键代码改动

**`backend/app/services/llm_service.py`**
- `stream_chat_completion()` 增加 `tools: list[dict] | None = None` 参数
- 若 `tools` 不为空，向 OpenAI/Claude API 传递 `tools` 字段
- 非流式模式新增 `call_with_tools()` 函数，用于工具调用阶段的非流式调用

**`backend/app/api/chat.py`**
- `send_message` 端点检测 LLM 响应中是否存在 `tool_calls`
- 若存在，将 `tool_call` 分发到对应的服务函数执行，并将结果拼入消息历史
- 注意：Claude API 的工具调用格式（`tool_use` block）与 OpenAI 不同，需在 `llm_service.py` 中统一适配

**`backend/app/services/retrieval_service.py`**
- `retrieve_chunks()` 保持原有接口不变
- 新增包装函数 `tool_search_documents(query, doc_ids, top_k)` → 返回可序列化的 JSON 结构，供 `chat.py` 在工具调用时直接使用

### 3.5 SSE 事件扩展

| 事件类型 | 示例 payload | 说明 |
|------|------|------|
| `tool_call` | `{"type":"tool_call","name":"search_documents","args":{...}}` | 通知前端 LLM 正在调用工具 |
| `tool_result` | `{"type":"tool_result","name":"search_documents","count":5}` | 工具执行完成，返回摘要信息 |

---

## 4. Stage 2：ReAct 推理循环

### 4.1 目标

单次工具调用不足以处理信息不足的情况。ReAct 循环让 LLM 进入"推理 → 行动 → 观察"的迭代过程，直到信息充分再输出最终答案。

### 4.2 循环逻辑

```
Round 1:
  Thought: 需要先查找 X
  Action:  search_documents("X")
  Observation: [检索结果]

Round 2:
  Thought: 结果不够，需要补充 Y
  Action:  search_documents("Y")
  Observation: [检索结果]

Round 3:
  Thought: 信息已充分
  Final Answer: 综合回答
```

### 4.3 关键设计结论

- **最大迭代次数**：`MAX_ITERATIONS = 5`，超出时强制终止并输出当前已有信息的回答
- **停止条件**：LLM 返回不含 `tool_calls` 的普通文本消息
- **上下文管理**：每轮的 `tool_call` + `tool_result` 消息均追加到消息历史中，保证 LLM 始终能看到完整推理链
- **超时保护**：单轮工具执行超过 30 秒时，以错误结果继续，不阻塞循环

### 4.4 新增模块

新增 `backend/app/services/agent_runner.py`，封装核心循环：

```python
async def run(
    provider: ProviderConfig,
    messages: list[ChatMessage],
    user_content: str,
    tools: list[dict],
    db: AsyncSession,
    session: ChatSession,
) -> AsyncGenerator[str, None]:
    """
    ReAct 循环主入口。
    每轮：调用 LLM → 检测 tool_calls → 执行工具 → 追加结果 → 继续
    无 tool_calls 时，流式输出最终答案并退出循环。
    """
```

### 4.5 关键代码改动

**`backend/app/api/chat.py`**
- `send_message` 中的 LLM 调用替换为 `agent_runner.run()`
- 原有的单次 `stream_chat_completion()` 调用只在 Stage 1 之前的降级路径中保留

**`backend/app/services/llm_service.py`**
- 新增 `call_once_with_tools()` 非流式接口，供 `agent_runner.py` 在每轮循环中同步等待 LLM 决策
- 保留原有 `stream_chat_completion()` 仅用于最终答案的流式输出

### 4.6 SSE 事件扩展

| 事件类型 | 示例 payload | 说明 |
|------|------|------|
| `thought` | `{"type":"thought","content":"需要先查找...","round":1}` | LLM 每轮推理内容（可选，用于调试/展示） |
| `token` | `{"type":"token","content":"根据文档..."}` | 最终答案流式 token（原有，不变） |
| `done` | `{"type":"done","message_id":"...","rounds":3}` | 完成，附带实际执行轮数 |

---

## 5. Stage 3：规划与任务分解

### 5.1 适用场景

用户问题涉及多个独立子问题，或需要跨多个文档比较、汇总。例如：

- "比较文档 A 和文档 B 对同一主题的不同观点"
- "分析这三份报告的共同结论，并指出分歧"
- "先总结第一章，再回答我关于第三章的问题"

单纯的 ReAct 循环在这类场景下可能产生遗漏或顺序混乱，规划模块将问题先结构化再执行。

### 5.2 触发条件

在 `agent_runner.py` 中判断是否启用规划，满足以下任一条件触发：

- 用户问题字符数 > 50
- 问题中包含关键词：`比较`、`对比`、`分析`、`总结所有`、`分别`、`各个`

### 5.3 规划 Prompt 设计

规划阶段使用独立的系统 Prompt，要求 LLM 以 JSON 输出执行计划：

```
你是一个任务规划器。请将用户的问题分解为若干个可独立执行的子任务。
每个子任务应对应一次文档检索或一次综合汇总。
输出格式：
{
  "tasks": [
    {"id": 1, "goal": "在文档A中查找关于X的内容", "tool": "search_documents", "args": {"query": "X"}},
    {"id": 2, "goal": "在文档B中查找关于X的内容", "tool": "search_documents", "args": {"query": "X"}},
    {"id": 3, "goal": "综合上述检索结果，对比两文档的观点", "tool": null}
  ]
}
```

### 5.4 执行模式

- **简单问题**（未触发规划）：直接进入 Stage 2 的 ReAct 循环
- **复杂问题**（触发规划）：
  1. 调用 LLM 生成计划（非流式，等待完整 JSON）
  2. 按计划顺序执行每个有 `tool` 的任务，收集结果
  3. 将所有结果作为上下文，调用 LLM 执行汇总任务（`tool: null`）
  4. 汇总结果流式输出

### 5.5 关键代码改动

**`backend/app/services/agent_runner.py`**
- `run()` 入口增加 `use_planner: bool` 参数
- 新增 `_plan(user_content, tools)` 内部函数，调用 LLM 生成计划 JSON
- 新增 `_execute_plan(plan, db, session)` 内部函数，逐步执行计划并汇总

**`backend/app/schemas/agent.py`**
- 新增 `PlanTask` 和 `ExecutionPlan` Pydantic 模型，用于校验 LLM 输出的计划结构

---

## 6. Stage 4：自我反思与评估

### 6.1 目标

在生成最终答案后，LLM 对自身输出质量进行评估。若回答不完整或存在明显缺失，自动触发一次补充检索并重新生成。

### 6.2 评估流程

```
Final Answer 生成完毕
  → 发起第二次 LLM 调用（非流式）
  → 评估 Prompt：对刚才的回答打分（1-5）
  → 若分数 ≤ 2：追加检索，重新生成
  → 若分数 > 2：直接返回，结束
```

最多重试 **1 次**，避免循环放大延迟。

### 6.3 评估 Prompt 设计

```
以下是用户的问题和你刚才生成的回答，请评估回答质量：

[用户问题]：{user_question}

[你的回答]：{answer}

[参考文档片段]：{retrieved_chunks}

请以 JSON 格式输出评估结果：
{
  "score": 3,          // 1-5 分，5 分最好
  "reason": "回答遗漏了...",
  "missing": "需要补充关于X的信息"
}
```

### 6.4 重试逻辑

- 分数 ≤ 2：以 `reason` + `missing` 作为新的检索线索，调用 `search_documents`，将补充内容加入上下文，重新生成回答
- 分数 > 2：直接输出，不重试

### 6.5 关键代码改动

**`backend/app/services/agent_runner.py`**
- `run()` 新增 `enable_reflection: bool = False` 参数（默认关闭，可通过配置开启）
- 新增 `_reflect(question, answer, chunks)` 内部函数，返回 `ReflectionResult`（score, reason, missing）

**`backend/app/schemas/agent.py`**
- 新增 `ReflectionResult` Pydantic 模型

### 6.6 SSE 事件扩展

| 事件类型 | 示例 payload | 说明 |
|------|------|------|
| `reflection` | `{"type":"reflection","score":2,"retry":true,"reason":"遗漏了X"}` | 反思结果，前端可据此显示"正在补充信息..." |

---

## 7. 实现优先级与依赖关系

```
Stage 1（工具调用）
    ↓  [Stage 1 是基础，必须先完成]
Stage 2（ReAct 循环）
    ↓  [Stage 2 完成后，以下两个可并行]
Stage 4（自我反思）     Stage 3（规划与任务分解）
```

**理由：**
- Stage 1 为其他所有阶段的基础，LLM 没有工具调用能力，ReAct 和规划无从实现
- Stage 4（反思）依赖 Stage 2 的最终答案，但改动量小，可优先于 Stage 3 实现
- Stage 3（规划）逻辑最复杂，Prompt 调优成本高，放在最后

---

## 8. 关键代码改动点汇总

| 文件 | 改动类型 | 核心改动内容 |
|------|------|------|
| `backend/app/api/chat.py` | 修改 | `send_message` 调用 `agent_runner.run()` 替换原有单次调用链 |
| `backend/app/services/llm_service.py` | 修改 | `stream_chat_completion` 增加 `tools` 参数；新增 `call_once_with_tools()` 非流式接口 |
| `backend/app/services/retrieval_service.py` | 修改 | 新增 `tool_search_documents()` 包装函数，返回可序列化 JSON |
| `backend/app/services/agent_runner.py` | **新建** | ReAct 主循环、规划执行、反思逻辑 |
| `backend/app/schemas/agent.py` | **新建** | 工具 schema、`PlanTask`、`ExecutionPlan`、`ReflectionResult` |
| SSE 协议（前后端） | 扩展 | 新增 `tool_call`、`tool_result`、`thought`、`reflection` 事件类型 |

### SSE 协议完整事件类型（演进后）

| 事件类型 | 阶段引入 | 说明 |
|------|------|------|
| `sources` | 原有 | 检索来源片段 |
| `token` | 原有 | 最终答案流式 token |
| `done` | 原有（扩展） | 完成，新增 `rounds` 字段 |
| `error` | 原有 | 错误信息 |
| `tool_call` | Stage 1 | LLM 发起工具调用 |
| `tool_result` | Stage 1 | 工具执行完成摘要 |
| `thought` | Stage 2 | LLM 每轮推理内容 |
| `reflection` | Stage 4 | 反思评分与重试状态 |
