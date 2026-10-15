# Architecture

## Responsibilities

`ServicePilot` is the application-facing SDK. The API consumes it rather than duplicating its logic. `ToolRegistry` validates arguments and scope before invoking an HTTP, SQLite or document connector. The model receives only three read tools.

The graph performs:

1. Input policy and scope checks.
2. Model/rule-based choice of read tools.
3. Bounded execution loop.
4. Structured diagnosis and canonical citation filtering.
5. Optional immutable ticket proposal.
6. Human decision interrupt.
7. Independently authorized, idempotent write.

The offline engine is a deterministic policy for fixtures, not an LLM. The live engine uses native model tool calls and a separate structured-output call for the final diagnosis.

## Persistence and recovery

| File | Contents |
|---|---|
| `servicepilot.db` | Runs, incidents, immutable proposals, tickets and decision audit |
| `checkpoints.db` | LangGraph state, messages and interrupts |

Proposal JSON is canonicalized and hashed with SHA-256. A decision checks proposal ID, digest, owner, service permission and expiry. Ticket insertion repeats the checks, validates exact content, and uses a unique proposal ID in a transaction.

The SDK serializes graph mutations within one process. Run **one worker and one application instance per data directory**. Horizontal scaling requires shared durable state and distributed coordination.

An approval retry returns the same ticket. A conflicting decision fails. If the app stops after recording approval, the same decision can resume the graph. If it stops after ticket insertion but before checkpoint persistence, the unique proposal ID prevents a second write. General unattended recovery of arbitrary interrupted running tasks is outside scope.

## Retrieval

Each small procedure is one retrieval unit, tagged with its service. Only authorized documents enter a principal's FAISS index. Indexing is rebuilt on startup. Similarity is not treated as calibrated confidence.

`HashEmbedder` uses 1,024-dimensional lexical hashing vectors. `SemanticEmbedder` optionally loads a sentence-transformer. A similarity threshold or a citation is not proof of correctness.

Final citations are resolved against actual retrieved sources. This removes invented IDs, but does not establish that every generated sentence is supported.

## Tradeoffs

- SQLite: minimal setup and durable local state, not distributed coordination.
- Fixed service vocabulary: narrow and inspectable contracts, not an unlimited general agent framework.
- Java standard-library status API: illustrates HTTP interoperability without a large framework.
- Plain browser assets: no frontend build pipeline or dependency tree.
- Text-file prompt versioning: sufficient for this scale; active prompt is `support-v1.txt`.

## Extension points

`StatusConnector` and `Embedder` are protocols. `Settings.procedures_dir` supplies another corpus. Engine adapters implement `next(state)` and `summarize(state)`. A real service integration must retain scope checks and return bounded, validated data.
