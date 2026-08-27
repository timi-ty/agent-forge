# Cyclomatic Complexity Reference

Owner of every number, cause name, and priority the complexity pass uses: Phase 4 (complexity notes), Phase 7 (priority of complexity findings), and Phase 9 (applying a transformation). The [checklist](checklist.md) `## Complexity` section says *what* to check; this file defines *how* to count, *when* a function is a finding, and *which* transformation applies.

The objective is to minimize the number of independent execution paths a reader must reason about while keeping the code explicit, cohesive, and easy to test. A lower number is the side effect, not the goal.

---

## Counting rules

Cyclomatic complexity (CC) of a function = the number of independent paths through it. Estimate it by reading:

1. Start at **1** for the function body.
2. Add **1** for each of:
   - `if`, `elif` / `else if` (plain `else` adds nothing)
   - conditional expression / ternary (`a if c else b`, `c ? a : b`)
   - loop: `for`, `while`, `do ... while`, `for ... of/in`, and a comprehension or generator `if` filter
   - each non-default `case` / `when` branch in a `switch` / `match` / `when` / `select`
   - `catch` / `except` / `rescue` clause
   - each `&&`, `||`, `and`, `or` inside a condition (they are short-circuit branches)
3. Add **nothing** for: `else`, `default`, `finally`, `return`, `throw` / `raise`, `break`, `continue`, recursion, and null-safe operators (`?.`, `??`, `or default`) used purely to supply a default value.

Language notes:
- Python `match`: `case _` adds nothing. A guard on a case (`case X if cond`) adds +1 more.
- TypeScript / JavaScript `switch`: +1 per `case` label, including fall-through labels, because each is a distinct entry path.

**Nesting depth**: the deepest chain of control-flow blocks (`if` / loop / `try` / `switch`) inside the body. Statements at the top level of the function are depth 0; each enclosing block adds 1. A `for` containing an `if` containing a `try` is depth 3.

**Measured numbers.** Use a linter's numbers instead of a hand estimate only when both hold: the repository already configures a complexity rule (eslint `complexity`; `max-complexity` / `C901` in `.flake8`, `setup.cfg`, `ruff.toml` or `pyproject.toml`; `gocyclo` in `.golangci.yml`; `Metrics/CyclomaticComplexity` in `.rubocop.yml`), and the PR head worktree already exists with dependencies installed. Otherwise hand-estimate. Never install tooling to get a number. Say above the complexity notes when linter numbers were used.

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

Estimated CC 6, nesting depth 2. In the 6-10 band and no cause from the catalog below applies, so not a finding -- the branching is the domain.

---

## Thresholds

Estimate every function the diff adds or modifies, **as it stands after the PR**. Functions the PR does not touch are never flagged, however bad they are -- the review is of this PR, not the codebase. When the PR moved a function into a higher band, cite the pre-PR estimate too.

| Estimated CC or nesting | Reading | Priority |
|-------------------------|---------|----------|
| CC <= 5 | Target for new code. | Not a finding. Counted, not tabulated. |
| CC 6-10 | Acceptable when the domain genuinely requires that many cases. | Not a finding unless a catalog cause applies (then Low). Record the row. |
| CC 11-15 | Refactoring signal. | **Low** -- nice to fix. |
| CC > 15 | Avoid unless there is a strong, stated reason. | **Medium** -- maintainability concern; should fix. |
| Nesting depth >= 4 | Hard to hold in your head regardless of CC. | **Medium** |

A function in any band that shows a cause from the catalog below, where the transformation clears the guardrails, is a **Low** finding. A row marked `Domain-justified? Yes` is not a finding regardless of its band (see Guardrails).

The Phase 4 complexity notes get a row for every function at CC >= 6, nesting >= 4, or showing a catalog cause. Functions in the target band are only counted.

### Finding format

A complexity finding is written like every other finding: bold file path and line, the function, the estimated CC and nesting depth, the dominant cause, and the transformation named by its catalog heading. Never write "this looks complex" -- the count and the cause are the finding.

```markdown
- **`src/billing/invoice.ts:42`** -- `applyDiscounts` is est. CC 17, nesting 4 (deep nesting). Guard clauses: convert the four precondition checks to early returns; the main loop then sits at depth 1.
```

---

## Cause -> transformation catalog

One entry per dominant cause -- the structural reason most of a function's paths exist -- and the transformation that removes it. Use the heading's cause name in the `Dominant cause` column and its transformation name in the `Transformation` column. Each entry gives what the cause looks like, a compact before / after, and when **not** to apply the transformation.

### Deep nesting -> Guard clauses

Looks like: precondition checks wrap the main operation in successive `if` blocks.

Prefer:

```python
if not user:
    return error

if not user.is_active:
    return error

if not user.has_permission:
    return error

return perform_action(user)
```

over:

```python
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
```

Not when: the "failure" branches each do substantive, different work. That is a chain (see below), not validation.

### Repeated conditions -> Flatten nested conditionals

Looks like: the same predicate (or its negation) is tested in several places, or nesting exists only because two checks were written separately.

```python
# before
if order.paid:
    if order.shipped:
        notify(order)

# after
if order.paid and order.shipped:
    notify(order)
```

Not when: flattening forces you to duplicate a condition elsewhere, or the inner check has its own `else` that must stay distinct.

### Long conditional chain or duplicated branches -> Replace the chain with data

Looks like: `if / elif / else` or a `switch` selecting behavior by a value; branches identical except for a value or call target; or a ladder of thresholds that is really configuration. Three shapes:

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

Not when: there are only two or three branches; the branches share intermediate state; the rules have side effects or ordering dependencies a table would hide; or the branches only coincide today and are documented to diverge.

### Type switch repeated across functions -> Polymorphism

Looks like: several functions each switch on the same discriminator.

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

Not when: the switch exists in one place. A single dispatch site is a map (above); a class hierarchy for one switch is excessive indirection.

### Compound boolean -> Extract predicate

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

### Several jobs in one function -> Split by responsibility

Looks like: independent decisions about unrelated concerns (parse, validate, persist, notify) in one body -- often a loop whose body carries most of the function's decisions.

```python
# before
for row in rows:
    if row.skip: continue
    if row.kind == "a": ...
    elif row.kind == "b": ...
    ...

# after
for row in rows:
    process_row(row)
```

Not when: the pieces read and write many locals of the enclosing function -- the extracted function would need a wide parameter list or an out-parameter, which is worse than the loop.

### Boolean mode flag -> Split the function

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

Not when: the flag toggles one small step inside an otherwise shared path. Then keep the flag; two near-identical functions are the duplicated-branches cause.

---

## Guardrails

Apply exactly one transformation per finding; if a second is needed, that is a second finding. Do not optimize the number blindly. A transformation is wrong -- and the slightly higher-complexity implementation is the correct one -- when the result would be:

- **harder to read than the branch it replaced**: an abstraction, an indirection, a class or pattern, or a helper that exists only to move a branch out of view
- **slower in a performance-critical path**
- **harder to debug**: a stack trace through a dispatch table is less obvious than a visible `if`

`Domain-justified? Yes` in the complexity notes means the branching is inherent to the problem, or every applicable transformation would fail one of these tests. State the reason in the row; a justified row is not a finding regardless of its band.

When applying a transformation in Phase 9: preserve behavior exactly, re-estimate CC after the edit, and state in the commit message which branching or responsibility was removed or isolated -- not just the new number.
