# DocQA Frontend — 智能文档问答助手

基于 RAG 的文档问答助手前端，支持文档上传、智能检索问答、多供应商 LLM 配置。

## 技术栈

| 层 | 技术 |
|---|------|
| 框架 | React 19 + TypeScript |
| 构建 | Vite 8 |
| UI 组件 | Ant Design v5 (zh_CN) |
| 服务端状态 | TanStack Query (React Query) |
| UI 状态 | Zustand |
| HTTP | Axios |
| 路由 | React Router v7 |

## 目录结构

```
src/
├── main.tsx              # 入口：StrictMode + ConfigProvider + QueryClientProvider
├── App.tsx               # 路由：/ → /documents, /chat, /settings
├── global.css            # CSS 变量 (DESIGN.md tokens) + Reset + 暗色模式
├── theme/
│   └── tokens.ts         # antd ThemeConfig + CSS 变量定义
├── types/
│   └── index.ts          # Document, ChatSession, ChatMessage, ProviderConfig, SSE
├── layouts/
│   ├── AppLayout.tsx      # 毛玻璃顶部导航 + Outlet
│   └── AppLayout.module.css
├── pages/
│   ├── Documents/         # 文档管理（上传、列表、搜索、删除）
│   ├── Chat/              # 智能问答（会话管理、SSE 流式对话）
│   └── Settings/          # 系统设置（LLM 供应商配置）
├── components/            # 公共组件
├── hooks/                 # 自定义 Hooks
├── services/              # API 请求层
└── stores/                # Zustand stores
```

## 启动

```bash
pnpm install
pnpm dev             # http://localhost:5173
```

## 构建

```bash
pnpm build           # 输出到 dist/
pnpm preview         # 预览生产构建
```

## 设计系统

所有视觉规范定义在项目根目录 `DESIGN.md`，包括：
- 色彩系统（克制策略：一个主色 + 中性灰阶）
- 字体（Outfit 标题 / Noto Serif SC 装饰 / 系统字体 UI / JetBrains Mono 代码）
- 8px 间距网格
- 5 级阴影 + 光晕变体
- 毛玻璃导航栏 + 滚动渐入动画
