#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev 考古辅助器（屎山模式第 1 步 + 影响面四问的机械部分）。

把 legacy-mode.md 中"依赖图用工具输出构建、fan-in 用 grep 验证、不许凭印象"
变成确定性脚本。零第三方依赖，Python 3.8+。

用法:
  python scripts/archaeology.py <项目根>                    # 依赖图 + fan-in 榜 + 循环依赖
  python scripts/archaeology.py <项目根> --impact <符号>    # 影响面四问 ①②③ 的机械输出
  python scripts/archaeology.py <项目根> --check-cycles     # 有循环依赖则退出码 1（CI 用）
  python scripts/archaeology.py <项目根> --json

语言覆盖:
  Python   ast 精确解析 import / from-import（含相对导入）
  JS/TS    正则解析 import-from / require（仅相对路径）
  Go       go.mod module 前缀匹配 import 路径
其他语言无依赖边，但 --impact 的符号引用搜索仍然有效。

退出码: 0 = 正常；1 = --check-cycles 且存在循环依赖；2 = 用法错误。
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".arch", "__pycache__", "node_modules", "venv", ".venv",
             "dist", "build", "attic", ".idea", ".vscode", ".tmptest", ".tmptest2"}
LANG_BY_EXT = {".py": "python", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
               ".ts": "js", ".tsx": "js", ".go": "go"}
JS_EXT_CANDIDATES = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
                     "/index.ts", "/index.tsx", "/index.js", "/index.jsx"]

JS_IMPORT_RE = re.compile(
    r"""(?:from\s+|require\(\s*|import\s+)['"]([^'"]+)['"]""")
GO_IMPORT_RE = re.compile(r"^\s*(?:_|\w+)\s+\"([^\"]+)\"", re.M)
WORD_RE_TEMPLATE = r"\b{sym}\b"
TEST_FILE_RE = re.compile(r"(^test_.*\.py$|.*\.test\.[jt]sx?$|.*_test\.go$)")


def scan_files(root):
    files = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in LANG_BY_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        try:
            files[rel] = (LANG_BY_EXT[p.suffix], p.read_text(encoding="utf-8",
                                                             errors="replace"))
        except OSError:
            continue
    return files


def resolve_py(module, level, src_rel, root):
    """把 python 模块路径解析为仓库内文件（解析不到返回 None）。"""
    if level:
        base = Path(src_rel).parent
        for _ in range(level - 1):
            base = base.parent
        targets = [base / module.replace(".", "/") if module else base]
    else:
        # 仓库根布局（import a.b）与扁平 src 布局（同目录互导）都尝试
        targets = [Path(module.replace(".", "/")),
                   Path(src_rel).parent / module.replace(".", "/")]
    for target in targets:
        for cand in (target.with_suffix(".py"), target / "__init__.py"):
            if (root / cand).is_file() and cand.as_posix() in files_index:
                return cand.as_posix()
    return None


def py_imports(rel, text, root, edges):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tgt = resolve_py(alias.name, 0, rel, root)
                if tgt:
                    edges[rel].add(tgt)
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names] or [""]
            if node.module:
                tgt = resolve_py(node.module, node.level, rel, root)
                if tgt:
                    edges[rel].add(tgt)
                    continue
            # from . import x / from ..pkg import y 的子模块候选
            for name in names:
                sub = f"{node.module}.{name}" if node.module else name
                tgt = resolve_py(sub, node.level, rel, root)
                if tgt:
                    edges[rel].add(tgt)


def js_imports(rel, text, root, edges):
    for ref in JS_IMPORT_RE.findall(text):
        if not ref.startswith("."):
            continue
        base = (Path(rel).parent / ref).as_posix()
        norm = re.sub(r"/\./", "/", base)
        while "/../" in norm:
            norm = re.sub(r"[^/]+/\.\./", "", norm, count=1)
        for ext in JS_EXT_CANDIDATES:
            cand = norm + ext
            if cand in files_index:
                edges[rel].add(cand)
                break


def go_imports(rel, text, root, module_prefix, edges, go_files_by_dir):
    if not module_prefix:
        return
    for ref in GO_IMPORT_RE.findall(text):
        if ref == module_prefix or not ref.startswith(module_prefix + "/"):
            continue
        sub = ref[len(module_prefix) + 1:]
        for cand in go_files_by_dir:
            if cand.startswith(sub + "/"):
                edges[rel].add(cand)


def find_cycles(edges):
    """三色 DFS 找环（与 validate_blueprint.py 同思路，按文件粒度）。"""
    color = {n: 0 for n in edges}
    cycles, stack = [], []

    def dfs(n):
        color[n] = 1
        stack.append(n)
        for dep in sorted(edges[n]):
            if color.get(dep) == 1:
                cyc = stack[stack.index(dep):] + [dep]
                key = frozenset(cyc)
                if key not in {frozenset(c) for c in cycles}:
                    cycles.append(cyc)
            elif color.get(dep) == 0:
                dfs(dep)
        stack.pop()
        color[n] = 2

    for n in sorted(edges):
        if color[n] == 0:
            dfs(n)
    return cycles


def symbol_refs(files, symbol):
    """符号引用清单: [(file, line)]，词边界匹配。"""
    pat = re.compile(WORD_RE_TEMPLATE.format(sym=re.escape(symbol)))
    refs = []
    for rel, (_, text) in files.items():
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                refs.append((rel, i))
    return refs


def impact_report(files, edges, symbol):
    refs = symbol_refs(files, symbol)
    if not refs:
        return [f"符号 {symbol} 在考古范围内零引用（确认拼写/范围，或它是死代码——入 @DEBT）"]
    out = []
    def_pat = re.compile(r"^\s*(?:def|class|func|function|const|let|var)\s+"
                         + re.escape(symbol) + r"\b")
    def_sites = [(f, ln) for f, ln in refs
                 if def_pat.match(files[f][1].splitlines()[ln - 1])]
    use_sites = [r for r in refs if r not in def_sites]
    out.append(f"影响面四问（机械部分）—— 符号: {symbol}")
    out.append(f"① fan-in（谁引用它）: {len(use_sites)} 处引用 / {len(def_sites)} 处定义")
    for f, ln in use_sites[:20]:
        out.append(f"     {f}:{ln}")
    if len(use_sites) > 20:
        out.append(f"     …共 {len(use_sites)} 处")
    if def_sites:
        def_file = def_sites[0][0]
        out.append(f"② 定义: {def_sites[0][0]}:{def_sites[0][1]}"
                   f"（fan-out 依赖 {len(edges.get(def_file, ()))} 个文件）")
        for dep in sorted(edges.get(def_file, ()))[:10]:
            out.append(f"     → {dep}")
        # ③ 波及面有无无测试区（测试文件直接引用符号，或 import 了依赖方）
        test_refs = {f for f, _ in use_sites if TEST_FILE_RE.match(f.rsplit("/", 1)[-1])}
        dependents = sorted(src for src, tgts in edges.items() if def_file in tgts)
        covered = {dep for dep in dependents
                   if any(dep in edges.get(t, ()) for t in test_refs)}
        untested = [d for d in dependents if d not in covered
                    and not TEST_FILE_RE.match(d.rsplit("/", 1)[-1])]
        out.append(f"③ 测试覆盖: {len(test_refs)} 个测试文件引用该符号；"
                   f"依赖定义文件的 {len(dependents)} 个文件中 "
                   f"{len(untested)} 个无测试关联")
        for d in untested[:10]:
            out.append(f"     ⚠ 无测试: {d}（先补特征测试再动刀）")
    out.append("④ 台账归属（人工判断）: 本次偿还/新增 @DEBT 哪一笔——对照 BLUEPRINT.md 台账")
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="考古辅助器（依赖图 / fan-in / 影响面四问机械部分）")
    ap.add_argument("root", type=Path, help="项目根目录")
    ap.add_argument("--impact", metavar="SYMBOL", default=None,
                    help="输出某符号的影响面四问机械部分（①②③）")
    ap.add_argument("--check-cycles", action="store_true",
                    help="存在循环依赖时退出码 1（CI 用）")
    ap.add_argument("--top", type=int, default=5, help="fan-in 榜单行数（默认 5）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"目录不存在: {root}")
        return 2

    global files_index
    files = scan_files(root)
    files_index = set(files)
    edges = {rel: set() for rel in files}
    go_files_by_dir = [rel for rel, (lang, _) in files.items() if lang == "go"]
    module_prefix = None
    go_mod = root / "go.mod"
    if go_mod.is_file():
        m = re.search(r"^module\s+(\S+)", go_mod.read_text(encoding="utf-8",
                                                            errors="replace"), re.M)
        module_prefix = m.group(1) if m else None

    for rel, (lang, text) in files.items():
        if lang == "python":
            py_imports(rel, text, root, edges)
        elif lang == "js":
            js_imports(rel, text, root, edges)
        else:
            go_imports(rel, text, root, module_prefix, edges, go_files_by_dir)

    fanin = {rel: 0 for rel in files}
    for src, tgts in edges.items():
        for t in tgts:
            fanin[t] += 1
    cycles = find_cycles(edges)

    if args.impact:
        lines = impact_report(files, edges, args.impact)
        if args.json:
            refs = symbol_refs(files, args.impact)
            print(json.dumps({"symbol": args.impact, "refs": refs,
                              "cycles": cycles}, ensure_ascii=False, indent=2))
        else:
            print("\n".join(lines))
        return 0

    if args.json:
        print(json.dumps({
            "root": str(root),
            "files": [{"file": rel, "lang": files[rel][0], "fan_in": fanin[rel],
                       "fan_out": len(edges[rel])} for rel in sorted(files)],
            "cycles": cycles,
        }, ensure_ascii=False, indent=2))
    else:
        by_lang = {}
        for rel, (lang, _) in files.items():
            by_lang[lang] = by_lang.get(lang, 0) + 1
        lang_desc = " / ".join(f"{k} {v}" for k, v in sorted(by_lang.items()))
        print(f"考古范围: {len(files)} 个文件（{lang_desc}），依赖边 "
              f"{sum(len(v) for v in edges.values())} 条")
        top = sorted(files, key=lambda r: (-fanin[r], r))[:args.top]
        print(f"fan-in top {args.top}（被最多文件依赖——动它先看波及面）:")
        for i, rel in enumerate([r for r in top if fanin[r] > 0], 1):
            print(f"  {i}. {rel}  fan-in {fanin[rel]}  fan-out {len(edges[rel])}")
        if cycles:
            print(f"循环依赖: {len(cycles)} 组" +
                  ("（--check-cycles 时退出码 1）" if not args.check_cycles else ""))
            for cyc in cycles[:10]:
                print("  " + " → ".join(cyc))
        else:
            print("循环依赖: 无 ✓")
        orphans = [r for r in sorted(files) if fanin[r] == 0 and not edges[r]]
        if orphans:
            show = f"{len(orphans)} 个（前 5: {'、'.join(orphans[:5])}）"
            print(f"孤儿文件（无入无出，可能是脚本/文档/死代码）: {show}")

    if args.check_cycles and cycles:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
