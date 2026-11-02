#!/usr/bin/env python3
"""Keep one listing PR from this fork mergeable with its upstream.

Runs in GitHub Actions on the fork. If the upstream PR is open and GitHub
reports a merge conflict, the PR branch is rebuilt on the upstream default
branch with only our entry added again, then force-pushed.

Modes:
  json-append  our object in a JSON "plugins" array, appended at the end
               (xai-org/plugin-marketplace .grok-plugin/marketplace.json)
  table-row    our row in a Markdown table, inserted in alphabetical place
               (jaw9c/awesome-remote-mcp-servers README.md)
"""
import json
import os
import subprocess
import sys
import time

UPSTREAM = os.environ["UPSTREAM"]          # owner/repo
PR = os.environ["PR_NUMBER"]
BRANCH = os.environ["PR_BRANCH"]
MODE = os.environ["MODE"]
FILE = os.environ["TARGET_FILE"]
MARKER = os.environ["MARKER"]              # plugin name or row prefix
AFTER = os.environ.get("AFTER_CMDS", "")   # commands run after editing, ";"-separated
TABLE_HEADER = os.environ.get("TABLE_HEADER", "| Name |")


def sh(*args, capture=False):
    print("+", " ".join(args), flush=True)
    if capture:
        return subprocess.check_output(args, text=True)
    subprocess.check_call(args)


def pr_status():
    for _ in range(6):
        data = json.loads(sh("gh", "api", f"repos/{UPSTREAM}/pulls/{PR}", capture=True))
        if data["state"] != "open" or data.get("mergeable") is not None:
            return data
        time.sleep(20)
    return data


def extract(text):
    if MODE == "json-append":
        plugins = json.loads(text)["plugins"]
        return next(p for p in plugins if p["name"] == MARKER)
    if MODE == "table-row":
        return next(line for line in text.splitlines() if line.startswith(MARKER))
    raise SystemExit(f"unknown MODE {MODE}")


def insert_json(text, entry):
    tail = "    }\n  ]\n}\n"
    if not text.endswith(tail):
        raise SystemExit("unexpected end of catalog file; fix by hand")
    src = entry["source"]
    lines = [
        "    },", "    {",
        f'      "name": {json.dumps(entry["name"])},',
        f'      "description": {json.dumps(entry["description"], ensure_ascii=False)},',
        f'      "category": {json.dumps(entry["category"])},',
        '      "source": {',
        f'        "source": {json.dumps(src["source"])},',
        f'        "url": {json.dumps(src["url"])},',
        f'        "sha": {json.dumps(src["sha"])}',
        "      },",
        f'      "homepage": {json.dumps(entry["homepage"])},',
        f'      "keywords": {json.dumps(entry["keywords"])},',
        f'      "domains": {json.dumps(entry["domains"])}',
        "    }", "  ]", "}",
    ]
    out = text[: -len(tail)] + "\n".join(lines) + "\n"
    json.loads(out)
    return out


def insert_row(text, row):
    def key(line):
        return line.split("|")[1].strip().lower()

    lines = text.splitlines(keepends=True)
    ours = key(row)
    header = next((i for i, l in enumerate(lines) if l.startswith(TABLE_HEADER)), None)
    if header is None:
        raise SystemExit("table header not found; fix by hand")
    rows = []
    for i in range(header + 2, len(lines)):
        if not lines[i].startswith("|"):
            break
        rows.append(i)
    if not rows:
        raise SystemExit("table is empty; fix by hand")
    # Before the first row that sorts after ours; the end of the table otherwise.
    pos = next((i for i in rows if key(lines[i]) > ours), rows[-1] + 1)
    lines.insert(pos, row + "\n")
    return "".join(lines)


def main():
    status = pr_status()
    print(f"PR {UPSTREAM}#{PR}: state={status['state']} mergeable={status.get('mergeable')} "
          f"mergeable_state={status.get('mergeable_state')}")
    if status["state"] != "open":
        print("PR is not open; nothing to do.")
        return
    if status.get("mergeable") is not False:
        print("No conflict; nothing to do.")
        return

    ours = extract(open(FILE, encoding="utf-8").read())
    base = status["base"]["ref"]
    sh("git", "remote", "add", "upstream", f"https://github.com/{UPSTREAM}.git")
    sh("git", "fetch", "--no-tags", "upstream", base)
    sh("git", "reset", "--hard", f"upstream/{base}")

    text = open(FILE, encoding="utf-8").read()
    try:
        extract(text)
        print("Upstream already contains our entry; leaving the branch alone.")
        sh("git", "reset", "--hard", f"origin/{BRANCH}")
        return
    except StopIteration:
        pass

    text = insert_json(text, ours) if MODE == "json-append" else insert_row(text, ours)
    open(FILE, "w", encoding="utf-8").write(text)
    for cmd in filter(None, (c.strip() for c in AFTER.split(";"))):
        sh("bash", "-c", cmd)

    sh("git", "add", "-A")
    title = subprocess.check_output(["git", "log", "-1", "--format=%B", f"origin/{BRANCH}"], text=True).strip()
    sh("git", "commit", "-m", title)
    sh("git", "push", f"--force-with-lease={BRANCH}:origin/{BRANCH}", "origin", f"HEAD:{BRANCH}")
    print("Branch rebuilt on upstream and pushed.")


if __name__ == "__main__":
    sys.exit(main())
