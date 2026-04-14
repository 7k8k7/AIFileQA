## Context

The current project answers questions through a fixed pipeline: resolve document scope, retrieve chunks, build a prompt, and make one model call. The existing `docs/agent-evolution.md` already identifies the limits of that approach, but the roadmap is still too broad for a first implementation pass. It combines essential agent foundations with later optimization ideas, and it leaves several implementation-critical constraints implicit:

- the current chat persistence model only stores `user` and `assistant` messages
- document storage is chunk-centric, not summary-centric
- frontend streaming currently understands only answer, source, and error events
- multi-step execution would exceed current context handling unless budgets and summarization are defined

The revised plan needs to become implementation-ready without pretending the full roadmap belongs in the first delivery.

## Goals / Non-Goals

**Goals:**
- Define a minimum viable agent architecture that is sufficient to classify the system as an agent-based workflow.
- Make the first-wave design fit the current repository shape, especially chunk retrieval, chat persistence, and SSE streaming.
- Introduce durable execution state so tool activity survives refreshes, retries, and debugging.
- Define safe user-facing progress events and the frontend/test work needed to support them.
- Preserve a clear growth path for planner and reflection stages without forcing them into the first implementation.

**Non-Goals:**
- Implement planner-driven decomposition in the first wave.
- Implement self-reflection, answer scoring, or automatic retry in the first wave.
- Expose raw chain-of-thought or unrestricted internal reasoning text to end users.
- Replace the current provider abstraction or require a single-model-only backend design.

## Decisions

### Decision: First-wave scope is limited to tool calling plus a bounded ReAct loop

The revised roadmap SHALL treat Stage 1 and Stage 2 as the minimum viable agent foundation. That means the first implementation wave focuses on:

- model-directed tool selection
- bounded action/observation loops
- controlled stop conditions
- final answer streaming after the loop completes

Planner and reflection remain explicit future enhancements instead of blocking requirements for the first implementation.

Alternatives considered:
- Keep the four-stage roadmap as-is: rejected because it hides the real implementation minimum and raises prompt, latency, and testing complexity too early.
- Only add one-shot function calling without a loop: rejected because it still leaves the system too close to a fixed RAG pipeline.

### Decision: Persist agent execution as first-class run and step records

The revised plan SHALL require durable storage for agent runs and agent steps rather than keeping tool activity only in transient in-memory context. In the first implementation wave, that durability SHALL be achieved by extending the existing chat persistence model instead of creating separate `agent_runs` and `agent_steps` tables.

The design baseline for the first wave is:

- keep `ChatSession` as the top-level execution container
- extend `ChatMessage` with agent/tool metadata so tool activity is queryable alongside user and assistant turns
- store tool call details and tool result summaries in chat persistence so refresh, debugging, and later replay decisions do not depend on in-memory state

This keeps the schema change small and fits the current repository better than introducing a second run-tracking subsystem before the first agent loop is proven out.

The documentation SHALL still require that persisted execution data supports:

- refresh-safe progress recovery
- history inspection
- debugging and support
- regeneration or replay decisions based on actual prior tool activity

Alternatives considered:
- Dedicated `agent_runs` and `agent_steps` tables: rejected for the first wave because they add migration and query complexity before the minimum viable runtime is stable.
- Store only final assistant output and discard tool steps: rejected because the project would still behave like a black-box chat app.
- Emit tool steps only over SSE: rejected because refreshes and later inspection would lose the execution trail.

### Decision: Replace broad document reads with chunk-oriented read tools

The revised plan SHALL replace `read_document(doc_id, page)` with tools that fit the current chunk model, such as:

- `search_documents(query, doc_ids, top_k)`
- `read_chunk_window(chunk_id, radius)`
- `request_clarification(question)`

For the first wave, `read_chunk_window` SHALL mean:

- `chunk_id` is the anchor chunk selected from prior retrieval output
- `radius` defaults to `2`
- the runtime reads the anchor chunk plus up to `radius` adjacent chunks before and after it, ordered by `chunk_index`, within the same document

This avoids introducing an implied full-document summary store that the current backend does not have while still giving the model a deterministic way to zoom in on local context.

Alternatives considered:
- Keep `read_document` with “full summary” semantics: rejected because it assumes a summary cache that does not exist.
- Re-parse full source documents inside the agent loop: rejected because it is expensive and misaligned with current retrieval architecture.

### Decision: User-facing progress is event-safe and status-oriented

The revised plan SHALL forbid exposing raw internal thought text as a product event. Instead, it SHALL define safe status events such as:

- `agent_status` or equivalent high-level progress markers
- `tool_call`
- `tool_result`
- existing `token`, `sources`, `done`, and `error`

The frontend should communicate what the agent is doing without surfacing hidden reasoning or unstable prompt internals.

The minimum first-wave `agent_status` contract is:

- `{"type":"agent_status","status":"searching","round":1,"tool":"search_documents"}`
- `{"type":"agent_status","status":"reading","round":2,"tool":"read_chunk_window"}`
- `{"type":"agent_status","status":"answering","round":3,"tool":null}`

The first-wave UI SHALL render these as live progress only. Historical step data is still persisted, but completed-run step traces are not yet rendered in the chat UI.

Alternatives considered:
- Stream raw `thought` content to the UI: rejected because it is unstable, hard to productize, and inappropriate as a user contract.
- Hide all intermediate activity: rejected because the new loop would otherwise feel opaque and harder to trust.

### Decision: Multi-step execution must include explicit budgets and degradation rules

The revised plan SHALL define:

- maximum iteration count
- per-tool timeout limits
- maximum serialized tool-result size per round
- summarization or truncation rules when accumulated context exceeds budget
- controlled fallback behavior when a tool fails or the loop reaches its budget

These rules are required because the current chat context trimming only addresses conversation history and does not cover repeated tool observations.

Alternatives considered:
- Append all tool results verbatim into context: rejected because it will become slow, expensive, and fragile.
- Leave budgeting as a later implementation detail: rejected because it changes core behavior and error handling.

### Decision: The revised plan must include frontend and test contracts

The updated roadmap SHALL include the downstream work needed to support the agent flow:

- frontend state additions for progress events and step visibility
- SSE compatibility expectations
- backend tests for tool dispatch, loop bounds, timeout handling, and persistence
- frontend tests for progress rendering and event handling

Alternatives considered:
- Keep the roadmap backend-only: rejected because the current frontend only handles a narrower event set and would fall out of sync immediately.

## Risks / Trade-offs

- [More durable execution state increases schema and API complexity] -> Keep the first-wave data model minimal and focused on queryable run/step metadata.
- [Bounding tool results may reduce raw evidence available to the model] -> Require summarization/truncation rules and preserve full raw results in durable storage when needed.
- [Progress events can add frontend complexity] -> Limit first-wave events to a small, explicit set and require graceful handling of unknown events.
- [Deferring planner and reflection may disappoint roadmap expectations] -> State clearly that they remain later stages after the minimum viable agent foundation is stable.

## Migration Plan

1. Revise `docs/agent-evolution.md` to reflect the narrowed first-wave scope and the new durability, safety, and testing requirements.
2. Add OpenSpec capability specs for the agent runtime foundation and run visibility requirements.
3. Use the revised plan as the only approved baseline for a later `/opsx:apply` implementation pass.
4. Keep the current fixed RAG path available as an explicit fallback until the agent runtime is implemented and verified.

## Provider Rollout Decision

The first implementation wave SHALL enable agent execution only for providers that satisfy all of the following:

- `provider_type` is `openai`, `openai_compatible`, or `claude`
- `last_test_success` is `True`
- the deployment is known to support tool calling end-to-end

Adapter-proxy-backed deployments are treated as unsupported for the first wave and SHALL fall back to the current fixed RAG path until explicit capability detection or dedicated support is added.
