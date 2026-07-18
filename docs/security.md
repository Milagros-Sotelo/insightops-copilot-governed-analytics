# Copilot security model

The Copilot never receives raw database access. It operates over five approved views and validates every SQL statement before execution. A production executor must also use the `insightops_readonly` PostgreSQL role, statement timeout and row limit.

Uploaded text is data, never an instruction channel. Known injection patterns are removed or rejected. Provider prompts keep system instructions separate from curated JSON context. Responses must expose source, period, metric IDs and SQL; when evidence is missing, the correct outcome is an explicit refusal to guess.

Human control is a separate boundary: the Copilot can draft and explain but cannot approve, publish, pay, delete or update operational records.

