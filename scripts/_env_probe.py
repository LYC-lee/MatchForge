"""验收环境探针: 检测 LLM / Neo4j / KB 检索 可用性 (只读, 短超时)"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

out = {}

# 1) LLM 连通性
async def probe_llm():
    try:
        from ai.base_agent import get_agent_llm
        llm = get_agent_llm()
        t0 = time.time()
        resp = await llm.ainvoke("回复 ok 两个字即可")
        out["llm"] = {"ok": True, "latency_s": round(time.time() - t0, 2),
                      "sample": str(getattr(resp, "content", resp))[:80]}
    except Exception as e:
        out["llm"] = {"ok": False, "error": str(e)[:300]}

asyncio.run(probe_llm())

# 2) Neo4j 连通性 + 数据量
try:
    from ai.tools.neo4j_client import get_driver
    driver = get_driver()
    with driver.session() as s:
        n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    out["neo4j"] = {"ok": True, "node_count": n}
except Exception as e:
    out["neo4j"] = {"ok": False, "error": str(e)[:300]}

# 3) KB 向量检索 (本地 Milvus, 不走 LLM)
try:
    from kb.rag import answer
    t0 = time.time()
    res = answer("村田 MLCC 产品线", company_id=1)
    out["kb_rag"] = {"ok": True, "intent": res.get("intent"),
                     "retrieved": len(res.get("retrieved", [])),
                     "answer_head": res.get("answer", "")[:80]}
except Exception as e:
    out["kb_rag"] = {"ok": False, "error": str(e)[:300]}

print(json.dumps(out, ensure_ascii=False, indent=2))
