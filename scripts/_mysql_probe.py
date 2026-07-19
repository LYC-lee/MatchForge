"""MySQL 供应商数据探针 (只读)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

out = {}
try:
    from ai.tools.mysql_client import get_engine
    from sqlalchemy import text
    eng = get_engine()
    with eng.connect() as conn:
        tables = [r[0] for r in conn.execute(text("SHOW TABLES"))]
        out["tables"] = tables
        for t in tables:
            if "supplier" in t.lower() or "part" in t.lower():
                c = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
                out[t] = c
except Exception as e:
    out["error"] = str(e)[:300]
print(json.dumps(out, ensure_ascii=False, indent=2))
