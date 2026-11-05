## What and why

<!-- One concern per PR. Link the issue if there is one. -->

## Evidence

<!-- The commands you ran and what they printed. Required. -->

```
uv run python -m pytest -q
bash tests/hook-test.sh
```

## Checklist

- [ ] PR title follows Conventional Commits (`fix(scope): ...`); it becomes the squash commit
- [ ] No real school, instructor, room or course names, device names, IDs, IPs, serials, stream keys or recordings in code, fixtures or this PR
- [ ] No internal messages, customer data, CRM figures or document contents in code, docs or commits
- [ ] Platform API calls are documented, cited, and read only unless a person approved the write
- [ ] No claim about timing or alignment across cameras or devices, in code, comments, docs or chat
- [ ] Edge write guard and redaction unchanged, or changed in the Epiphan Edge Claude Kit first
- [ ] Prose passed the Epiphan Brand check
- [ ] Docs updated if behavior or setup changed
