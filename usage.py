"""Per-run cost and token split, two ways.

usage: python usage.py <evidence/runs dir>

Method 1: the CLI's own `result` event (total_cost_usd, modelUsage).
Method 2: sum `usage` on every assistant message in stream.jsonl, deduplicated by
message id, grouped by model. Subagent messages carry parent_tool_use_id.
Only these fields are read; nothing else from the stream is printed.
"""
import json, sys
from collections import defaultdict
from pathlib import Path

FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
PRICES = json.loads((Path(__file__).resolve().parent / "prices.json").read_text(encoding="utf-8"))


def price_of(model, u):
    """Cost of one request (or one advisor iteration) from the official table. [COMPUTED]"""
    p = PRICES.get(model)
    if not p:
        raise KeyError(f"no price for {model}")
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    w5m = cc.get("ephemeral_5m_input_tokens", (u.get("cache_creation_input_tokens") or 0) - w1h) or 0
    prompt = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + w1h + w5m
    if "_over_100k" in p and prompt > 100_000:
        p = p["_over_100k"]
    return ((u.get("input_tokens") or 0) * p["in"] + (u.get("output_tokens") or 0) * p["out"]
            + w5m * p["w5m"] + w1h * p["w1h"] + (u.get("cache_read_input_tokens") or 0) * p["hit"]) / 1e6


def short(model):
    for k in ("opus", "sonnet", "haiku", "fable"):
        if k in model:
            return k
    return model


PROJECTS = Path.home() / ".claude" / "projects"


def session_id(run_dir):
    for line in (run_dir / "stream.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            sid = json.loads(line).get("session_id")
        except json.JSONDecodeError:
            continue
        if sid:
            return sid


def transcript_usage(sid):
    """Session transcript(s): main file plus any subagent files under <sid>/.
    One message can span several lines; keep the line with the largest output count."""
    files = list(PROJECTS.glob(f"*/{sid}.jsonl")) + list(PROJECTS.glob(f"*/{sid}/**/*.jsonl"))
    best = {}
    for f in files:
        sub_file = f.stem != sid
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message") or {}
            if ev.get("type") != "assistant" or not msg.get("usage") or msg.get("model") == "<synthetic>":
                continue
            key = (msg.get("id"), ev.get("requestId"))
            sub = sub_file or bool(ev.get("isSidechain"))
            prev = best.get(key)
            if not prev or (msg["usage"].get("output_tokens") or 0) >= (prev[1].get("output_tokens") or 0):
                best[key] = (msg.get("model", "?"), msg["usage"], sub)
    return best.values()


def one(run_dir):
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    result = None
    for line in (run_dir / "stream.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result = ev
    # message-level usage = the model's own iterations; advisor iterations are extra
    m2 = defaultdict(lambda: defaultdict(int))
    for model, u, sub in transcript_usage(session_id(run_dir)):
        role = "sub" if sub else "main"
        row = m2[f"{role}:{model}"]
        for f in FIELDS:
            row[f] += u.get(f, 0) or 0
        row["msgs"] += 1
        its = u.get("iterations") or []
        own = [it for it in its if it.get("type") != "advisor_message"] or [u]
        row["cost_x1e6"] += round(sum(price_of(model, it) for it in own) * 1e6)
        for it in its:
            if it.get("type") == "advisor_message":
                am = short(it.get("model", "?"))
                arow = m2[f"advisor:{it.get('model', '?')}"]
                for f in FIELDS:
                    arow[f] += it.get(f, 0) or 0
                arow["msgs"] += 1
                arow["cost_x1e6"] += round(price_of(it.get("model", "?"), it) * 1e6)
    m1 = {}
    if result:
        for model, u in (result.get("modelUsage") or {}).items():
            m1[short(model)] = {"in": u.get("inputTokens", 0), "out": u.get("outputTokens", 0),
                                "cache_read": u.get("cacheReadInputTokens", 0),
                                "cache_write": u.get("cacheCreationInputTokens", 0),
                                "cost": round(u.get("costUSD", 0), 4), "full_name": model}
    return {"id": meta["id"], "cond": meta["cond"], "wall_s": meta["wall_s"],
            "cost": round((result or {}).get("total_cost_usd", 0), 4),
            "turns": (result or {}).get("num_turns"), "is_error": (result or {}).get("is_error"),
            "cost_computed": round(sum(v["cost_x1e6"] for v in m2.values()) / 1e6, 4),
            "m1": m1, "m2": {k: dict(v) for k, v in m2.items()}}


if __name__ == "__main__":
    root = Path(sys.argv[1])
    rows = [one(d) for d in sorted(root.iterdir()) if (d / "meta.json").exists()]
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    (root.parent / "usage.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
