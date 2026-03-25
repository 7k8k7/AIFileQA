# QA Report — DocQA (localhost:8080)

**Date:** 2026-03-25
**Duration:** ~25 min
**Pages tested:** 4 (文档管理, 智能问答, 系统设置, all in dark mode + mobile)
**Screenshots:** 12
**Framework:** React 19 + Vite + Ant Design 6 + React Router 7 (SPA)
**Mode:** Full (Standard tier)
**Branch:** main

---

## Summary

| Metric | Value |
|--------|-------|
| Issues found | 4 |
| Fixes applied | 2 (verified) |
| Deferred | 2 (low severity) |
| Health score | 89 → 95 |

---

## Top 3 Things to Fix

1. **[FIXED] Chat sidebar inaccessible on mobile** — Users on mobile (≤768px) couldn't access conversation history, switch conversations, or create new ones. Added hamburger button + slide-out drawer.
2. **[FIXED] Google Fonts not loaded** — DESIGN.md specifies Outfit, JetBrains Mono, and Noto Serif SC but `<link>` tags were missing from `index.html`. All fonts fell back to system stack silently.
3. **[DEFERRED] Document actions menu limited** — Only "Delete" action available. Missing download, preview, rename options.

---

## Issues

### ISSUE-001 — Chat sidebar inaccessible on mobile
- **Severity:** HIGH
- **Category:** Functional / UX
- **Fix Status:** verified
- **Commit:** 48268ae
- **Files Changed:** `frontend/src/pages/Chat/index.tsx`, `frontend/src/pages/Chat/Chat.module.css`
- **Description:** On viewport ≤768px, the chat sidebar (`display: none`) was completely hidden with no hamburger menu, drawer, or any mechanism to access it. Users couldn't view conversation history, switch sessions, or create new conversations.
- **Fix:** Added floating hamburger button (bottom-left), slide-out drawer with overlay backdrop, close button in sidebar header, auto-close on session selection.
- **Before:** `screenshots/mobile-chat.png`
- **After:** `screenshots/mobile-sidebar-open.png`

### ISSUE-002 — Google Fonts link missing from index.html
- **Severity:** MEDIUM
- **Category:** Visual / Design System
- **Fix Status:** verified
- **Commit:** c86026f
- **Files Changed:** `frontend/index.html`
- **Description:** DESIGN.md specifies Outfit (display), JetBrains Mono (code), and Noto Serif SC (serif accent) fonts. CSS variables `--font-display`, `--font-code`, `--font-serif` were correctly defined and used throughout CSS modules, but the Google Fonts `<link>` tags were never added to `index.html`. All fonts silently fell back to system stack.
- **Fix:** Added `preconnect` and Google Fonts stylesheet link to `index.html`.

### ISSUE-003 — Document actions menu only has Delete
- **Severity:** LOW
- **Category:** UX
- **Fix Status:** deferred
- **Description:** The document row action menu (⋯ button) only offers "删除" (Delete). Common actions like download, preview, and rename are missing. Users can upload and delete but cannot download or preview their documents.

### ISSUE-004 — Ant Design deprecation warning
- **Severity:** LOW
- **Category:** Console
- **Fix Status:** deferred
- **Description:** Console shows: `Warning: [antd: Modal] 'destroyOnClose' is deprecated. Please use 'destroyOnHidden' instead.` This is a minor Ant Design v6 migration issue.

---

## Console Health

| Page | Errors | Warnings |
|------|--------|----------|
| 文档管理 | 0 | 0 |
| 智能问答 | 0 | 1 (antd deprecation) |
| 系统设置 | 0 | 0 |

---

## Health Score

| Category | Weight | Before | After |
|----------|--------|--------|-------|
| Console | 15% | 70 | 70 |
| Links | 10% | 100 | 100 |
| Visual | 10% | 85 | 100 |
| Functional | 20% | 80 | 100 |
| UX | 15% | 97 | 97 |
| Performance | 10% | 100 | 100 |
| Content | 5% | 100 | 100 |
| Accessibility | 15% | 97 | 97 |
| **Total** | **100%** | **89** | **95** |

---

## Pages Tested

| Page | URL | Status | Notes |
|------|-----|--------|-------|
| 文档管理 | /documents | OK | Search, upload area, document list all functional |
| 智能问答 | /chat | OK (after fix) | Chat works, streaming responses, session management |
| 系统设置 | /settings | OK | Provider config, connection test, edit/delete |
| Dark mode | all pages | OK | Colors match DESIGN.md (`#0A0A0B` bg verified) |
| Mobile (375px) | /documents | OK | Responsive layout adapts well |
| Mobile (375px) | /chat | OK (after fix) | Sidebar now accessible via drawer |

---

## PR Summary

QA found 4 issues, fixed 2, health score 89 → 95.
