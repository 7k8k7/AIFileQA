# Design System — 智能文档问答助手

## Product Context
- **What this is:** A RAG-based document Q&A assistant that lets users upload documents, parse them, and ask questions answered by LLM with retrieved context
- **Who it's for:** Individual users managing personal document collections (coursework project)
- **Space/industry:** AI-powered document management and knowledge retrieval
- **Project type:** Web app (React + FastAPI)

## Aesthetic Direction
- **Direction:** Refined Industrial — 工业骨架 + 精致细节
- **Decoration level:** Purposeful — 结构做主力，少量精心设计的视觉细节（毛玻璃、渐变光晕、滚动渐入）提升品质感
- **Mood:** 冷静、精确、有呼吸感。界面像一台精密仪器 — 克制但不廉价，每一处视觉效果都有功能意图。
- **Differentiation:** 毛玻璃导航栏 + 网格背景纹理 + 滚动触发动画，三者共同构成"精密工具"的视觉语言

## Typography
- **Display/Hero:** `Outfit` — 几何无衬线，用于页面大标题和 Hero 区域，通过 Google Fonts 加载
  - Weights: 300 (light), 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
  - `letter-spacing: -0.035em` — 标题紧凑排版
- **Subtitle/Accent:** `Noto Serif SC` — 中文衬线体，用于副标题和需要区分层级的装饰性文案
  - Weights: 400, 600, 700
  - 用途有限，仅在需要"编辑感"的场景出现（如 Hero 副标题、空状态引导语）
- **Body/UI:** System font stack — `-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif`
  - 正文、表格、表单、按钮、标签等所有 UI 元素
  - 零加载时间，最佳 CJK 渲染
- **Data/Tables:** Same system stack with `font-variant-numeric: tabular-nums` for aligned numbers
- **Code:** `JetBrains Mono` — 等宽字体，用于 LLM 输出的代码片段、技术标注、token 名称
  - Weights: 400, 500, 600
- **Loading strategy:**
  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@300;400;500;600;700&family=Noto+Serif+SC:wght@400;600;700&display=swap" rel="stylesheet">
  ```
- **Font variables:**
  ```css
  --font-display: 'Outfit', sans-serif;
  --font-serif: 'Noto Serif SC', 'Source Han Serif SC', serif;
  --font-system: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-code: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  ```
- **Scale:**
  - `--font-size-xs`: 12px / 0.75rem — caption, 来源标注
  - `--font-size-sm`: 13px / 0.8125rem — 辅助文本, UI 标签
  - `--font-size-base`: 14px / 0.875rem — 正文 (Ant Design default)
  - `--font-size-lg`: 16px / 1rem — 小标题
  - `--font-size-xl`: 20px / 1.25rem — 页面标题
  - `--font-size-2xl`: 24px / 1.5rem — 区域标题
  - `--font-size-3xl`: 30px / 1.875rem — Display

## Color
- **Approach:** Restrained — one accent + neutrals, color is rare and meaningful
- **Primary:** `#1677FF` — Ant Design blue, used for interactive elements, links, and primary actions
  - Hover: `#4096FF`
  - Active: `#0958D9`
  - Background tint: `#E6F4FF`
  - Alpha variants: `rgba(22, 119, 255, 0.05 / 0.10 / 0.20)` — 用于悬停底色、聚焦光圈、选中态
- **Accent gradient:** `linear-gradient(135deg, #1677FF 0%, #6C5CE7 100%)` — 仅用于 Hero 标题等极少数装饰场景
- **Background:** `#FAFAFA` — warm off-white, reduces eye strain vs pure white
  - Elevated: `#F5F5F5` — 侧栏、表头等需要区分层级的区域
- **Surface:** `#FFFFFF` — cards, modals, dropdowns
- **Text primary:** `#1F1F1F` — near-black, high contrast against both backgrounds
- **Text secondary:** `#8C8C8C` — secondary information, timestamps, helper text
- **Text tertiary:** `#BFBFBF` — placeholder, disabled text,最弱层级
- **Border:** `#F0F0F0` — subtle structural separation (default)
  - Strong: `#D9D9D9` — input borders, dividers needing more definition
- **Semantic:**
  - Success: `#52C41A` / bg `#F6FFED` / border `#B7EB8F` — upload complete, connection test passed
  - Warning: `#FAAD14` / bg `#FFFBE6` / border `#FFE58F` — parsing in progress, configuration warnings
  - Error: `#FF4D4F` / bg `#FFF2F0` / border `#FFCCC7` — validation errors, failed operations
  - Info: `#1677FF` / bg `#E6F4FF` / border `#91CAFF` — informational notices
- **Dark mode:**
  - All colors defined as CSS custom properties
  - Dark mode swaps variable values via `[data-theme="dark"]` selector
  - Key overrides:
    ```css
    --color-bg: #0A0A0B;
    --color-bg-elevated: #141415;
    --color-surface: #1A1A1C;
    --color-text: #E8E8EA;
    --color-text-secondary: #8C8C90;
    --color-text-tertiary: #4A4A4E;
    --color-border: #2A2A2E;
    --color-border-strong: #3A3A3E;
    --color-primary: #3B8BFF; /* slightly brighter for dark bg */
    ```
  - Semantic colors reduce saturation ~15%
  - Shadows increase opacity to compensate for dark background

## Shadows
- **System:** 5-level shadow scale + 1 glow variant
  ```css
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);
  --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
  --shadow-glow: 0 0 0 1px var(--color-primary-10), 0 4px 16px var(--color-primary-10);
  ```
- **Usage:**
  - `xs` — 表格行悬停、按钮默认
  - `sm` — 卡片默认、Badge
  - `md` — 卡片悬停、下拉菜单
  - `lg` — 弹窗、悬浮面板
  - `xl` — 页面原型容器、Dialog
  - `glow` — 卡片聚焦态（primary 色光晕）

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable
- **Scale:**
  - `--space-2xs`: 2px
  - `--space-xs`: 4px
  - `--space-sm`: 8px
  - `--space-md`: 16px
  - `--space-lg`: 24px
  - `--space-xl`: 32px
  - `--space-2xl`: 48px
  - `--space-3xl`: 64px

## Layout
- **Approach:** Grid-disciplined — strict columns, predictable alignment
- **Grid:** 24-column (Ant Design Grid), 16px gutter
- **Max content width:** 1440px (inner content), 1200px (text-heavy pages)
- **Border radius:**
  - `--radius-sm`: 4px — buttons, inputs, tags
  - `--radius-md`: 8px — cards, modals, tooltips
  - `--radius-lg`: 12px — large containers, upload zone
  - `--radius-xl`: 16px — Hero sections, feature cards
  - `--radius-full`: 9999px — avatars, badges, pill buttons, nav links
- **Navigation:** Horizontal top nav bar
  - 固定定位 (`position: fixed`), 高度 56px
  - 毛玻璃效果: `backdrop-filter: blur(20px) saturate(180%); background: rgba(250,250,250,0.72)`
  - Logo left, nav links center (pill-shaped active state), actions right
  - 暗色模式: `background: rgba(10,10,11,0.75)`
- **Breakpoints:**
  - Desktop: ≥1280px — full layout
  - Tablet: 768–1279px — collapsible sidebar, responsive grid
  - Mobile: <768px — stacked layout, bottom nav, sidebar hidden

## Motion
- **Approach:** Purposeful — 微交互确认操作，滚动动画引导阅读节奏，装饰动效仅限于 Hero 区域
- **Easing:**
  ```css
  --ease-out: cubic-bezier(0, 0, 0.2, 1);     /* 进入 — 快到慢 */
  --ease-in: cubic-bezier(0.4, 0, 1, 1);       /* 退出 — 慢到快 */
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1); /* 移动 — 两端缓 */
  ```
- **Duration:**
  ```css
  --duration-fast: 150ms;   /* 按钮悬停、toggle、checkbox */
  --duration-normal: 250ms; /* 下拉展开、tooltip、skeleton fade */
  --duration-slow: 400ms;   /* 弹窗、侧栏折叠 */
  ```
  - Micro: 50–100ms — button hover, toggle
  - Short: 150–250ms — dropdown open, tooltip appear, skeleton fade
  - Medium: 250–400ms — modal open/close, sidebar collapse
  - Long: 400–700ms — scroll-triggered fade-in, page transitions
- **Scroll animations:**
  - 元素进入视口时触发 `.fade-in` → `.visible`
  - `IntersectionObserver` with `threshold: 0.1, rootMargin: '0px 0px -40px 0px'`
  - 同组元素使用 `.stagger-N` (50ms increments) 错开入场
  - 动画: `opacity 0→1, translateY 24px→0, duration 700ms, ease-out`
- **Decorative (Hero only):**
  - 光晕脉冲: `radial-gradient` of primary color, `scale(1)→scale(1.15)`, 6s alternate infinite
  - 导航指示点: `scale(1)→scale(0.8)`, 2s infinite
  - 滚动提示: `translateY(0)→translateY(8px)`, 3s infinite
- **Skeleton loading:** Ant Design Skeleton + `opacity 1→0.4→1`, 1.5s ease-in-out infinite

## Backgrounds & Textures
- **Grid pattern:** 页面级网格纹理，用于 Hero 和需要"蓝图感"的区域
  ```css
  background-image:
    linear-gradient(var(--color-border) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-border) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, black 20%, transparent 70%);
  ```
- **Primary glow:** 用于 Hero 背景的微妙光源
  ```css
  radial-gradient(ellipse, var(--color-primary-10) 0%, transparent 70%)
  ```
- **Selection highlight:** `::selection { background: var(--color-primary-20); }`

## Component Library
- **Framework:** Ant Design (antd) v5
- **Locale:** zh_CN (Chinese)
- **Token customization:** Override Ant Design's design tokens via `ConfigProvider` theme:
  ```js
  {
    token: {
      colorPrimary: '#1677FF',
      colorBgLayout: '#FAFAFA',
      colorText: '#1F1F1F',
      colorTextSecondary: '#8C8C8C',
      colorTextTertiary: '#BFBFBF',
      colorBorder: '#F0F0F0',
      colorBorderSecondary: '#D9D9D9',
      borderRadius: 8,
      fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
      fontSize: 14,
      controlHeight: 36,
      boxShadow: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
    }
  }
  ```
- **Interactive patterns:**
  - Cards: `border-color` transition on hover + `shadow-glow` on focus
  - Table rows: `background: var(--color-primary-05)` on hover
  - Buttons: `translateY(-1px)` lift on hover for primary buttons
  - Upload zone: dashed border → solid primary border + primary tint background on hover/dragover

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-23 | Initial design system created | Created by /design-consultation |
| 2026-03-23 | Upgraded to Refined Industrial aesthetic | Preview page validated: pure utilitarian feels cheap; adding Outfit, Noto Serif SC, glassmorphism nav, scroll animations elevates quality without losing industrial character |
| 2026-03-23 | Outfit for display, Noto Serif SC for accent | Geometric sans (Outfit) reinforces precision; serif accent (Noto Serif SC) adds editorial warmth to key moments. System fonts remain for all body/UI |
| 2026-03-23 | Three-font loading via Google Fonts | Outfit + Noto Serif SC + JetBrains Mono loaded together with preconnect; system fonts handle body so critical rendering path unaffected |
| 2026-03-23 | 5-level shadow scale + glow variant | Finer shadow control than antd defaults; glow variant creates branded focus states |
| 2026-03-23 | Glassmorphism top nav | `backdrop-filter: blur(20px)` with semi-transparent background; content scrolls beneath nav creating depth |
| 2026-03-23 | Scroll-triggered fade-in animations | IntersectionObserver + staggered delays; adds polish to page load without blocking interaction |
| 2026-03-23 | Grid background texture for Hero | 64px engineering grid with radial mask; reinforces "precision tool" metaphor |
| 2026-03-23 | Primary gradient for Hero title only | `#1677FF → #6C5CE7` gradient strictly limited to Hero display text; everywhere else uses solid primary |
| 2026-03-23 | #FAFAFA warm off-white background (RISK) | Reduces eye strain vs pure white; subtle departure from default Ant Design |
| 2026-03-23 | Restrained color palette | Color is rare and meaningful, not decorative |
| 2026-03-23 | Dark mode: darker base + brighter primary | `#0A0A0B` base instead of `#141414` for more contrast; primary shifts to `#3B8BFF` for readability |
