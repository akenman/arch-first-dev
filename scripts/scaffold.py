#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev 骨架生成器（蓝图编译器的可执行版）。

从 BLUEPRINT.md 生成 Python 代码骨架，把弱模型的自由度压到最低：
  - @DATA   → dataclass（字段/类型机械转换，锁定数据形状）
  - @MODULE → 函数骨架：签名锁定 + 四段契约进 docstring + NotImplementedError
  - 契约测试桩 → tests/test_<module>.py（每接口一个 skip 桩，标注四段声明）
  - 全部生成文件 py_compile 自检

弱模型只需要填充 TODO；接口签名幻觉从机制上不可能（签名来自蓝图）。
自然语言的 pre/post 无法机械翻译为断言——骨架把它们原样放进 docstring 与
测试桩的 skip reason，提醒实现者与测试编写者，不假装已验证。

用法:
  python scripts/scaffold.py <BLUEPRINT.md> [--out DIR]
"""

import argparse
import py_compile
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_blueprint import parse_file  # noqa: E402

TYPE_MAP = {
    "str": "str", "string": "str", "text": "str",
    "int": "int", "integer": "int",
    "float": "float", "number": "float", "decimal": "float",
    "bool": "bool", "boolean": "bool",
    "date": "date", "datetime": "datetime",
    "dict": "dict", "list": "list", "any": "object",
}


def norm_type(raw, indent="    "):
    """蓝图类型 → Python 注解。未知类型保留原名（前向引用），带注释。"""
    t = (raw or "").strip().rstrip(",")
    if not t:
        return None
    t = re.sub(r"//.*$", "", t).strip()
    optional = bool(re.search(r"\|\s*null|null\b\s*$", t, re.I)) or t.endswith("?")
    t = re.sub(r"\?\s*$", "", t)
    t = re.sub(r"\|\s*null", "", t, flags=re.I).strip()
    list_m = re.match(r"^(.+?)\[\]$", t)
    if list_m:
        inner = norm_type(list_m.group(1))
        return f"list[{inner or 'object'}]"
    enum_m = re.match(r"^enum\[", t)
    if enum_m:
        return "str  # enum, 见蓝图"
    base = TYPE_MAP.get(t.lower())
    if base:
        core = base
    elif re.match(r"^[A-Za-z_]\w*$", t):
        core = f'"{t}"'  # 前向引用
    else:
        core = "object  # 复合类型, 见蓝图"
    return f"Optional[{core}]" if optional else core


def split_params(params):
    """按顶层逗号切参数（忽略括号/尖括号内逗号）。"""
    parts, depth, cur = [], 0, ""
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [x.strip() for x in parts if x.strip()]


def parse_data_sections(text):
    """@DATA 段：支持「字段: a:int, b:str」与「每行 a: int // 注释」两种写法。"""
    out = []
    cur = None
    for raw in text.splitlines():
        s = raw.strip()
        m = re.match(r"^@DATA\s+(\w+)", s)
        if m:
            cur = {"name": m.group(1), "lines": []}
            out.append(cur)
            continue
        if cur is None or s.startswith("#") or s.startswith("|") or s.startswith("```"):
            continue
        if re.match(r"^@(?![A-Z])", s) or re.match(r"^@(?!DATA)", s) and re.match(r"^@[A-Z]", s):
            cur = None
            continue
        if s.startswith("---"):
            continue
        cur["lines"].append(s)
    result = []
    for d in out:
        fields = []
        joined = " ".join(d["lines"])
        # 形式1: 字段: a:int, b:str, ...
        m = re.search(r"字段\s*[:：]\s*(.+)", joined)
        if m:
            for piece in m.group(1).split(","):
                fm = re.match(r"^\s*(\w+)\s*[:：]\s*(.+)$", piece.strip())
                if fm:
                    fields.append((fm.group(1), fm.group(2).strip()))
        else:
            # 形式2: 每行 name: type // comment
            for line in d["lines"]:
                fm = re.match(r"^\s*(\w+)\s*[:：]\s*([^\s]+)", line)
                if fm and fm.group(1) not in ("字段",):
                    fields.append((fm.group(1), fm.group(2)))
        result.append({"name": d["name"], "fields": fields})
    return result


def gen_dataclass(d):
    lines = [f"@dataclass\nclass {d['name']}:",
             f'    """{d["name"]} —— 由 BLUEPRINT.md @DATA 生成，字段即契约"""', ""]
    if not d["fields"]:
        lines.append("    pass")
    for name, raw in d["fields"]:
        py = norm_type(raw)
        if py is None:
            lines.append(f"    {name} = None  # 蓝图未给类型")
        elif "  # " in py:
            ann, note = py.split("  # ", 1)
            lines.append(f"    {name}: {ann}  # {note}（原声明: {raw}）")
        else:
            lines.append(f"    {name}: {py}")
    return "\n".join(lines)


def gen_module(mod, blueprint_name):
    parts = [f'"""{mod.name} —— 由 BLUEPRINT.md @MODULE 生成。\n\n实现约束：签名不可改（漂移检测以此为准）；\n契约见各函数 docstring，唯一真相源为 {blueprint_name}。\n"""\n']
    for i in mod.ifaces:
        params = split_params(i.params)
        args = []
        for pr in params:
            pm = re.match(r"^(\w+)\s*[:：]?\s*(.*)$", pr)
            name, t = (pm.group(1), pm.group(2)) if pm else (pr, "")
            ann = norm_type(t)
            args.append(f"{name}: {ann}" if ann and "  # " not in ann else name)
        ret = norm_type(i.ret)
        ret_ann = ""
        if ret and "  # " not in ret:
            ret_ann = f" -> {ret}"
        contract = []
        for key in ("pre", "post", "error", "side-effect"):
            if key in i.behaviors or (key == "pre" and i.behaviors):
                pass
        lines = [f"def {i.name}({', '.join(args)}){ret_ann}:"]
        lines.append(f'    """{i.name} —— 契约（唯一真相源: {blueprint_name} @MODULE {mod.name} → {i.name}）')
        lines.append("")
        for key in ("pre", "post", "error", "side-effect"):
            if key in i.behaviors:
                lines.append(f"    {key}: {i.behaviors[key]}")
        if not i.behaviors:
            lines.append("    契约缺失：先补蓝图再实现（validator W_NO_BEHAVIOR）")
        lines.append('    """')
        lines.append(f'    raise NotImplementedError("{mod.name}.{i.name}: 按 {blueprint_name} 契约实现")')
        parts.append("\n".join(lines) + "\n")
    if not mod.ifaces:
        parts.append("# 蓝图中该模块未声明接口\n")
    header = parts[0]
    body = "\n\n".join(parts[1:])
    imports = "from dataclasses import dataclass  # noqa: F401\nfrom typing import Optional  # noqa: F401\nfrom datetime import date, datetime  # noqa: F401\n\n" if body else ""
    return header + imports + body


def gen_tests(mod):
    if not mod.ifaces:
        return None
    lines = ["import pytest", ""]
    for i in mod.ifaces:
        fn = "test_%s_%s" % (mod.name, i.name)
        post = i.behaviors.get("post", "").replace(chr(34), chr(39))
        beh = ((", ".join(sorted(i.behaviors)) or "契约缺失") + (f" | {post}" if post else "")).replace(chr(34), chr(39))
        lines.append(f'@pytest.mark.skip(reason="TODO 契约测试 [{beh}] — 依据 BLUEPRINT @MODULE {mod.name} → {i.name}")')
        lines.append(f"def {fn}():")
        lines.append(f'    """验证 {i.name} 的四段声明（把 skip 去掉并实现）"""')
        lines.append("    raise NotImplementedError")
        lines.append("")
    return "\n".join(lines)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="蓝图 → Python 骨架（弱模型自由度压缩器）")
    ap.add_argument("blueprint")
    ap.add_argument("--out", default="scaffold_out")
    args = ap.parse_args()

    path = Path(args.blueprint)
    if not path.exists():
        print(f"文件不存在: {path}")
        return 1
    text = path.read_text(encoding="utf-8")
    issues = []
    bp = parse_file(text, issues)
    if not bp.modules:
        print("蓝图未解析出 @MODULE，无法生成")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n_files = 0
    datas = parse_data_sections(text)
    if datas:
        models_src = ("\"\"\"@DATA 生成的数据契约（字段即契约，改字段先改蓝图）\"\"\"\n"
                      "from dataclasses import dataclass\n"
                      "from typing import Optional\n"
                      "from datetime import date, datetime\n\n\n"
                      + "\n\n".join(gen_dataclass(d) for d in datas))
        (out / "models.py").write_text(models_src, encoding="utf-8")
        n_files += 1
    for mod in bp.modules.values():
        (out / f"{mod.name}.py").write_text(gen_module(mod, path.name), encoding="utf-8")
        n_files += 1
        tests = gen_tests(mod)
        if tests:
            tdir = out / "tests"
            tdir.mkdir(exist_ok=True)
            (tdir / f"test_{mod.name}.py").write_text(tests, encoding="utf-8")
            n_files += 1
    (out / "tests" / "__init__.py").write_text("", encoding="utf-8")

    # 入口桩：@VERIFY 命令引用了、但模块生成未覆盖的 .py 文件 → 生成接线桩
    TQ = chr(34) * 3
    referenced = set()
    for v in bp.verifies:
        for m in re.finditer(r"[\w./\\-]+\.py", v.get("run") or ""):
            referenced.add(m.group(0).replace("\\", "/").split("/")[-1])
    generated = {f"{mod.name}.py" for mod in bp.modules.values()} | {"models.py"}
    entries = sorted(referenced - generated - {"conftest.py"})
    for fname in entries:
        hint = "\n".join(
            f"#   {mod.name}: " + ", ".join(i.name for i in mod.ifaces)
            for mod in bp.modules.values() if mod.ifaces
        )
        stub = (
            f"{TQ}{fname} —— 入口桩（scaffold 从 BLUEPRINT @VERIFY 命令反推生成）。\n\n"
            f"@VERIFY 期望本文件可执行。任务：把命令行参数分发到各模块的契约函数，\n"
            f"使命令输出满足 @VERIFY 的 expect-exit / expect-contains。\n"
            f"可用契约函数（签名已锁定，见对应模块文件）：\n{hint}\n{TQ}\n\n\n"
            f'raise NotImplementedError("{fname}: 按 BLUEPRINT @VERIFY 接线命令分发")\n'
        )
        (out / fname).write_text(stub, encoding="utf-8")
        n_files += 1
    if entries:
        print(f"入口桩: {', '.join(entries)}（@VERIFY 引用；实现后其命令应满足期望）")

    # @VERIFY 骨架建议：未覆盖的 @FLOW 生成待填块，写入 out/VERIFY.scaffold.md
    covered = " ".join(v.get("name", "") for v in bp.verifies)
    uncovered = [f for f in bp.flows if f.name not in covered and f.name != "(未命名)"]
    if uncovered:
        blocks = []
        for f in uncovered:
            blocks.append(
                f"  {f.name}:\n"
                f"    run: # TODO: 触发该 @FLOW 的命令\n"
                f"    expect-exit: 0\n"
                f"    expect-not-contains: Traceback"
            )
        suggest = (
            "# @VERIFY 建议骨架（scaffold 生成）\n\n"
            "以下 @FLOW 尚无机器验证。把本块补进 BLUEPRINT.md 的 @VERIFY 段，填好 run 与期望值\n"
            "（命令应可在项目根运行；expect-exit 0 表示成功路径）。\n\n"
            "@VERIFY\n" + "\n".join(blocks) + "\n"
        )
        (out / "VERIFY.scaffold.md").write_text(suggest, encoding="utf-8")
        n_files += 1
        print(f"@VERIFY 建议骨架: {len(uncovered)} 条未覆盖 @FLOW → {out / 'VERIFY.scaffold.md'}")

    # 编译自检：生成的代码必须语法正确
    bad = []
    for py in out.rglob("*.py"):
        try:
            py_compile.compile(str(py), doraise=True)
        except py_compile.PyCompileError as e:
            bad.append(f"{py.name}: {e}")
    if bad:
        print("生成的骨架未通过编译自检：")
        for b in bad:
            print("  " + b)
        return 1
    print(f"骨架已生成: {out}（{n_files} 个文件，编译自检通过）")
    print("下一步：把 TODO 交给实现者填充；签名与 dataclass 不可改（漂移检测以此为准）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
