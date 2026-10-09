"""Merge gate that runs outside the model loop.

usage: python gate.py <run_dir> [--json out.json]

G1 residual machine paths, G2 syntax, G3 scope, G4 redaction kept.
Nothing here calls a model.
"""
import json, re, subprocess, sys, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = (HERE / "targets.txt").read_text(encoding="utf-8").split()
BASE_SHA = {}
for line in (HERE / "base.sha256").read_text(encoding="utf-8").splitlines():
    digest, name = line.split(" ", 1)
    BASE_SHA[name.lstrip("*")] = digest

# 改成你自己的：匹配「含用户名或个人目录的绝对路径」，YOURNAME 换成你的用户名
MACHINE = re.compile(r"(?i)[a-z]:[\\/]+Users[\\/]+YOURNAME")
# 含脱敏规则的文件：这些文件里带 <HOME> 的行不算残留，且必须保留脱敏
REDACT_FILES = set()


def residual(rel, text):
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        if not MACHINE.search(line):
            continue
        if rel in REDACT_FILES and "<HOME>" in line:
            continue  # redaction literal, not a path dependency
        hits.append(no)
    return hits


def syntax(path):
    suffix = path.suffix.lower()
    if suffix == ".py":
        cmd = [sys.executable, "-c", "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())", str(path)]
    elif suffix in (".mjs", ".js"):
        cmd = ["node", "--check", str(path)]
    elif suffix == ".ps1":
        script = ("$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile("
                  f"'{path}',[ref]$null,[ref]$e);if($e.Count){{$e|%{{$_.Message}};exit 1}}")
        cmd = ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script]
    else:
        return True, "skipped"
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout + r.stderr).strip()[:300]


def redaction_kept(text):
    if "<HOME>" not in text:
        return False
    sources = ("homedir()", "USERPROFILE", "os.homedir", "expanduser")
    return any(s in text for s in sources)


def main():
    run = Path(sys.argv[1]).resolve()
    out = {"run": run.name, "files": {}, "scope": {}}
    changed = 0
    for rel in TARGETS:
        p = run / rel
        f = out["files"][rel] = {}
        if not p.exists():
            f.update(exists=False, ok=False)
            continue
        data = p.read_bytes()
        text = data.decode("utf-8", errors="replace")
        f["changed"] = hashlib.sha256(data).hexdigest() != BASE_SHA[rel]
        changed += f["changed"]
        f["residual_lines"] = residual(rel, text)
        f["syntax_ok"], f["syntax_msg"] = syntax(p)
        if rel in REDACT_FILES:
            f["redaction_kept"] = redaction_kept(text)
        f["ok"] = (not f["residual_lines"]) and f["syntax_ok"] and f.get("redaction_kept", True)
    allowed = set(TARGETS) | {"targets.txt", "TASK.md"}
    extra = sorted(str(p.relative_to(run)).replace("\\", "/") for p in run.rglob("*")
                   if p.is_file() and ".git" not in p.parts)
    extra = [e for e in extra if e not in allowed and not e.startswith("_migration/")]
    out["scope"] = {"unexpected_files": extra, "missing": [r for r in TARGETS if not (run / r).exists()]}
    out["changed_files"] = changed
    out["gate_pass"] = all(f["ok"] for f in out["files"].values()) and not extra and not out["scope"]["missing"]
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for rel, f in out["files"].items():
        flag = "PASS" if f["ok"] else "FAIL"
        notes = []
        if f.get("residual_lines"): notes.append(f"残留行 {f['residual_lines']}")
        if not f.get("syntax_ok", True): notes.append("语法错")
        if f.get("redaction_kept") is False: notes.append("脱敏被削弱")
        if not f.get("changed", True): notes.append("未改动")
        print(f"{flag}  {rel}  {' '.join(notes)}")
    print(f"范围外文件：{extra or '无'}")
    print(f"GATE {'PASS' if out['gate_pass'] else 'FAIL'}  改动 {changed}/{len(TARGETS)}")


if __name__ == "__main__":
    main()
