# Cyclomatic Complexity Reference

Method for the complexity pass in Phase 4 (complexity notes), the severity mapping in Phase 7 (output), and the refactors applied in Phase 9 (plan to address issues). The [checklist](checklist.md) `## Complexity` section lists *what* to look for; this file defines *how* to count, *when* it is a finding, and *which* transformation to apply.

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
- Python `match`: +1 per `case` except `case _`. Guard clauses on a case (`case X if cond`) add +1 more.
- TypeScript / JavaScript `switch`: +1 per `case` label, including fall-through labels, because each is a distinct entry path.
- Kotlin `when` and Go `select` / `switch`: same as `switch`.
- Go `if err != nil { return err }`: counts +1 like any `if`. A function that is mostly error plumbing can legitimately sit in the 6-10 band; diagnose the cause before flagging (see below).

**Nesting depth**: the deepest chain of control-flow blocks (`if` / loop / `try` / `switch`) inside the body. Statements at the top level of the function are depth 0; each enclosing block adds 1. A `for` containing an `if` containing a `try` is depth 3.

**Prefer measured numbers when the project already has them.** If the repository has a complexity linter configured -- eslint `complexity`, `radon` / `flake8` `C901`, `gocyclo`, rubocop `Metrics/CyclomaticComplexity`, PHPMD `CyclomaticComplexity` -- run it on the changed files and use its numbers. Never install tooling to get a number; a hand estimate from the rules above is sufficient and reproducible.

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

Estimated CC 6, nesting depth 2. In the 6-10 band; only a finding if a listed smell is present and obviously fixable (here: none -- the branching is the domain).

---

## Thresholds

| Estimated CC | Reading |
|--------------|---------|
| <= 5 | Target for new code. |
| 6-10 | Acceptable when the domain genuinely requires that many cases. Not a finding on its own. |
| 11-15 | Refactoring signal. A finding when the function is new or changed in this PR. |
| > 15 | Avoid unless there is a strong, stated reason. A finding when new or changed in this PR. |

Nesting depth >= 4 is a finding regardless of CC -- depth is what makes a function hard to hold in your head.

---

## Scope rule

Audit **every function the diff adds or modifies**. Do not audit or flag functions the PR does not touch, even if they are worse -- the review is of this PR, not the codebase.

Two exceptions that *are* findings:
- The PR pushes an existing function across a threshold (e.g. adds the branch that takes it from 10 to 11). Cite the before and after estimate.
- The PR copies an already-complex function to create a near-duplicate. That is a reuse finding *and* a complexity finding.

---

## Cause diagnosis

For each function above threshold, name the **dominant cause** -- the one structural reason most of the paths exist. The cause selects the transformation.

| Dominant cause | What it looks like | Transformation |
|----------------|--------------------|----------------|
| **Deep nesting** | Validation or precondition checks wrap the main operation in successive `if` blocks. | Guard clauses / early return |
| **Repeated conditions** | The same predicate (or its negation) is tested in several places in the function. | Flatten nested conditionals, or extract predicate |
| **Long conditional chain** | `if / elif / elif / else` or a `switch` selecting behavior by a value. | Dispatch map, or replace chain with data |
| **Several jobs in one function** | Independent decisions about unrelated concerns (parse, validate, persist, notify) in one body. | Extract loop body / split by responsibility |
| **Boolean mode flag** | A parameter like `dry_run`, `strict`, `as_json` that steers into substantially different paths. | Split a boolean-flag function |
| **Duplicated branches** | Two or more branches that are identical except for a value or a call target. | Consolidate duplicated branches |
| **Compound boolean** | A condition with three or more `&&` / `||` terms, often mixing unrelated concerns. | Extract predicate |
| **Type switch repeated across functions** | Several functions each `switch` on the same discriminator. | Polymorphism / strategy |

---

## Transformation catalog

Each entry: the smell it targets, a compact before / after, and when **not** to use it. Apply exactly one transformation per finding; if a second is needed, that is a second finding.

### 1. Guard clauses / early return

Targets: deep nesting from validation.

Prefer:

```text
validate -> return early on failure
validate -> return early on failure
perform main operation
return result
```

over:

```text
if valid:
    if another_condition:
        if another_condition:
            perform main operation
        else:
            ...
    else:
        ...
else:
    ...
```

Concretely, prefer:

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

Not when: the "failure" branches each do substantive, different work. That is dispatch, not validation -- see 3.

### 2. Flatten nested conditionals

Targets: repeated conditions; nesting that exists only because two checks were written separately.

```python
# before
if order.paid:
    if order.shipped:
        notify(order)

# after
if order.paid and order.shipped:
    notify(order)
```

Not when: flattening forces you to duplicate a condition elsewhere, or when the inner check has its own `else` that must stay distinct.

### 3. Dispatch map / lookup table

Targets: a long `if / elif` or `switch` chain that selects behavior by a value.

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

Not when: there are only two or three branches, the branches share intermediate state, or evaluation order matters (a map hides ordering).

### 4. Polymorphism / strategy

Targets: the *same* discriminator switched on in several functions.

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

Not when: the switch exists in one place. A single dispatch site is a map (see 3), and a class hierarchy for one switch is excessive indirection.

### 5. Extract predicate

Targets: compound booleans; a condition whose meaning is not obvious from its terms.

```python
# before
if user.plan == "pro" and not user.suspended and user.seats_used < user.seats_total:
    grant_seat(user)

# after
if can_add_seat(user):
    grant_seat(user)
```

The predicate is the same CC; the win is that the caller now has one concept to reason about, and the predicate is testable in isolation.

Not when: the name would only restate the expression (`is_a_and_b`). If you cannot name the concept, the condition may be fine as it is.

### 6. Extract loop body

Targets: a loop whose body carries most of the function's decisions.

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

Not when: the body reads and writes many locals of the enclosing function -- the extracted function would need a wide parameter list or an out-parameter, which is worse than the loop.

### 7. Split a boolean-flag function

Targets: a flag parameter that selects between substantially different execution paths.

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

Not when: the flag toggles one small step inside an otherwise shared path. Then keep the flag; two near-identical functions are the duplicated-branch smell.

### 8. Consolidate duplicated branches

Targets: branches identical except for a value or call target.

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

Not when: the branches only coincide today and are expected to diverge (a documented reason, not a hunch).

### 9. Replace an `if / elif` chain with data

Targets: a ladder of thresholds or rules that is really configuration.

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

Not when: the rules have side effects or ordering dependencies that a table would hide from the reader.

---

## Severity mapping

Applies only to functions the PR adds or modifies (see Scope rule).

| Finding | Priority |
|---------|----------|
| Estimated CC > 15, or nesting depth >= 4 | **Medium** -- maintainability concern; should fix before merge. |
| Estimated CC 11-15 | **Low** -- refactoring signal; nice to fix. |
| Estimated CC 6-10 with a listed smell (boolean mode flag, duplicated branches, long chain) and an obvious transformation | **Low** |
| Estimated CC 6-10 with no listed smell | Not a finding. Record the row in the complexity notes and move on. |
| PR pushes an existing function across a threshold | Same priority as the band it lands in; cite before and after. |

A complexity finding is written like every other finding: bold file path, the function, the estimate and dominant cause, and the named transformation.

```markdown
- **`src/billing/invoice.ts:42`** -- `applyDiscounts` is est. CC 17, nesting 4 (deep nesting from validation). Convert the four precondition checks to guard clauses; the main loop then sits at depth 1.
```

---

## Guardrails

Do not optimize the number blindly. Before proposing or applying a transformation, confirm it does **not** introduce:

- obscure abstractions
- excessive indirection
- unnecessary classes or design patterns
- fragmented code -- meaningless one-line helpers that exist only to move a branch out of view
- worse performance in a performance-critical path
- harder debugging (a stack trace through a dispatch table is less obvious than a visible `if`)
- behavior that is less obvious to the reader than the branch it replaced

If any of these would result, the slightly higher-complexity implementation is the correct one. Say so in the complexity notes (`Domain-justified? Yes` with the reason) and do not raise a finding.

When applying a transformation in Phase 9: preserve behavior exactly, re-estimate CC after the edit, and state in the commit message which branching or responsibility was removed or isolated -- not just the new number.
