## Why

The current `docs/agent-evolution.md` points in the right direction, but it is still too broad and underspecified to guide safe implementation. It mixes must-have agent foundations with later-stage enhancements, and it does not yet define durable run state, bounded tool context, or the frontend/test contracts needed to evolve the project from a fixed RAG pipeline into a real agent workflow.

## What Changes

- Narrow the first implementation target from a four-stage roadmap to a minimum viable agent foundation centered on tool calling and a bounded ReAct loop.
- Define durable agent execution state so tool calls and tool results are preserved across refreshes, history views, retries, and debugging.
- Replace the broad `read_document` concept with chunk-oriented read tools that fit the current document and chunk storage model.
- Define a safe UI event model for agent progress that exposes user-appropriate status updates instead of raw model thoughts.
- Add explicit context-budget, timeout, and summarization rules for multi-step tool execution.
- Extend the plan to include frontend state changes, SSE compatibility expectations, and the tests required to support the new workflow.
- Move planning and self-reflection to later enhancements instead of first-wave implementation requirements.

## Capabilities

### New Capabilities
- `agent-runtime-foundation`: Define the minimum viable agent runtime that replaces the fixed one-shot RAG path with tool-based, bounded multi-step execution.
- `agent-run-visibility`: Define how agent runs, steps, and safe progress events are persisted and surfaced to the frontend and test suite.

### Modified Capabilities
- None.

## Impact

- Documentation: `docs/agent-evolution.md`
- New OpenSpec capability specs under `openspec/specs/`
- Backend runtime and schemas, especially the future `agent_runner`, chat persistence, tool wrappers, and SSE event contract
- Frontend chat streaming state, progress rendering, and compatibility handling
- Backend and frontend tests covering tool loops, budgets, persistence, and progress events
