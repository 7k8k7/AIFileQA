## 1. Align the roadmap scope

- [ ] 1.1 Review `docs/agent-evolution.md` against the new proposal, design, and capability specs
- [ ] 1.2 Rewrite the evolution goals and stage breakdown so Stage 1 and Stage 2 are the only first-wave requirements
- [ ] 1.3 Reposition planner and reflection as later enhancements instead of first-wave deliverables

## 2. Strengthen the runtime design in the document

- [ ] 2.1 Replace the broad `read_document` tool definition with a chunk-oriented bounded read tool that fits the current storage model
- [ ] 2.2 Add durable run/step persistence requirements for agent execution history and debugging
- [ ] 2.3 Add explicit iteration, timeout, and context-budget rules for multi-step tool execution

## 3. Strengthen UI and testing contracts

- [ ] 3.1 Replace raw `thought` exposure with safe status-oriented progress events in the roadmap
- [ ] 3.2 Add frontend state and SSE compatibility expectations for the new agent progress model
- [ ] 3.3 Add backend and frontend test expectations for persistence, event handling, and degraded cases

## 4. Validate the revised plan

- [ ] 4.1 Verify the updated roadmap is consistent with the `agent-runtime-foundation` and `agent-run-visibility` specs
- [ ] 4.2 Confirm the revised document clearly separates minimum viable agent requirements from future enhancements
