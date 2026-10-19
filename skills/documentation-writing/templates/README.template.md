<!-- For a human, read years later by someone who has forgotten everything. Diagrams, not prose (prose ≤ ~150 words). Entities only: files, folders, arrows, status — never a rule or a tunable number (those live in AGENTS.md). -->
<!-- Only when there is nothing to draw: otherwise a README.html instead (templates/README.template.html), never both. -->

# <project-name>

**<One line: what this does, for whom.>**

## The big picture

```mermaid
flowchart LR
    A["1_ingest<br/><code>ingest.py</code>"] -- "raw.csv" --> B["2_process<br/><code>process.py</code>"]
    B -- "clean.parquet" --> C["3_report<br/><code>report.py</code>"]
    classDef live fill:#d4edda,stroke:#28a745
    classDef broken fill:#f8d7da,stroke:#dc3545
    classDef planned fill:#eeeeee,stroke:#999999,stroke-dasharray: 4 3
    class A,B live
    class C planned
```

<sub>green = live · red = broken · dashed = planned</sub>

## Folder map

```
<project-name>/
├── AGENTS.md          rules for agents (Claude and Codex)
├── doc/               companion files for the code
└── src/               …
```

---
Rules for agents: [`AGENTS.md`](AGENTS.md)
