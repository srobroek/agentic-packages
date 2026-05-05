---
description: Data ownership, database, pipeline, and notebook steering.
applyTo: "{data/**,**/data/**,**/*.sql,**/*.ipynb}"
---

# Data

Use root `data/` only for shared assets where no single owner exists. Otherwise
keep data with its owning app, service, worker, or library.

Database-specific assets live under `data/database/` for their owner. Use
separate folders for migrations, queries, seeds, fixtures, datasets, pipelines,
notebooks, and warehouse assets.
