# Data Context

Use this context for data ownership, database assets, migrations, queries,
seeds, fixtures, datasets, pipelines, notebooks, warehouses, and analytics
material.

Use root `data/` only for shared assets where no single owner exists. Otherwise
keep data with its owning app, service, worker, or library.

Database-specific assets live under the owner's `data/database/` folder. Use
separate folders for migrations, queries, seeds, fixtures, datasets, pipelines,
notebooks, and warehouse assets.

Keep notebooks and exploratory data close to the owning domain unless the
project deliberately maintains a shared data science workspace.
