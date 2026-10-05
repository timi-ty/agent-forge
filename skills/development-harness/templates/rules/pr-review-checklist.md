# Phase Completion Review Checklist

Read at Step 9c, before a phase is marked `"completed"`: after this turn's units
are validated and recorded in phase-graph.json (9a) and state.json (9b), and
before the checkpoint refresh (9d) and the commit, push and PR (Step 10).

Only what is answerable at that point belongs here. Anything a later step owns
is verified by that step — see the note at the end.

## Code Quality
- [ ] All units have validation evidence in phase-graph.json
- [ ] No linter errors in changed files
- [ ] No type errors in changed files
- [ ] Code follows existing conventions where they serve current requirements; obsolete patterns are not preserved automatically
- [ ] Every mechanism added or retained in the affected flow answers **"Which current requirement would fail if this mechanism were deleted?"** with code, contract, supported-consumer, or runtime evidence. Being called and tested does not establish need
- [ ] Removals/replacements cover affected producers, consumers, fields/types/serialization, stored representations, helpers, comments, tests, fixtures, and data transformations; no unjustified obsolete machinery remains
- [ ] Retained compatibility identifies an evidenced currently supported consumer or explicit current requirement and the contract deletion would break; missing evidence has been investigated
- [ ] Unresolved in-scope remnants block phase completion and are reported as blockers; unrelated cleanup is recorded for later within ownership and scope rules

## Testing
- [ ] Unit tests pass for all new/modified code
- [ ] Integration tests pass (if applicable)
- [ ] E2E tests pass (if applicable and configured)

## Deployment
- [ ] CI is not failing on this branch's most recent push
- [ ] No regressions in the deployed environment (if the phase is deploy-affecting)

## Documentation
- [ ] Phase document updated with completion evidence
- [ ] Any new APIs or interfaces documented

---

Deliberately not checked here, because a later step owns each and runs
unconditionally:

- **Deployment verification** — Step 9c runs the verifier from `config.json`
  itself, on the bullet immediately after this file is read. Listing it here
  would run the deployed-environment layers twice.
- **Checkpoint refresh** — Step 9d.
- **Committing, pushing, and PR creation** — Step 10, per the harness-git rule.
  At 9c none of this turn's work is committed yet, and 9a/9b have just written
  phase-graph.json and state.json, so a "no uncommitted harness changes" gate
  could never pass.
