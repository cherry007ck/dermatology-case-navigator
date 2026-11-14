# Paste at the start of every new Kiro coding chat

```text
Use the repository playbook and AGENTS.md. Before implementing, ask exactly: “Who is coding today: Luffy or Zoro?” If I already explicitly supplied my identity in this chat, use it without asking twice. Do not infer it from git, the machine or another chat.

After I answer, read my docs/status/<name>.md, the sprint plan, API contract and current branch/diff. Tell me the next incomplete sprint, allowed files, dependency state and checks. Read the matching sprint prompt and execute that sprint's tasks, not the other developer's backlog. Continue routine authorized coding/checks without asking me to approve every step. Ask only for genuinely missing credentials, decisions, ownership changes or human account actions.

Use the shared mocks if the teammate's implementation is not yet available. Do not change the contract or touch their owned code silently. When blocked, complete independent tasks and give a concrete minimal handoff. Preserve edits. Keep secrets out of the chat and git.

At the end, run the relevant checks, update only my status file and my task checkboxes, and give a concise PR-ready handoff: behavior, evidence/checks actually run, remaining work, and next teammate action. Stop at the sprint checkpoint so we can integrate before proceeding.
```

After Kiro asks, answer `Luffy` or `Zoro`, optionally adding `Sprint S2` or `resume current sprint`. Checkboxes are marked complete only after their acceptance evidence exists. Ownership is a coordination boundary, not a requirement to request permission for every normal edit inside the lane.
