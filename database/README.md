# Database operations

PostgreSQL 16 is the production target. Docker Compose applies `sql/01_schema.sql` and `sql/02_views.sql` on a new volume. For an existing environment use a migration tool and review changes before deployment.

Applications write through a dedicated service role. Copilot queries must use `insightops_readonly`, which receives `SELECT` only on the five approved views. Configure a statement timeout of eight seconds and an application row limit of 200.

