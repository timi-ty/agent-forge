# Cyclomatic Complexity Reference

Owns every number, cause name, and priority the complexity pass uses; the [checklist](checklist.md) `## Complexity` items are the code properties this file makes checkable.

---

## Counting rules

Cyclomatic complexity (CC) of a function = the number of independent paths through it. Estimate it by reading:

1. Start at **1** for the function body.
2. Add **1** for each of:
   - `if`, `elif` / `else if`
   - conditional expression / ternary (`a if c else b`, `c ? a : b`)
   - loop: `for`, `while`, `do ... while`, `for ... of/in`, and a comprehension or generator `if` filter
   - each non-default `case` / `when` branch in a `switch` / `match` / `when` / `select`
   - `catch` / `except` / `rescue` clause
   - each `&&`, `||`, `and`, `or` inside a condition (they are short-circuit branches)
3. Add **nothing** for: `else`, `default` / `case _`, `finally`, `return`, `throw` / `raise`, `break`, `continue`, recursion, and null-safe operators (`?.`, `??`, `or default`) used purely to supply a default value.

Language notes:
- Python `match`: a guard on a case (`case X if cond`) adds +1 beyond the case itself.
- TypeScript / JavaScript `switch`: +1 per `case` label, including fall-through labels, because each is a distinct entry path.

**Nesting depth**: the deepest chain of control-flow blocks (`if` / loop / `try` / `switch`) inside the body. Statements at the top level of the function are depth 0; each enclosing block adds 1. A `for` containing an `if` containing a `try` is depth 3.

**Unit of audit**: a named function or method, or an anonymous function containing at least one decision point. Code inside documentation or fenced examples is not audited.

**Modified functions**: read the function as it stands after the PR from the head ref Phase 3 fetched (`git show pr-<N>:<path>`, or `$HEAD_WT/<path>` when that worktree exists) and count it as for an added function. For a row that is assigned a priority, also count the base body from `$REVIEW_BASE` so the cell reads `base -> PR`.

### Worked example

```python
def resolve_price(order, user):                 # 1
    if order is None:                           # +1 -> 2
        raise ValueError("order required")
    price = order.base
    for item in order.items:                    # +1 -> 3   (depth 1)
        if item.discounted and user.is_member:  # +1 (if) +1 (and) -> 5   (depth 2)
            price -= item.discount
    return price if price > 0 else 0            # +1 -> 6
```

Estimated CC 6, nesting depth 2. No signal below matches, so neither recorded nor a finding.

---

## Finding signals

Audit every function the diff adds or modifies, **as it stands after the PR**. Functions the PR does not touch are never flagged, however bad they are -- the review is of this PR, not the codebase. A function that matches no row below is not recorded.

| Signal | Reading | Priority |
|--------|---------|----------|
| CC 11-15 | Refactoring signal. | Low |
| CC > 15 | Avoid. | Medium |
| Nesting depth >= 4 | Hard to hold in your head regardless of CC. | Medium |
| Branch hidden behind indirection | Catalog entry below; Medium because it is a regression this PR introduced. | Medium |
| Any other catalog cause | A named structural cause; its entry's transformation is the fix. | Low |

### Complexity notes

Record a row for every function that matches a signal. `Priority` is the highest matched signal, or `--` when the catalog rule below yields no usable transformation. Rows with a priority are findings, and every one names a cause.

| Function | File:line | Est. CC | Nesting | Dominant cause | Priority |
|----------|-----------|---------|---------|----------------|----------|
| `function name` | `path/to/file:line` | [n; `base -> PR` for a modified function with a priority] | [n, same form] | [cause name, with `(on <merge key>)` where the catalog requires it] | Medium / Low / -- (reason) |

### Finding format

A complexity finding follows the Phase 7 output rules and additionally names the function, the estimated CC and nesting depth, and the dominant cause and its transformation. Never write "this looks complex" -- the count and the cause are the finding.

```markdown
- **`src/billing/invoice.ts:42`** -- `applyDiscounts` is est. CC 12 -> 17, nesting 3 -> 4 (nested preconditions). Guard clauses: convert the four precondition checks to early returns; the main loop then sits at depth 1.
```

---

## Cause -> transformation catalog

One entry per dominant cause and the transformation that removes it. Rank the matching per-function entries by Finding signals priority, then by the number of decision points each covers; walk them in that order and take the first whose transformation passes its Not-when and the Guardrails as `Dominant cause`. If the walk exhausts, the row takes `--` and names the entry and the clause that failed. If no entry matches, the branching is inherent and the row takes `--`. A `--` row keeps the failed entry's cause name in `Dominant cause` and the failed clause in `Priority`; an inherent row leaves `Dominant cause` empty and states why in `Priority`. Use the heading's cause name in the column.

### Per-function entries (Phase 4)

#### Nested preconditions -> Guard clauses

Looks like: precondition checks whose failure branch exits (return, raise, error) wrap the main operation in successive `if` blocks.

```python
# before
if user:
    if user.is_active:
        if user.has_permission:
            return perform_action(user)
        else:
            return error
    else:
        return error
else:
    return error

# after
if not user:
    return error

if not user.is_active:
    return error

if not user.has_permission:
    return error

return perform_action(user)
```

Not when: the "failure" branches each do substantive, different work.

#### Nested sequential checks -> Flatten nested conditionals

Looks like: nesting that exists only because two independent checks with no failure branch were written separately, guarding one statement.

```python
# before
if order.paid:
    if order.shipped:
        notify(order)

# after
if order.paid and order.shipped:
    notify(order)
```

Not when: flattening forces you to duplicate a condition elsewhere.

#### Long conditional chain or duplicated branches -> Replace the chain with data

Looks like: `if / elif / else` or a `switch` of three or more branches selecting behavior by a value; branches identical except for a value or call target; or a ladder of thresholds that is really configuration. Three shapes:

Value -> handler:

```ts
// before
function handler(kind: Kind) {
  if (kind === "create") return onCreate;
  else if (kind === "update") return onUpdate;
  else if (kind === "delete") return onDelete;
  else if (kind === "archive") return onArchive;
  throw new Error(`unknown kind ${kind}`);
}

// after
const HANDLERS: Record<Kind, Handler> = {
  create: onCreate,
  update: onUpdate,
  delete: onDelete,
  archive: onArchive,
};

function handler(kind: Kind) {
  const h = HANDLERS[kind];
  if (!h) throw new Error(`unknown kind ${kind}`);
  return h;
}
```

Value -> parameter:

```python
# before
if env == "prod":
    client = Client(url=PROD_URL, retries=3)
elif env == "staging":
    client = Client(url=STAGING_URL, retries=3)
else:
    client = Client(url=DEV_URL, retries=3)

# after
client = Client(url=URLS[env], retries=3)
```

Ordered thresholds -> value:

```python
# before
if score >= 90: grade = "A"
elif score >= 80: grade = "B"
elif score >= 70: grade = "C"
else: grade = "F"

# after
GRADE_BANDS = [(90, "A"), (80, "B"), (70, "C")]

grade = next((g for floor, g in GRADE_BANDS if score >= floor), "F")
```

When the chain selects on a discriminator (the first two shapes), append the merge key to the cause cell -- `Long conditional chain or duplicated branches (on shape.kind)` -- so Phase 6 can group sites on the same discriminator.

Not when: the branches share intermediate state; the rules have side effects or ordering dependencies a table would hide; or the branches only coincide today and are documented to diverge.

#### Compound boolean -> Extract predicate

Looks like: a condition with three or more `&&` / `||` terms, often mixing unrelated concerns.

```python
# before
if user.plan == "pro" and not user.suspended and user.seats_used < user.seats_total:
    grant_seat(user)

# after
if can_add_seat(user):
    grant_seat(user)
```

The predicate has the same CC; the win is that the caller now has one concept to reason about, and the predicate is testable in isolation.

Not when: the name would only restate the expression (`is_a_and_b`). If you cannot name the concept, the condition may be fine as it is.

#### Several jobs in one function -> Split by responsibility

Looks like: independent decisions about unrelated concerns (validate, parse, persist, notify) in one body, or more decisions than one concern accounts for.

```python
# before
def handle_upload(req):
    if not req.file:
        return error("no file")
    if req.file.size > MAX_SIZE:
        return error("too large")
    if req.file.kind == "csv":
        rows = parse_csv(req.file)
    else:
        rows = parse_json(req.file)
    db.save(rows)
    if req.notify:
        send_email(req.user, len(rows))

# after -- each helper owns one concern's decisions; the orchestrator is straight-line
def handle_upload(req):
    file = validate_upload(req)
    rows = parse_rows(file)
    db.save(rows)
    notify_if_requested(req, rows)
```

Not when: the pieces read and write many locals of the enclosing function -- the extracted function would need a wide parameter list or an out-parameter, which is worse than the original.

#### Boolean mode flag -> Split the function

Looks like: a parameter such as `dry_run`, `strict`, `as_json` that steers into substantially different execution paths.

```python
# before
def export(data, as_json=False):
    if as_json:
        ...  # 12 lines
    else:
        ...  # 14 lines

# after
def export_json(data): ...
def export_csv(data): ...
```

Not when: the two paths share most of their body -- splitting would duplicate it.

#### Branch hidden behind indirection -> Inline the branch

Looks like: a refactor in this PR whose result fails a Guardrail.

```python
# the PR replaced this ...
if user.is_admin:
    show_admin_panel()

# ... with this
ADMIN_ACTIONS = {True: show_admin_panel, False: lambda: None}
ADMIN_ACTIONS[user.is_admin]()

# inline the branch
if user.is_admin:
    show_admin_panel()
```

Not when: the indirection is reused from several call sites.

### Cross-function entries (Phase 6)

Phase 6 groups rows by merge key; two or more rows on one key become a single finding under the entry below, replacing those rows, with the highest signal among them as its Priority. If Polymorphism fails a Guardrail, leave the rows unmerged.

#### Type switch repeated across functions -> Polymorphism

Looks like: several functions each switch on the same discriminator (the merge key); a single dispatch site is a map (above), and a class hierarchy for one switch is excessive indirection.

```python
# before -- three functions each do `if shape.kind == "circle": ... elif "rect": ...`
def area(shape): ...
def perimeter(shape): ...
def bounding_box(shape): ...

# after -- one class per kind owns its three behaviors
class Circle:
    def area(self): ...
    def perimeter(self): ...
    def bounding_box(self): ...
```

---

## Guardrails

Do not optimize the number blindly. A transformation is wrong -- and the slightly higher-complexity implementation is the correct one -- when the result would be:

- **harder to read than the branch it replaced**: an abstraction, indirection, class, or helper with no name a caller can reason about on its own -- it exists only to move the branch out of view
- **slower in a performance-critical path**
- **harder to debug**: the failure site no longer shows which decision selected the path
