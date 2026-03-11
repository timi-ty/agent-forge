# Ownership Model

Three ownership classes govern what the harness controls vs. what the project owns. Ownership is explicit and tracked in `manifest.json`.

---

## 1. Harness-Owned

| Property | Description |
|----------|-------------|
| **Definition** | Created and fully controlled by the harness. |
| **/clear behavior** | `/clear` removes these files. |
| **Modification** | Only the harness may modify them. User edits should be flagged by sync. |
| **Examples** | `.harness/state.json`, `.harness/config.json`, `.harness/manifest.json`, `.harness/phase-graph.json`, `.harness/checkpoint.md`, `.harness/ARCHITECTURE.md`, `.harness/scripts/*`, `.harness/plans/*`, `.harness/issues/*`, `.harness/PHASES/*` |

---

## 2. Product-Owned

| Property | Description |
|----------|-------------|
| **Definition** | May be scaffolded by the harness during `create`, but immediately become the project's responsibility. |
| **/clear behavior** | `/clear` NEVER touches these. |
| **Modification** | The harness may read them but never modify without explicit user approval. |
| **Examples** | `.github/workflows/`, `tests/e2e/`, `ROADMAP.md`, all application source (e.g., `src/`, `app/`, `lib/`), `package.json`, `requirements.txt` |

---

## 3. Managed-Block

| Property | Description |
|----------|-------------|
| **Definition** | Content injected into a pre-existing file using markers. |
| **Markers** | `<!-- HARNESS:START -->` ... `<!-- HARNESS:END -->` |
| **/clear behavior** | `/clear` removes only the marked block; the rest of the file is untouched. |
| **Use case** | When the harness must add content to an existing user-owned file (e.g., pre-existing `AGENTS.md`). |
| **Tracking** | Manifest includes `marker_pattern` field for each managed block. |

---

## Ownership Rules

| Rule | Description |
|------|-------------|
| **No silent transition** | A harness-owned file NEVER becomes product-owned silently. |
| **Sync flags drift** | If the user modifies a harness-owned file, sync should flag it. |
| **Product stays product** | Product-owned files NEVER become harness-owned. |
| **Managed blocks** | Only the content between markers is harness-controlled; the rest of the file is product-owned. |
