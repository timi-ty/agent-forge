# Code Review Checklist

Detailed review criteria for Phase 4 (file-by-file review) and Phase 5 (semantic verification). Check each item for every changed file.

---

## Scope

- [ ] **PR description exists**: The PR has a non-empty body that describes what it does and why.
- [ ] **Linked issue**: The PR links to a motivating issue. If no issue is linked, flag as a hygiene concern.
- [ ] **Title-diff coherence**: Every changed file relates to the goal stated in the PR title and description. No unrelated files.
- [ ] **Issue-scope alignment**: If a linked issue exists, changes stay within the issue's stated scope. No scope creep.
- [ ] **No accidental inclusions**: No files that appear to come from an unrelated branch or a dirty working directory.
- [ ] **Test coverage for behavioral changes**: If the PR changes runtime behavior (not just config/docs), corresponding tests exist or are added.

## Pattern Conformance

- [ ] **Naming**: Functions, variables, types, and files follow the same naming conventions as existing code in the same module (camelCase vs snake_case, prefix/suffix patterns, abbreviation style).
- [ ] **File structure**: The file is organized the same way as its siblings (imports at top, then types, then constants, then main exports -- or whatever the local convention is).
- [ ] **Import style**: Import ordering, grouping (external vs internal), and syntax (named vs default, `import type` usage) match existing files.
- [ ] **Export style**: Named exports vs default exports, barrel files, re-export patterns match the module's convention.
- [ ] **Error handling**: Uses the same error handling patterns as surrounding code (custom error classes, Result types, try/catch style, error propagation).
- [ ] **Logging**: Uses the same logger and log levels as surrounding code.
- [ ] **Comments**: Comment style and density matches the codebase (JSDoc vs inline, when comments are used vs when they are omitted).
- [ ] **Formatting**: Indentation, bracket style, trailing commas, semicolons match (should be enforced by linter, but verify).

## Correctness

- [ ] **Logic**: The code does what the PR description says it should do.
- [ ] **Edge cases**: Null/undefined inputs, empty arrays/objects, boundary values are handled.
- [ ] **Error paths**: All operations that can fail have proper error handling. No swallowed errors.
- [ ] **Async correctness**: Promises are awaited. No fire-and-forget unless intentional. No race conditions between concurrent operations.
- [ ] **State mutations**: No unintended side effects. Mutable state is managed carefully.
- [ ] **Type narrowing**: Type guards and narrowing are correct. No unsafe casts (`as`, `!`) unless justified.
- [ ] **API contracts**: Function signatures, return types, and thrown errors match what callers expect.
- [ ] **Boundary conditions**: Off-by-one errors, integer overflow, string encoding issues.

## Efficiency

- [ ] **Redundant operations**: No duplicate computations, repeated lookups, or unnecessary re-renders.
- [ ] **Algorithmic complexity**: Data structures and algorithms are appropriate for the data size. No O(n^2) where O(n) is possible.
- [ ] **Batching**: Operations that can be batched (DB queries, API calls, DOM updates) are batched.
- [ ] **Lazy evaluation**: Expensive computations are deferred until actually needed.
- [ ] **Memory**: No unnecessary copies of large data structures. No memory leaks from retained references or uncleaned listeners.
- [ ] **Network**: No unnecessary API calls. Requests are deduplicated or cached where appropriate.

## Dead Code

- [ ] **Unused imports**: Every import is referenced in the file.
- [ ] **Unused variables**: Every declared variable is read at least once.
- [ ] **Unused functions**: Every defined function is called (in this file or exported and called elsewhere).
- [ ] **Unreachable code**: No code after unconditional `return`, `throw`, `break`, or `continue`.
- [ ] **Commented-out code**: No blocks of commented-out code (should be deleted, not commented).
- [ ] **Dead branches**: No `if` branches that can never be true, no `switch` cases that can never match.
- [ ] **Unused parameters**: Function parameters are all used. Remove or prefix with `_` if intentionally unused.

## Security

- [ ] **Input validation**: All external input (user input, API responses, URL params) is validated before use.
- [ ] **Injection**: No SQL injection, XSS, command injection, or path traversal vulnerabilities.
- [ ] **Secrets**: No hardcoded API keys, passwords, tokens, or connection strings.
- [ ] **Auth**: Authentication and authorization checks are present where required.
- [ ] **Data exposure**: No sensitive data leaked in logs, error messages, or API responses.

## Type Safety

- [ ] **No `any`**: Avoid `any` unless truly necessary. Use `unknown` and narrow instead.
- [ ] **Narrow types**: Types are as specific as possible (string literals vs `string`, specific union vs broad type).
- [ ] **Generic correctness**: Generic type parameters are constrained appropriately.
- [ ] **Null safety**: Optional values are checked before use. Strict null checks are respected.
- [ ] **Return types**: Functions have explicit return types where the codebase convention requires them.

---

The sections below are used in **Phase 5 (Semantic Verification)**, not Phase 4. During Phase 4, skip these sections -- they require a separate adversarial re-read.

## Semantic Verification -- Test Code

Shift from "does this test follow patterns?" to "does this test actually prove what it claims?" For each test, ask: **if the feature this test covers were broken, would this test fail?**

- [ ] **Subject identity**: The test instantiates and exercises the *real* implementation, not a hand-written stub, re-implementation, or test-local subclass defined in the test file. If the test defines its own version of the class/function it claims to test, every assertion passes against the fake -- proving nothing about the application.
- [ ] **Data preconditions**: Tests that query, filter, or aggregate data first create data with sufficient variety that the operation is meaningfully exercised. A filter test against an empty table always returns `success: true` with zero results -- it cannot distinguish a working filter from a broken one.
- [ ] **Assertion strength**: Assertions verify specific expected values, not just structural existence. Flag weak assertions that would pass on almost any response: `toBeDefined()`, `toBeTruthy()`, `toHaveProperty('x')` without a value check, `expect(data).toBeDefined()` on an endpoint that always returns a (possibly empty) data wrapper.
- [ ] **Mock boundaries**: Mocks replace *dependencies* of the subject under test, not the subject itself. If a test fully mocks the component it claims to test, it is testing mock behavior. Verify that the real code path -- the one with actual conditionals and logic -- is exercised.
- [ ] **Mutation verification**: Tests for create/update/delete operations verify the mutation took effect by reading back state (database query, subsequent GET, downstream side-effect check) -- not just asserting the API returned a success status code.
- [ ] **Content verification**: Tests for data export, transformation, or rendering verify the actual output content (parsed CSV rows, JSON payload field values, rendered markup). Checking only metadata (Content-Type header, Content-Disposition filename, HTTP status) is insufficient -- those pass even on empty or wrong bodies.
- [ ] **Failure possibility**: The test setup creates conditions where the assertion *could* fail if the feature were broken. If the test would pass regardless of whether the feature works (e.g., asserting a property exists on a response that always includes it as an empty default), the test is vacuous.
- [ ] **Test independence**: Each test proves something distinct about the system. Flag suites where many tests are structural copies exercising the same underlying code path (e.g., N endpoint tests that all only verify auth middleware returns 401, inflating the test count without testing endpoint-specific behavior).

## Semantic Verification -- Application Code

Shift from "does this code follow patterns?" to "does this code actually accomplish what it claims?" For each function, trace the data flow and verify the logic matches the intent.

- [ ] **Business logic substance**: For each conditional or branching path, verify it handles a case that actually occurs. A guard clause whose condition is always true (or always false) in practice is dead logic that looks alive. Trace the data flow to confirm the branch can be reached with realistic inputs.
- [ ] **Integration point correctness**: Where code calls external services (database queries, API calls, message brokers, Firebase, etc.), verify the call is semantically correct: right table/collection, right fields, right query conditions, right message format. Syntactically valid calls to the wrong table or with wrong conditions are bugs that compile cleanly.
- [ ] **Error handling substance**: Error handlers do more than catch and re-throw or catch and silently swallow. Verify they provide useful diagnostic information, clean up intermediate state, or propagate errors in a way that callers can act on. A `try/catch` that transforms an error into a less informative one is a net negative.
- [ ] **Computed value correctness**: Calculations, transformations, and derived values use the correct inputs. A pagination helper that computes `Math.ceil(total / limit)` is correct in isolation, but if `total` is sourced from the wrong query or `limit` is a stale default, the output is wrong despite the formula being right. Trace the inputs.
