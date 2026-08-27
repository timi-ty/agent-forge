# Phase Completion Review Checklist

Before marking a phase complete, verify each item:

## Code Quality
- [ ] All units have validation evidence in phase-graph.json
- [ ] No linter errors in changed files
- [ ] No type errors in changed files
- [ ] Code follows existing codebase patterns

## Testing
- [ ] Unit tests pass for all new/modified code
- [ ] Integration tests pass (if applicable)
- [ ] E2E tests pass (if applicable and configured)

## Deployment
- [ ] CI checks pass
- [ ] Deployment verification passes (if phase is deploy-affecting)
- [ ] No regressions in deployed environment

## Documentation
- [ ] Phase document updated with completion evidence
- [ ] Checkpoint updated with what completed and what's next
- [ ] Any new APIs or interfaces documented

## Git
- [ ] All changes committed following git policy
- [ ] PR created (if applicable per git policy)
- [ ] No uncommitted harness-related changes
