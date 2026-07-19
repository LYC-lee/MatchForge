"""验证导入"""
import sys
sys.path.insert(0, r"D:\Reference\LLM-Base\MatchForge")
from api.main import main
print("OK:", type(main).__name__)
