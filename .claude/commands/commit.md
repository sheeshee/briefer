Stage files and commit changes. Do not ask for permission — git add and git commit are pre-approved in settings.local.json.

## Workflow

1. Run `git status` and `git diff` to understand what changed
2. Group changes into logical commits (one concern per commit)
3. Stage and commit each group:

```bash
git add <files>
git commit -m "$(cat <<'EOF'
<subject line>

<body if needed>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

## Rules

- Never use `git add -A` or `git add .` — stage files explicitly by name
- Never commit unrelated changes together
- Write commit messages that explain *why*, not just *what*
- Always include the Co-Authored-By trailer
- Do not push unless the user asks
