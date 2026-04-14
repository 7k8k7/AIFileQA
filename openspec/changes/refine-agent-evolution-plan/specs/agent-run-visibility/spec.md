## ADDED Requirements

### Requirement: Agent runs and steps SHALL be durably queryable
The system SHALL require durable storage for agent runs and agent steps, or an equivalent persistence model, so that tool activity and intermediate execution state can be inspected after the live stream ends.

#### Scenario: Refresh preserves execution history
- **WHEN** a user refreshes the chat page after an agent turn has already executed tool steps
- **THEN** the system can recover the persisted run and step data needed to show what happened during that turn

#### Scenario: Regeneration can inspect prior activity
- **WHEN** a later workflow such as regeneration or debugging needs to inspect the previous agent turn
- **THEN** the system can query the persisted tool calls and results without depending on transient in-memory state

### Requirement: User-facing progress events SHALL expose safe status, not raw internal thought
The system SHALL define user-facing SSE events for agent progress using safe, status-oriented payloads. The documented event model MUST NOT require exposing raw internal thought text as part of the product contract.

The minimum first-wave payload contract for `agent_status` SHALL be:

- `type`: fixed string `agent_status`
- `status`: one of `searching`, `reading`, or `answering`
- `round`: integer round number starting at `1`
- `tool`: `search_documents`, `read_chunk_window`, or `null`

#### Scenario: Tool activity is visible through safe events
- **WHEN** the runtime starts and completes a supported tool call
- **THEN** the system emits documented progress events that identify the action and result summary without revealing raw hidden reasoning

#### Scenario: Agent status payload matches the first-wave contract
- **WHEN** the runtime emits a progress event before or during a round
- **THEN** the payload matches the documented `agent_status` structure, such as `{"type":"agent_status","status":"searching","round":1,"tool":"search_documents"}`, `{"type":"agent_status","status":"reading","round":2,"tool":"read_chunk_window"}`, or `{"type":"agent_status","status":"answering","round":3,"tool":null}`

#### Scenario: Final answer remains compatible with existing chat flow
- **WHEN** the runtime completes an agent turn
- **THEN** the system still emits answer, completion, and error events in a way that preserves a clear final-response contract for the chat UI

### Requirement: The roadmap SHALL include frontend and test obligations for agent visibility
The system SHALL document the frontend state changes and test coverage needed to support persisted runs and safe progress events.

#### Scenario: Frontend state changes are explicitly documented
- **WHEN** the roadmap introduces new agent progress or persistence behavior
- **THEN** it also identifies the chat UI state, rendering, and compatibility work required to consume that behavior

#### Scenario: Tests cover visibility behavior
- **WHEN** the roadmap defines durable run visibility and progress events
- **THEN** it includes backend and frontend test requirements for event handling, persistence, and degraded cases
