"""Blind review: a fresh `claude -p` session grades each run's diffs against rubric.md
(write it BEFORE the first run). It never sees the condition, the run id or REPORT.md.

usage: python review.py <evidence/runs dir> <out dir>
"""
import difflib, json, random, subprocess, sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
TARGETS = (LAB / "targets.txt").read_text(encoding="utf-8").split()
KEY = (LAB / "rubric.md").read_text(encoding="utf-8")
# The reviewer must see the same task text the agents saw. Paraphrasing it here is how the
# original experiment lost half of a requirement and marked a correct edit wrong.
TASK = (LAB / "TASK.md").read_text(encoding="utf-8")

INSTRUCTIONS = f"""You are reviewing a migration on the scripts listed below. The full task the agents received is
quoted under TASK. Grade each file against the SCORING KEY, reading it together with the TASK. For each file answer
"correct" or "wrong", with one sentence of reason. Judge only from the diff. Missing edits count as wrong. Then list
any behaviour change outside the task that you notice, per file.

Reply with JSON only, no code fence:
{{"files": [{{"n": 1, "verdict": "correct|wrong", "reason": "..."}}, ... {len(TARGETS)} items], "side_effects": [{{"n": 2, "note": "..."}}]}}
"""


def packet(run_out):
    parts = [INSTRUCTIONS, "\nTASK\n", TASK, "\nSCORING KEY\n", KEY, "\nDIFFS\n"]
    for n, rel in enumerate(TARGETS, 1):
        before = (LAB / "base" / rel).read_text(encoding="utf-8").splitlines()
        after_p = run_out / rel
        after = after_p.read_text(encoding="utf-8").splitlines() if after_p.exists() else []
        diff = "\n".join(difflib.unified_diff(before, after, f"a/{rel}", f"b/{rel}", n=3, lineterm=""))
        parts.append(f"\n### File {n}: {rel}\n```diff\n{diff or '(no change)'}\n```\n")
    return "".join(parts)


def main():
    runs, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    ids = sorted(d.name for d in runs.iterdir() if (d / "gate.json").exists())
    key_file = out / "key.json"
    key = json.loads(key_file.read_text(encoding="utf-8")) if key_file.exists() else {}
    rng = random.Random(20261009 + len(key))
    new = [i for i in ids if i not in key.values()]
    rng.shuffle(new)
    for rid in new:
        code = f"R{rng.randrange(100, 1000)}"
        while code in key:
            code = f"R{rng.randrange(100, 1000)}"
        key[code] = rid
    key_file.write_text(json.dumps(key, indent=1), encoding="utf-8")
    for code, rid in key.items():
        target = out / f"{code}.json"
        if target.exists():
            continue
        text = packet(runs / rid / "out")
        (out / f"{code}.prompt.md").write_text(text, encoding="utf-8")
        r = subprocess.run(["claude", "-p", "--model", "claude-opus-5-5", "--output-format", "json",
                            "--strict-mcp-config", "--max-turns", "1",
                            "--disallowedTools", "Bash", "Read", "Edit", "Write", "Grep", "Glob", "Agent", "Skill",
                            "WebFetch", "WebSearch"],
                           input=text, capture_output=True, text=True, encoding="utf-8", cwd=out)
        (out / f"{code}.raw.json").write_text(r.stdout, encoding="utf-8")
        try:
            res = json.loads(r.stdout)["result"].strip()
            res = res[res.index("{"):res.rindex("}") + 1]
            target.write_text(json.dumps(json.loads(res), ensure_ascii=False, indent=1), encoding="utf-8")
            print(code, "ok")
        except Exception as e:  # keep raw output for inspection
            print(code, "parse failed", e)


if __name__ == "__main__":
    main()
