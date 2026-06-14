# Codex Review Packet Template

Use this template when Hermes hands implemented work to Codex for an
independent review gate.

```text
# Codex Review Packet

Generated:
Branch:
Mode:

## Review scope

### A. Changes to review
- Commit:
- Files:
- Claimed behavior:

### B. Working tree changes
- File:
- Reason still unstaged/uncommitted:

### C. Verification evidence
- Tests run:
- Build/check commands:
- Known failures or skips:

## Review questions

1. Does the implementation stay within the active phase boundary?
2. Do the changed files support the claimed conclusion?
3. Are the tests sufficient for the touched surface?
4. Is there any scope drift, regression risk, or documentation mismatch?

## Expected Codex output

Review scope:
Verdict: accept | partial | fail
Evidence:
Drift or defects:
Required corrections:
```

## Repo notes

- Use `ecc-readonly-review` for static acceptance and drift checks.
- Use `ecc-self-test` when regression execution is part of the gate.
- If Codex returns `accept`, commit only the approved files.
