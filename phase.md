阶段 G — 后端搭建计划
G1 — 项目骨架 + 数据库
搭建 FastAPI 项目结构 + SQLite/PostgreSQL 数据模型
内容	说明
项目初始化	backend/ 目录，pyproject.toml，依赖安装
目录结构	app/main.py, app/models/, app/schemas/, app/api/, app/services/, app/core/
数据模型	3 张表：documents, chat_sessions, chat_messages, provider_configs
数据库连接	SQLAlchemy async + alembic 迁移
配置管理	.env + Pydantic Settings（端口、数据库 URL、上传目录）
启动验证	uvicorn 启动，/health 端点返回 200
G2 — 供应商管理 API（Settings）
最简单的 CRUD，无外部依赖，适合先做
端点	方法	说明
/api/providers	GET	列表（api_key 脱敏返回）
/api/providers	POST	创建供应商
/api/providers/{id}	PUT	更新（空 api_key 保留原值）
/api/providers/{id}/test	POST	测试连接（实际调用 LLM API）
/api/providers/{id}/default	PUT	设为默认
/api/providers/{id}	DELETE	删除（默认供应商不可删）
G3 — 文档管理 API（Documents）
文件上传 + 状态机
端点	方法	说明
/api/documents	GET	分页列表，支持 keyword / page / page_size
/api/documents	POST	上传文件（multipart/form-data），存储到磁盘
/api/documents/{id}	GET	单个文档详情
/api/documents/{id}	DELETE	删除文档 + 清理文件
后台任务	—	上传后异步解析：提取文本 → 分块 → 存储
涉及：文件存储管理、PDF/DOCX/TXT/MD 文本提取、状态机（上传成功→解析中→可用/解析失败）
G4 — 向量化 + 检索
RAG 核心：文档分块 → embedding → 向量存储 → 相似度检索
内容	说明
文本分块	RecursiveCharacterTextSplitter（chunk_size=500, overlap=50）
Embedding	调用供应商 API 生成向量（OpenAI / 兼容接口）
向量存储	ChromaDB 或 FAISS 本地存储
检索接口	根据 query 返回 top-k 相关分块
与 G3 集成	文档解析完成后自动触发向量化
G5 — 会话 + 聊天 API（Chat）
会话管理 + SSE 流式回答
端点	方法	说明
/api/sessions	GET	会话列表（按 updated_at 降序）
/api/sessions	POST	创建会话（scope_type + document_id）
/api/sessions/{id}	DELETE	删除会话 + 所有消息
/api/sessions/{id}/messages	GET	消息列表
/api/sessions/{id}/messages	POST	发送消息 → SSE 流式返回
SSE 格式与前端契约一致：
data: {"type":"token","content":"..."}
data: {"type":"done","message_id":"..."}
流程：用户消息 → 检索相关文档块 → 构造 prompt → 调用 LLM（streaming） → SSE 推送
G6 — 前后端对接
将前端 mock services 替换为真实 API 调用
内容	说明
创建 api.ts	axios/fetch 封装，base URL 配置
改写 services/*.ts	每个 mock 函数替换为真实 HTTP 请求
sendMessage	改用 EventSource / fetch + ReadableStream 对接 SSE
CORS 配置	FastAPI 添加 CORS 中间件，允许前端 dev server
代理配置	Vite proxy 配置 /api → localhost:8000
联调测试	全流程走通：上传→解析→问答→流式回答

依赖关系
G1 (骨架) → G2 (供应商) → G3 (文档) → G4 (向量化) → G5 (聊天) → G6 (对接)
                                ↘                    ↗
                                 G4 依赖 G2(embedding 调用供应商)
                                 G5 依赖 G2(LLM 调用) + G4(检索)