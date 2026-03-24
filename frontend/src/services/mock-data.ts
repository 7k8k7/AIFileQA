import type {
  Document,
  ChatSession,
  ChatMessage,
  ProviderConfig,
} from '../types';

// ── Documents ──

export const mockDocuments: Document[] = [
  {
    id: 'd1a2b3c4-0001-4000-8000-000000000001',
    file_name: '微服务架构设计.pdf',
    file_ext: '.pdf',
    file_size: 2516582, // 2.4 MB
    status: '可用',
    uploaded_at: '2026-03-23T14:30:00Z',
    updated_at: '2026-03-23T14:32:15Z',
  },
  {
    id: 'd1a2b3c4-0001-4000-8000-000000000002',
    file_name: '产品需求文档 v3.docx',
    file_ext: '.docx',
    file_size: 876544, // 856 KB
    status: '解析中',
    uploaded_at: '2026-03-23T15:12:00Z',
    updated_at: '2026-03-23T15:12:00Z',
  },
  {
    id: 'd1a2b3c4-0001-4000-8000-000000000003',
    file_name: 'API 接口规范.md',
    file_ext: '.md',
    file_size: 131072, // 128 KB
    status: '可用',
    uploaded_at: '2026-03-22T09:45:00Z',
    updated_at: '2026-03-22T09:45:30Z',
  },
  {
    id: 'd1a2b3c4-0001-4000-8000-000000000004',
    file_name: '用户手册.txt',
    file_ext: '.txt',
    file_size: 45056, // 44 KB
    status: '上传成功',
    uploaded_at: '2026-03-24T08:00:00Z',
    updated_at: '2026-03-24T08:00:00Z',
  },
  {
    id: 'd1a2b3c4-0001-4000-8000-000000000005',
    file_name: '损坏文件.pdf',
    file_ext: '.pdf',
    file_size: 1024,
    status: '解析失败',
    error_message: '无法提取文本内容：文件格式损坏',
    uploaded_at: '2026-03-21T16:00:00Z',
    updated_at: '2026-03-21T16:01:00Z',
  },
];

// ── Chat Sessions ──

export const mockSessions: ChatSession[] = [
  {
    id: 's1a2b3c4-0001-4000-8000-000000000001',
    title: '微服务拆分策略',
    scope_type: 'single',
    document_id: 'd1a2b3c4-0001-4000-8000-000000000001',
    created_at: '2026-03-23T15:30:00Z',
    updated_at: '2026-03-23T15:45:00Z',
  },
  {
    id: 's1a2b3c4-0001-4000-8000-000000000002',
    title: 'API 鉴权方案讨论',
    scope_type: 'all',
    created_at: '2026-03-23T14:20:00Z',
    updated_at: '2026-03-23T14:35:00Z',
  },
  {
    id: 's1a2b3c4-0001-4000-8000-000000000003',
    title: '数据库选型对比',
    scope_type: 'all',
    created_at: '2026-03-22T10:00:00Z',
    updated_at: '2026-03-22T10:30:00Z',
  },
  {
    id: 's1a2b3c4-0001-4000-8000-000000000004',
    title: '部署架构规划',
    scope_type: 'single',
    document_id: 'd1a2b3c4-0001-4000-8000-000000000003',
    created_at: '2026-03-21T09:00:00Z',
    updated_at: '2026-03-21T09:20:00Z',
  },
];

// ── Chat Messages ──

export const mockMessages: Record<string, ChatMessage[]> = {
  // Session 1: 微服务拆分策略
  's1a2b3c4-0001-4000-8000-000000000001': [
    {
      id: 'm001',
      session_id: 's1a2b3c4-0001-4000-8000-000000000001',
      role: 'user',
      content: '微服务拆分应该遵循哪些核心原则？',
      created_at: '2026-03-23T15:30:00Z',
    },
    {
      id: 'm002',
      session_id: 's1a2b3c4-0001-4000-8000-000000000001',
      role: 'assistant',
      content: `根据您上传的《微服务架构设计》文档，微服务拆分应遵循以下核心原则：

**1. 单一职责原则** — 每个服务围绕一个明确的业务能力构建，避免职责交叉。

**2. 数据自治** — 每个微服务拥有自己的数据存储，不直接访问其他服务的数据库。

**3. 接口契约** — 服务间通过定义良好的 API 通信，推荐使用 RESTful 或 gRPC。

**4. 故障隔离** — 单个服务的故障不应影响整体系统运行，采用熔断器模式。

\`\`\`python
# 示例：使用 Circuit Breaker 模式
@circuit_breaker(failure_threshold=5, recovery_timeout=30)
def call_user_service(user_id: str):
    return requests.get(f"{USER_SERVICE_URL}/users/{user_id}")
\`\`\`

> 来源：微服务架构设计.pdf · 第 3 章 · 置信度 92%`,
      created_at: '2026-03-23T15:30:15Z',
    },
    {
      id: 'm003',
      session_id: 's1a2b3c4-0001-4000-8000-000000000001',
      role: 'user',
      content: '具体怎么确定服务边界？有没有实际的方法论？',
      created_at: '2026-03-23T15:32:00Z',
    },
    {
      id: 'm004',
      session_id: 's1a2b3c4-0001-4000-8000-000000000001',
      role: 'assistant',
      content: `文档中推荐了两种主要的服务边界划分方法：

**方法一：领域驱动设计 (DDD)**

通过识别 **限界上下文 (Bounded Context)** 来划分服务边界：

1. 进行事件风暴 (Event Storming)，识别核心业务事件
2. 将相关事件聚合为限界上下文
3. 每个限界上下文对应一个微服务

**方法二：业务能力分解**

按组织的业务能力矩阵拆分：

| 业务域 | 微服务 | 核心实体 |
|--------|--------|----------|
| 用户管理 | user-service | User, Role, Permission |
| 订单处理 | order-service | Order, OrderItem |
| 支付结算 | payment-service | Payment, Refund |
| 库存管理 | inventory-service | Stock, Warehouse |

> 来源：微服务架构设计.pdf · 第 4 章 · 置信度 88%`,
      created_at: '2026-03-23T15:32:20Z',
    },
  ],

  // Session 2: API 鉴权方案讨论
  's1a2b3c4-0001-4000-8000-000000000002': [
    {
      id: 'm005',
      session_id: 's1a2b3c4-0001-4000-8000-000000000002',
      role: 'user',
      content: 'JWT 和 OAuth2 在微服务鉴权中各有什么优劣？',
      created_at: '2026-03-23T14:20:00Z',
    },
    {
      id: 'm006',
      session_id: 's1a2b3c4-0001-4000-8000-000000000002',
      role: 'assistant',
      content: `根据您的文档，两种方案的对比如下：

| 维度 | JWT | OAuth2 |
|------|-----|--------|
| 无状态性 | ✅ 完全无状态 | ❌ 需要 Token 存储 |
| 吊销能力 | ❌ 困难，需黑名单 | ✅ 可即时吊销 |
| 性能 | ✅ 无需查库验证 | ❌ 每次需验证 Token |
| 适用场景 | 内部微服务间通信 | 第三方应用授权 |

**推荐方案：** 混合使用 — OAuth2 用于外部 API 网关鉴权，JWT 用于内部服务间通信。

> 来源：API 接口规范.md · 第 2 节 · 置信度 85%`,
      created_at: '2026-03-23T14:20:15Z',
    },
  ],
};

// ── Provider Configs ──

export const mockProviders: ProviderConfig[] = [
  {
    id: 'p1a2b3c4-0001-4000-8000-000000000001',
    provider_type: 'openai',
    base_url: 'https://api.openai.com/v1',
    model_name: 'gpt-4o',
    api_key: 'sk-proj-****7f3d',
    temperature: 0.7,
    max_tokens: 4096,
    timeout_seconds: 30,
    is_default: true,
    created_at: '2026-03-20T10:00:00Z',
    updated_at: '2026-03-20T10:00:00Z',
  },
  {
    id: 'p1a2b3c4-0001-4000-8000-000000000002',
    provider_type: 'claude',
    base_url: 'https://api.anthropic.com/v1',
    model_name: 'claude-sonnet-4-6',
    api_key: 'sk-ant-****a1b2',
    temperature: 0.5,
    max_tokens: 8192,
    timeout_seconds: 60,
    is_default: false,
    created_at: '2026-03-21T14:00:00Z',
    updated_at: '2026-03-21T14:00:00Z',
  },
];

// ── Simulated SSE stream tokens ──

export const mockStreamTokens = [
  '根据', '您', '上传', '的', '文档', '，',
  '以下', '是', '关于', '该', '问题', '的', '分析', '：\n\n',
  '**', '要点', '一', '**', ' — ',
  '文档', '中', '明确', '指出', '了', '核心', '架构', '决策', '。\n\n',
  '**', '要点', '二', '**', ' — ',
  '实现', '方案', '需要', '考虑', '以下', '因素', '：\n',
  '1. ', '性能', '需求\n',
  '2. ', '可维护性\n',
  '3. ', '团队', '技术', '栈\n\n',
  '> ', '来源', '：', '微服务架构设计', '.pdf', ' · ', '第 5 章', ' · ', '置信度 ', '90%',
];
