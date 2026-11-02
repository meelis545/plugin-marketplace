# qqq-automation

This branch is the fork's default branch and holds only automation. Once a day
it checks the listing PR xai-org/plugin-marketplace#1546 (head branch `add-qqq-ai-visibility`). If
GitHub reports a merge conflict, it rebuilds that branch on the upstream default
branch with only the QQQ entry added again and force-pushes it.

The fork's `main` mirrors upstream and is not used. Run by hand: Actions →
"Keep QQQ listing PR mergeable" → Run workflow.

Local test without pushing: set `FORCE=1 DRY_RUN=1` with the same environment
variables as the workflow and run `scripts/keep_pr_mergeable.py` inside a clone
of the PR branch.
