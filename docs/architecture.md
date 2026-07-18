# Architecture decisions

- **Canonical schema:** isolates changing source names from business logic.
- **Quarantine before metrics:** a rejected row never silently affects a KPI.
- **Metric catalog:** keeps Python, SQL and BI definitions aligned.
- **Explainable detection:** robust statistics and rules are the default; black-box methods are optional evidence, not sole decision makers.
- **Provider boundary:** optional LLM integration implements a narrow interface and cannot weaken controls.
- **Append-only audit:** events include a canonical SHA-256 hash for tamper-evident export.
- **Human state machine:** reports move through explicit transitions; direct Draft-to-Published is impossible.

