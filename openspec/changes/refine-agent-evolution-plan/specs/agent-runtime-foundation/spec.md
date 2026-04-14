## ADDED Requirements

### Requirement: Agent responses SHALL use bounded tool-based execution
The system SHALL define the first implementation wave of agent evolution as a bounded tool-based runtime that replaces the current one-shot fixed RAG path for the targeted agent flow. The runtime SHALL allow the model to select supported tools, observe results, and continue for a limited number of rounds before producing a final answer or controlled fallback.

#### Scenario: Tool call continues the loop
- **WHEN** the model returns a supported tool call during an agent-enabled chat turn
- **THEN** the system executes the tool, appends the result to the agent context, and performs another bounded decision step instead of ending the turn immediately

#### Scenario: Iteration budget ends the loop
- **WHEN** the runtime reaches the configured maximum iteration count before the model emits a final answer
- **THEN** the system stops the loop and returns a controlled answer or explicit fallback based only on the information gathered so far

### Requirement: Agent tools SHALL fit the current chunk-based document model
The system SHALL define the minimum viable tool set using operations that fit the current repository architecture. The first-wave roadmap MUST include a search tool and a bounded chunk-oriented read tool, and it MUST NOT require implicit full-document summary reads that are not backed by stored data.

The bounded read tool contract for the first wave SHALL be:

`read_chunk_window(chunk_id: str, radius: int = 2) -> list[ChunkResult]`

The arguments SHALL mean:

- `chunk_id`: the anchor chunk selected from prior retrieval output
- `radius`: the number of adjacent chunks to include before and after the anchor chunk, ordered by `chunk_index`, within the same document

The returned window SHALL include the anchor chunk itself plus up to `radius` preceding chunks and up to `radius` following chunks.

#### Scenario: Search tool targets retrievable chunks
- **WHEN** the model requests document search
- **THEN** the system resolves the request through the existing retrieval layer and returns serializable chunk-level results scoped to the permitted documents

#### Scenario: Read tool uses bounded chunk access
- **WHEN** the model requests additional document detail beyond the initial search results
- **THEN** the system uses `read_chunk_window` semantics based on an anchor chunk and symmetric `radius` expansion instead of requiring a whole-document summary read

#### Scenario: Read window respects chunk boundaries
- **WHEN** `read_chunk_window` is called with `chunk_id = X` and `radius = 2`
- **THEN** the system returns chunk `X` plus up to two lower-`chunk_index` neighbors and up to two higher-`chunk_index` neighbors from the same document

### Requirement: Agent execution SHALL enforce context and timeout budgets
The system SHALL define explicit budgets for multi-step execution, including per-tool timeout handling, maximum serialized tool-result size, and summarization or truncation rules when accumulated context exceeds the allowed budget.

#### Scenario: Tool timeout degrades safely
- **WHEN** a tool execution exceeds the configured timeout
- **THEN** the runtime records a bounded failure result and continues or terminates according to documented fallback rules without hanging the chat turn

#### Scenario: Tool results exceed context budget
- **WHEN** accumulated tool observations exceed the configured context budget
- **THEN** the runtime summarizes or truncates prior tool results according to the documented policy before continuing

### Requirement: Planner and reflection SHALL remain outside the first implementation wave
The system SHALL document planning and self-reflection as later enhancements and MUST NOT require them to complete the first implementation wave of agent evolution.

#### Scenario: First-wave roadmap defines later stages explicitly
- **WHEN** the roadmap describes planner or self-reflection features
- **THEN** it marks them as post-foundation enhancements rather than prerequisites for the minimum viable agent runtime
