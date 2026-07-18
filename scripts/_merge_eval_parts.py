"""合并分段评测结果 -> scripts/eval_current.json, 并立为首测基线 eval_baseline.json"""
import json
import glob

results = []
for f in sorted(glob.glob("scripts/eval_part_*.json")):
    data = json.load(open(f, encoding="utf-8"))
    results.extend(data["results"])

spec = [r for r in results if r["category"] == "spec_parse"]
ref = [r for r in results if r["category"] == "kb_refusal"]
red = [r for r in results if r["category"] == "alt_redline"]

summary = {
    "total": len(results),
    "accuracy": round(sum(r["accuracy"] for r in spec) / len(spec), 4) if spec else 0,
    "refusal_correctness": round(sum(1 for r in ref if r["passed"]) / len(ref), 4) if ref else 0,
    "hallucination_block": round(sum(1 for r in red if r["passed"]) / len(red), 4) if red else 0,
    "overall_pass_rate": round(sum(1 for r in results if r["passed"]) / len(results), 4) if results else 0,
    "by_category": {},
}
for r in results:
    c = summary["by_category"].setdefault(r["category"], {"total": 0, "passed": 0})
    c["total"] += 1
    if r["passed"]:
        c["passed"] += 1

out = {"summary": summary, "results": results}
for path in ("scripts/eval_current.json", "scripts/eval_baseline.json"):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
