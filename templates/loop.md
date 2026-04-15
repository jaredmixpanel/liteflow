Check on liteflow workflows and system health:

1. Run `/liteflow:flow-status` to check system health. If the queue has stuck items, report them.
2. Check if any workflows have failed recently with `/liteflow:flow-history --limit 5`. For any failures, briefly summarize what went wrong.
3. If everything is healthy and no recent failures, say "liteflow: all clear" in one line.

Do not start new workflows or make changes. Report only.
