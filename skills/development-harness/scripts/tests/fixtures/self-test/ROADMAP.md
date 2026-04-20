# Tasklet — a tiny CRUD task tracker

Tasklet is a minimal task-tracking API with two resources: **Items** (the tasks) and **Users** (the people who create them). This roadmap is deliberately small — two phases, six units — but shaped to exercise every interesting edge of the harness's parallel execution machinery.

## Milestones

### Items

Create, read, update, and delete tasks. Every Item has an owner (a `user_id` foreign key) and a `status` enum (`todo | in_progress | done`). Items are persisted via a thin SQL-ish model layer and exposed through a REST route tree mounted on the app router.

The Items milestone covers three independent pieces of work: the data model (schema + migration), the route layer (handlers + the router registration), and a bulk-action endpoint that groups items by status.

### Users

Create, read, update, and delete users. Users have `email`, `display_name`, and `created_at`. The Users milestone covers three independent pieces of work: the data model, the route layer (handlers + router registration), and seed data loaded at app boot.

## Out of scope (deliberately)

- Auth, sessions, JWT — none of it. A `user_id` in the URL is the trust boundary.
- Pagination, sorting, filtering — assume small tables.
- Observability (metrics, traces) — not this roadmap.
- UI — API-only.
- Deploy target — this project's `.harness/` will configure `deployment.target` as `"none"`.

## Why this shape

Tasklet is a **self-test fixture** for the harness. The two phases and six units are not arbitrary — they're seeded to produce specific harness behaviors when run through `/invoke-development-harness` with parallelism enabled. See [README.md](./README.md) in the same directory for the full list of seeded conditions and what each unit is expected to exercise.
