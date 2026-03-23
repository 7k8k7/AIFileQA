# 智能文档问答助手技术方案

## 1. 文档目标与设计原则

### 1.1 文档目标

本文档用于说明“智能文档问答助手”的技术实现方案，作为研发实现、接口设计、测试设计和部署交付的统一依据。

本文档必须满足以下目标：

1. 完整覆盖 [prd.md](D:/documentD/works/AgenticEngineering/FileManagement/docs/prd.md) 中定义的 MVP 范围。
2. 对关键技术决策给出明确结论，避免实现阶段再次进行高成本讨论。
3. 为前端、后端、测试和部署提供统一的实现边界。
4. 支撑项目以 React + TypeScript + FastAPI + PostgreSQL + pgvector + Docker / Docker Compose 方案落地。

### 1.2 设计原则

1. 以可运行、可演示、可验收为第一优先级。
2. 以最少依赖满足主交付范围，不引入消息队列、对象存储、Redis、OCR 等额外基础设施。
3. 所有问答结果优先基于已上传文档内容，减少脱离文档事实的生成。
4. 架构上预留扩展能力，但不为未来复杂场景过度设计。
5. 失败路径必须可观测、可提示、可恢复。

## 2. 总体架构

### 2.1 架构概览

系统采用前后端分离架构，由以下部分组成：

1. 前端 Web 应用：React + TypeScript 单页应用，负责三大页面和用户交互。
2. 后端 API 服务：FastAPI 提供 REST API，负责文档管理、问答、会话和配置管理。
3. PostgreSQL：保存业务数据、任务状态和向量索引。
4. 本地文件存储：保存原始上传文档，挂载 Docker volume。
5. 外部 AI Provider：OpenAI、Claude、兼容 OpenAI API 的本地模型服务。

### 2.2 逻辑架构

系统逻辑分层如下：

1. 表现层：前端页面、表单、列表、消息流、状态反馈。
2. 接口层：FastAPI 路由、请求校验、统一响应和错误处理。
3. 应用层：文档服务、问答服务、Provider 服务、任务调度服务。
4. 领域层：文档对象、会话对象、消息对象、Provider 配置对象、任务对象。
5. 基础设施层：文件存储、数据库访问、Embedding 调用、LLM 调用、文档解析器。

### 2.3 关键技术结论

1. 前端固定采用 React + TypeScript，不提供 Vue 替代方案。
2. 后端固定采用 FastAPI + REST API，不引入 GraphQL。
3. 文档原文件固定存储在本地文件系统，通过 Docker volume 持久化。
4. 文档解析、切片、Embedding、索引构建采用应用内异步任务，使用 `concurrent.futures.ProcessPoolExecutor` 在独立进程中执行 CPU 密集型解析，避免阻塞主事件循环。不单独引入 Worker 和消息队列。
5. 检索方式采用 PostgreSQL + pgvector（HNSW 索引），问答链路采用”文档过滤 + 向量召回 + 上下文拼装 + LLM 生成”。
6. Embedding 服务独立于 LLM Provider，统一使用 OpenAI Embedding API（text-embedding-3-small，1536 维），确保向量空间一致性。
7. 问答响应采用 SSE（Server-Sent Events）流式输出，前端逐字渲染。

## 3. 模块划分与职责

### 3.1 前端模块

#### 文档管理模块

负责上传文档、展示文档列表、按名称搜索、查看文档基础信息、执行删除操作、展示解析状态。

#### Agent 问答模块

负责创建会话、输入问题、选择问答范围、展示多轮对话消息流（支持 Markdown 渲染，使用 react-markdown + rehype-sanitize）、SSE 流式逐字渲染、会话历史侧栏（列表、切换、删除）、展示加载态和异常态。

#### 系统配置模块

负责新增或修改 Provider 配置、测试连通性、切换默认 Provider、展示配置保存结果。

### 3.2 后端模块

#### 文档管理服务

负责文件接收、格式校验、元数据入库、文件落盘、删除文档、查询文档列表和详情。

#### 文档解析服务

负责根据文件类型提取文本内容，对文本进行清洗、切片、Embedding 生成，并写入向量索引。

#### 问答服务

负责根据用户选择的范围召回相关文档切片，结合当前会话上下文拼装 Prompt，并调用 LLM 生成答案。

#### 会话服务

负责创建会话、记录消息、读取历史消息、保存会话级 Provider 快照。

#### Provider 配置服务

负责维护 OpenAI、Claude 和兼容 OpenAI API 的本地模型配置，测试配置是否可用，并管理默认 Provider。

#### 任务调度服务

负责驱动异步解析任务执行，维护任务状态、错误信息和重试次数。

## 4. 核心业务流程

### 4.1 文档上传与解析流程

1. 前端选择文件并提交到上传接口。
2. 后端校验扩展名和基础大小限制。
3. 后端生成文档记录，状态初始化为 `上传成功`。
4. 后端将原文件落盘到本地存储目录。
5. 后端创建解析任务，文档状态更新为 `解析中`。
6. 异步任务读取文件并按类型执行解析。
7. 解析成功后生成切片、向量并写入数据库，文档状态更新为 `可用`。
8. 解析失败时记录错误信息，文档状态更新为 `解析失败`。

### 4.2 问答流程

1. 用户进入问答页，新建会话或选择已有会话。
2. 系统创建会话时写入当前默认 Provider 快照。
3. 用户选择“全部文档”或“单个文档”范围并输入问题。
4. 后端根据会话范围过滤可用文档。
5. 后端对问题生成查询向量并从文档切片中进行 Top-K 召回。
6. 后端将召回结果与最近若干轮会话消息拼装为模型上下文。
7. LLM 生成答案，若召回为空则返回“未在文档中找到依据”。
8. 用户问题和系统回答均写入消息表。

### 4.3 Provider 配置流程

1. 管理员在系统配置页填写 Provider 信息。
2. 前端提交配置内容到后端。
3. 后端执行字段校验。
4. 管理员可调用测试连接接口验证配置。
5. 测试成功后方可设置为默认 Provider。
6. 新会话创建时读取默认 Provider 并写入会话快照。

## 5. 数据模型设计

### 5.1 文档对象 `documents`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 文档主键 |
| file_name | varchar | 原始文件名 |
| file_ext | varchar | 文件扩展名 |
| file_size | bigint | 文件大小 |
| storage_path | varchar | 文件存储路径 |
| status | varchar | 上传成功 / 解析中 / 可用 / 解析失败 |
| error_message | text | 解析失败原因 |
| uploaded_at | timestamptz | 上传时间 |
| updated_at | timestamptz | 更新时间 |

### 5.2 文档切片对象 `document_chunks`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 切片主键 |
| document_id | UUID | 所属文档 |
| chunk_index | int | 切片序号 |
| content | text | 切片文本 |
| page_no | int | 页码，TXT/MD 可为空 |
| section_label | varchar | 标题或段落标识 |
| embedding | vector(1536) | pgvector 向量字段，1536 维（text-embedding-3-small） |
| created_at | timestamptz | 创建时间 |

### 5.3 会话对象 `chat_sessions`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 会话主键 |
| title | varchar | 会话标题，根据首次提问自动生成 |
| scope_type | varchar | `all` 或 `single` |
| document_id | UUID | 单文档模式下的文档 ID，可为空 |
| provider_snapshot | jsonb | 会话创建时的 Provider 配置快照 |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

### 5.4 消息对象 `chat_messages`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 消息主键 |
| session_id | UUID | 所属会话 |
| role | varchar | `user` / `assistant` |
| content | text | 消息内容 |
| created_at | timestamptz | 创建时间 |

### 5.5 Provider 配置对象 `provider_configs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 配置主键 |
| provider_type | varchar | `openai` / `claude` / `openai_compatible` |
| base_url | varchar | 接口地址 |
| model_name | varchar | 模型名 |
| api_key | text | 密钥，数据库加密存储 |
| temperature | numeric | 温度 |
| max_tokens | int | 最大 Token |
| timeout_seconds | int | 超时时间 |
| is_default | boolean | 是否默认 Provider |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

### 5.6 任务对象 `jobs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 任务主键 |
| job_type | varchar | `parse_document` |
| target_id | UUID | 关联文档 ID |
| status | varchar | `pending` / `running` / `succeeded` / `failed` |
| retry_count | int | 重试次数 |
| error_message | text | 错误信息 |
| started_at | timestamptz | 开始时间 |
| finished_at | timestamptz | 结束时间 |

## 6. 接口设计

### 6.1 文档接口

#### `POST /api/documents`

用途：上传文档并创建解析任务。  
核心入参：文件。  
核心返回：文档 `id`、文件名、状态、上传时间。  
错误场景：格式不支持、文件为空、文件过大、写盘失败。

#### `GET /api/documents`

用途：查询文档列表。  
核心入参：`keyword`、`page`、`page_size`。  
核心返回：文档列表、分页信息。  
错误场景：分页参数非法。

#### `GET /api/documents/{document_id}`

用途：查询文档详情。  
核心返回：文档元数据、状态、错误信息。  
错误场景：文档不存在。

#### `DELETE /api/documents/{document_id}`

用途：删除文档及其切片索引。  
核心返回：删除结果。  
错误场景：文档不存在、文件删除失败、数据库删除失败。

### 6.2 问答接口

#### `GET /api/chat/sessions`

用途：查询会话列表（会话历史侧栏）。
核心入参：无。
核心返回：会话列表（`id`、`title`、`scope_type`、`created_at`），按创建时间倒序。
错误场景：无。

#### `POST /api/chat/sessions`

用途：创建新会话。
核心入参：`scope_type`、`document_id`。
核心返回：会话 `id`、Provider 快照、创建时间。
错误场景：单文档模式下文档不存在或不可用、默认 Provider 不存在。

#### `DELETE /api/chat/sessions/{session_id}`

用途：删除会话及其所有消息。
核心返回：删除结果。
错误场景：会话不存在。

#### `POST /api/chat/sessions/{session_id}/messages`

用途：发送用户问题并生成流式回答。
核心入参：问题文本。
核心返回：SSE 流（`EventSourceResponse`），事件格式为 `{"type": "token", "content": "..."}` 和 `{"type": "done", "message_id": "..."}`。流结束后用户消息和助手消息均已写入消息表。
错误场景：会话不存在、模型调用失败、没有可用文档、SSE 连接中断。
特殊处理：首次提问时自动生成会话标题（截取问题前 50 字符或由 LLM 生成摘要）。

#### `GET /api/chat/sessions/{session_id}/messages`

用途：获取会话历史。
核心返回：消息列表。
错误场景：会话不存在。

### 6.3 配置接口

#### `GET /api/providers`

用途：查询 Provider 配置列表。  
核心返回：配置列表，密钥字段脱敏。  
错误场景：无。

#### `POST /api/providers`

用途：新增 Provider 配置。  
核心入参：Provider 类型、地址、模型、密钥、温度、Token、超时。  
核心返回：配置对象。  
错误场景：参数不合法、重复配置。

#### `PUT /api/providers/{provider_id}`

用途：更新 Provider 配置。  
核心返回：更新后的配置对象。  
错误场景：配置不存在、参数不合法。

#### `POST /api/providers/{provider_id}/test`

用途：测试当前配置是否可连接。  
核心返回：成功或失败结果。  
错误场景：网络不可达、鉴权失败、模型不存在。

#### `POST /api/providers/{provider_id}/default`

用途：设置默认 Provider。  
核心返回：设置结果。  
错误场景：配置不可用、配置不存在。

### 6.4 健康检查接口

#### `GET /api/health`

用途：检查应用、数据库和基础依赖状态。  
核心返回：服务状态、数据库状态、版本号。  
错误场景：数据库不可达。

## 7. 文档解析与索引方案

### 7.1 文件存储方案

1. 上传文件存储在后端挂载目录，例如 `/app/data/uploads`。
2. Docker Compose 通过 volume 持久化该目录。
3. 数据库存储文件路径和元数据，不直接保存二进制文件内容。

### 7.2 文件解析方案

1. TXT：按 UTF-8 优先读取，必要时做编码兜底。
2. Markdown：提取纯文本内容并保留标题层级信息。
3. PDF：提取可复制文本内容，记录页码信息。
4. DOCX：使用 python-docx 提取段落文本，保留段落顺序。不支持 .doc（旧版 Word 二进制格式）。

### 7.3 切片策略

1. 按固定字符窗口结合段落边界切片，默认切片长度为 500 字符。
2. 相邻切片重叠 100 字符，减少跨段信息丢失。
3. 切片长度控制在适合 Embedding 模型输入的范围（text-embedding-3-small 支持 8191 tokens）。
4. 对 PDF / Word 额外记录页码或段落标签，便于后续引用来源扩展。

### 7.4 异步任务策略

1. 上传请求只负责入库、写盘和创建任务，不阻塞等待全文解析完成。
2. 应用内后台任务每 2 秒轮询 `jobs` 表中待处理任务。
3. 解析任务通过 `asyncio.run_in_executor(ProcessPoolExecutor)` 在独立进程中执行，避免 CPU 密集型解析阻塞主事件循环。
4. 同一文档只允许存在一个活跃解析任务。
5. 失败任务支持有限次数重试（最多 3 次），超过阈值后保持失败状态。
6. 运行超过 5 分钟的任务自动重置为待处理状态，防止停滞任务永久阻塞。
7. 文件大小上限为 50 MB，前后端均需校验。

## 8. 问答与多轮会话方案

### 8.1 检索生成链路

1. 接收问题文本。
2. 基于会话范围筛选文档集合。
3. 将问题转换为查询向量（单条 embedding 调用）。文档解析阶段的切片 embedding 采用批量调用，一次请求提交所有切片以减少 API 延迟和成本。
4. 在 `document_chunks` 中执行 Top-5 相似度检索（HNSW 索引，余弦距离）。
5. 取最近 10 条消息（5 轮对话）作为对话上下文，避免上下文无限增长。
6. 将检索结果和对话上下文拼装为 Prompt。
7. 调用会话绑定的 Provider 生成答案，通过 SSE 流式返回 token。
8. 前端通过 EventSource 逐字渲染回答内容，并以 Markdown 格式展示。
9. SSE 事件格式：`data: {"type": "token", "content": "..."}\n\n`，结束事件：`data: {"type": "done", "message_id": "..."}\n\n`。

### 8.2 Prompt 模板

系统 Prompt 模板示例如下：

```
你是一个文档问答助手。请严格基于以下文档内容回答用户问题。
如果文档中找不到答案依据，请明确告知"未在文档中找到依据"，不要编造答案。

【文档内容】
{retrieved_chunks}

【对话历史】
{conversation_history}

【用户问题】
{user_question}
```

Prompt 拼装规则：
1. 检索到的切片按相似度降序拼入 `retrieved_chunks`，每个切片标注来源文档名和片段序号。
2. 对话历史取最近 10 条消息（5 轮），按时间升序拼入。
3. Prompt 总长度需控制在模型 context window 限制内，超出时优先裁剪对话历史。

### 8.3 无答案处理

满足以下任一条件时直接返回固定语义提示：

1. 当前范围下没有可用文档。
2. 检索结果为空。
3. 检索结果余弦相似度低于 0.3（默认阈值，可通过环境变量 `SIMILARITY_THRESHOLD` 调整）。

默认返回口径为：`未在文档中找到依据。`

### 8.4 SSE 流式输出策略

1. 助手消息在 SSE 流完成后一次性写入消息表，避免部分消息残留。
2. 若 SSE 连接中断，后端检测 `Request.is_disconnected()` 并取消 LLM 调用，不写入消息表。
3. 前端重试时重新发送整个问题，不尝试恢复中断的流。

### 8.5 多轮上下文策略

1. 每次问答读取最近若干轮消息，避免上下文无限增长。
2. 会话创建时绑定 Provider 快照，后续问答沿用该快照。
3. 历史会话不因默认 Provider 变化而自动切换模型。

## 9. Provider 抽象与配置方案

### 9.1 Provider 抽象接口

后端定义统一 LLM Provider Adapter，至少包含以下能力：

1. `test_connection`：测试 Provider 连接是否可用。
2. `generate_answer`：调用 LLM 生成回答，支持流式输出（返回 AsyncGenerator）。

Embedding 服务独立于 LLM Provider Adapter：

1. `EmbeddingService`：统一使用 OpenAI Embedding API（text-embedding-3-small，1536 维）。
2. 无论 LLM Provider 选择 OpenAI、Claude 还是本地模型，Embedding 均由 `EmbeddingService` 完成。

### 9.2 Provider 实现方式

1. OpenAI：直接调用 OpenAI API。
2. Claude：通过独立适配器处理鉴权和请求格式差异。
3. OpenAI-compatible：按 OpenAI 协议构造请求，适配本地模型服务。

### 9.3 配置存储要求

1. API Key 必须脱敏返回给前端。
2. 数据库存储时应进行加密或至少预留加密封装层。
3. 默认 Provider 全局唯一。

## 10. 前端页面与状态设计

### 10.1 路由设计

1. `/`：重定向到 `/documents`。
2. `/documents`：文档管理页。
3. `/chat`：Agent 问答页。
4. `/settings`：系统配置页。

### 10.2 组件库与设计规范

1. 前端统一使用 Ant Design (antd) 组件库，启用中文 locale。
2. 导航采用水平顶部导航栏（Ant Design Layout.Header），左侧应用名称，右侧三个导航链接。
3. 统一错误展示：表单校验 = 行内红色提示；异步失败 = Toast 通知（antd notification，5 秒自动消失）；SSE 失败 = 消息流内联提示 + 重试按钮。

### 10.3 页面状态

所有列表视图的首次加载使用 Ant Design Skeleton 组件（骨架屏），匹配最终表格/列表布局，避免使用简单 spinner。

#### 文档管理页

状态包括：首次加载（Skeleton 骨架屏）、空列表（居中引导上传）、上传中（按钮 loading）、解析中（标签脉冲动画）、可用、解析失败（悬停查看错误）、删除确认中（Modal）、搜索无结果。

#### Agent 问答页

状态包括：首次加载（Skeleton 骨架屏）、无会话（居中引导新建）、新会话零消息（居中引导提问）、会话列表加载中（侧栏 Skeleton）、会话加载中、SSE 流式输出中（闪烁光标 ▌）、回答成功、问答失败（内联错误 + 重试）、SSE 连接中断（内联提示 + 重试）、无依据提示（含建议操作）、无可用文档（引导上传）。

#### 系统配置页

状态包括：首次加载（Skeleton 骨架屏）、零 Provider（居中引导新增）、Provider 列表、编辑中、测试中（按钮 loading）、测试成功（绿色提示 3 秒）、测试失败（红色错误原因）、保存成功、保存失败。

### 10.4 前端状态管理

1. 使用 TanStack Query (React Query) 管理服务端状态（文档列表、会话列表、Provider 配置），提供缓存、自动刷新和乐观更新。
2. 使用 Zustand 管理页面级 UI 状态（SSE 流式输出状态、当前会话选择、表单编辑状态）。
3. 上传、问答、配置保存都必须有明确的 loading 和 error 状态。
4. 关键列表和消息流在接口成功后刷新，不依赖前端猜测状态。
5. 文档列表轮询：当任意文档处于 `解析中` 状态时，TanStack Query 以 `refetchInterval: 3000` 每 3 秒轮询 `GET /api/documents`。所有文档进入终态后停止轮询。

### 10.5 响应式设计

系统支持全响应式布局，三个断点：

1. **桌面（≥1280px）**：完整布局，文档表格显示所有列，问答页显示侧栏 + 消息区域，配置页列表 + 行内编辑。
2. **平板（768-1279px）**：文档表格隐藏大小列，问答页侧栏收起为抽屉（☰ 按钮触发），配置页列表/表单上下堆叠。
3. **手机（<768px）**：文档以堆叠卡片展示（名称+状态+操作），问答页全屏消息、会话列表为抽屉，配置页堆叠表单。

### 10.6 无障碍要求

1. 所有交互元素支持键盘导航（Tab、Enter、Escape），Ant Design 组件默认支持。
2. 页面使用 ARIA 语义标签：`<nav>`（导航栏）、`<main>`（页面主区域）、`<aside>`（问答页会话侧栏）。
3. 颜色对比度符合 WCAG AA 标准（正文 4.5:1，UI 组件 3:1）。
4. 移动端触摸目标最小 44×44px。
5. 状态标签同时使用颜色和文字标签，不依赖纯颜色区分。

### 10.7 边界场景处理

1. 删除正在解析中的文档：后端先将文档状态标记为已删除，解析任务在写入切片前检查文档是否仍存在，若已删除则放弃写入并标记任务为取消。
2. 删除会话关联的文档：当会话的 `scope_type` 为 `single` 且关联文档已被删除时，问答接口返回"关联文档已被删除，请新建会话"提示。
3. Provider 配置被删除后的会话处理：已创建的会话保留 Provider 快照，可继续使用，不受 Provider 删除影响。

## 10.8 数据库迁移方案

1. 使用 Alembic 管理数据库 Schema 迁移。
2. 后端启动时自动执行 `alembic upgrade head`，确保数据库结构与代码一致。
3. 初始迁移脚本需创建 pgvector 扩展（`CREATE EXTENSION IF NOT EXISTS vector`）及所有业务表。
4. 每次 Schema 变更需生成新的迁移版本文件。

## 10.9 CORS 配置

前后端分离架构中，前端和后端运行在不同端口，需配置 CORS：

1. 后端 FastAPI 启动时通过 `CORSMiddleware` 配置允许的前端域名。
2. 开发环境允许 `http://localhost:3000`（前端端口）。
3. 生产环境通过环境变量 `CORS_ORIGINS` 配置允许域名。

## 10.10 Embedding API Key 管理

Embedding 服务（OpenAI Embedding API）的 API Key 通过环境变量 `EMBEDDING_API_KEY` 配置：

1. Docker Compose 通过 `.env` 文件注入。
2. 后端启动时校验该环境变量是否存在，缺失时给出明确启动失败提示。
3. 该 Key 不通过系统配置页管理，不存入数据库。

## 11. 部署架构与运行方式

### 11.1 Docker Compose 组成

至少包含以下服务：

1. `frontend`
2. `backend`
3. `postgres`

### 11.2 持久化内容

1. PostgreSQL 数据目录。
2. 上传文件目录。

### 11.3 运行要求

1. 前端和后端均应提供 Dockerfile。
2. 后端启动时自动检查数据库连接和 pgvector 扩展可用性。
3. 本地开发和演示环境均以 Docker Compose 作为标准启动方式。

## 12. 安全、日志与错误处理

### 12.1 安全要求

1. 前端不保存明文 API Key。
2. 文件类型必须在前后端双重校验。
3. 所有接口需返回统一错误结构，便于前端处理。

### 12.2 日志要求

后端至少记录以下日志：

1. 文件上传开始与结束。
2. 文档解析开始、成功、失败。
3. 问答请求开始、成功、失败。
4. Provider 测试连接结果。

### 12.3 错误处理要求

1. 文件解析失败时写入文档错误信息。
2. 模型调用失败时返回用户可理解的错误提示。
3. 数据库或依赖不可用时健康检查接口应返回失败状态。

## 13. 测试方案

### 13.1 前端单元测试

覆盖以下内容：

1. 文档列表状态渲染（空列表、加载中、有数据、解析失败状态标签）。
2. 上传按钮和表单交互（文件选择、格式校验、大小校验提示）。
3. 问答消息流渲染（用户消息、助手消息、Markdown 格式正确渲染）。
4. SSE 流式输出组件（逐字渲染、加载指示器、连接中断提示）。
5. 会话历史侧栏（会话列表渲染、切换会话、删除会话确认）。
6. Provider 配置表单校验（必填项、类型校验、测试连接状态）。
7. 搜索框输入与筛选行为。
8. 分页器交互。

### 13.2 后端单元测试

覆盖以下内容：

1. 文件格式校验（合法格式通过、非法格式拒绝、大小写扩展名）。
2. 文件大小校验（50 MB 上限，超出拒绝）。
3. 文档状态流转（上传成功 → 解析中 → 可用 / 解析失败）。
4. 切片逻辑（500 字符窗口、100 字符重叠、段落边界处理）。
5. TXT 解析（UTF-8 正常解析、非 UTF-8 编码兜底）。
6. Markdown 解析（标题层级提取、纯文本输出）。
7. PDF 解析（正常 PDF、密码锁定 PDF 报错、损坏 PDF 报错）。
8. DOCX 解析（正常 DOCX、格式异常 DOCX 报错）。
9. 空文档检测（0 字节文件、提取文本为空）。
10. EmbeddingService 单元测试（正常 embedding、空文本拒绝、批量 embedding）。
11. Provider 配置校验（必填字段、类型校验、重复配置检查）。
12. 无依据返回逻辑（无可用文档、检索结果为空、相似度低于阈值）。
13. 会话标题自动生成（截取首次提问前 50 字符）。
14. 停滞任务恢复（运行超 5 分钟自动重置）。
15. 最大重试次数（3 次失败后停止重试）。

### 13.3 后端接口测试

覆盖以下场景：

1. TXT、Markdown、PDF、DOCX 上传成功。
2. 上传非法格式文件返回 400 错误。
3. 上传超过 50 MB 文件返回 413 错误。
4. 上传空文件（0 字节）解析后标记为失败。
5. 上传同名文件创建独立记录。
6. 文档解析成功后状态变为 `可用`。
7. 文档解析失败后状态变为 `解析失败` 并记录错误。
8. 删除文档后无法继续被查询和问答命中。
9. 删除不存在的文档返回 404。
10. 文档列表支持按名称搜索和分页。
11. 创建问答会话并返回 Provider 快照。
12. 查询会话列表返回标题和创建时间。
13. 删除会话同时删除关联消息。
14. 问答接口返回 SSE 流式响应，事件格式正确。
15. 问答支持全部文档和单文档范围。
16. 第二轮追问能够继承上一轮语境。
17. 无可用文档时返回明确提示。
18. LLM 调用超时时返回错误事件。
19. OpenAI、Claude、OpenAI-compatible Provider 可保存、测试和切换默认值。
20. 测试连接失败时返回失败原因。
21. 健康检查接口在数据库可用与不可用时返回正确状态。

### 13.4 E2E 测试

覆盖以下关键用户流程：

1. 上传 TXT 文件 → 等待解析完成 → 创建会话 → 提问 → 验证流式回答。
2. 上传 PDF 文件 → 验证解析状态变为可用。
3. 上传文档 → 在问答页提问 → 切换历史会话 → 验证消息恢复。

## 14. 与 PRD 验收项的映射关系

| PRD 要求 | 技术实现落点 |
| --- | --- |
| 支持多格式文档上传 | 上传接口 + 文档解析器 + 文件存储目录 |
| 文档查询与删除 | 文档管理 API + 数据库元数据 + 前端列表页 |
| 基于文档问答 | 向量检索 + Prompt 拼装 + LLM 生成 |
| 多轮对话 | 会话表 + 消息表 + 上下文裁剪策略 |
| 多 Provider 配置 | Provider Adapter + 配置表 + 默认值切换接口 |
| 三大核心页面 | React 路由 + 页面模块拆分 |
| 镜像与联调方案 | Dockerfile + Docker Compose |
| 单元测试和接口测试 | 前端单测 + 后端单测 + 后端接口测试 |

## 15. 边界与后续扩展

### 15.1 当前边界

1. 不包含权限系统。
2. 不包含 OCR。
3. 不包含扫描版 PDF 增强识别。
4. 不包含复杂表格结构恢复。

### 15.2 后续扩展方向

1. 增加答案引用来源片段返回。
2. 增加扫描版 PDF 与图片文字识别。
3. 增加更复杂的召回重排策略。
4. 增加用户体系和权限控制。
