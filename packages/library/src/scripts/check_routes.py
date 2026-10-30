"""检查 app.py 的所有路由和函数"""
import re
import ast

with open('src/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取所有路由
routes = re.findall(r"@app\.route\(['\"](/[^'\"]+)", content)
print(f"=== 路由列表 ({len(routes)}) ===")
for r in sorted(set(routes)):
    print(f"  {r}")

# 提取所有函数
tree = ast.parse(content)
funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
print(f"\n=== 函数列表 ({len(funcs)}) ===")
for f in funcs:
    print(f"  {f}")
