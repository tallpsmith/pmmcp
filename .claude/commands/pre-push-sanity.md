# Pre-Push Sanity Check

Run the full pre-push sanity check to verify the codebase is ready to push.

## Steps

1. Execute `scripts/pre-push-sanity.sh` via Bash
2. Report pass/fail for each phase: Lint, Format, Unit+Integration, E2E (if applicable)
3. If any phase fails, block the push and show the failure output
4. If `PMPROXY_URL` is not set, note that E2E was skipped and remind the developer to add a note to their PR description

## Execution

```bash
scripts/pre-push-sanity.sh
```

If the script exits with a non-zero code, the push is blocked. Fix the reported failures before pushing.
