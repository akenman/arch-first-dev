#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev 解析器模糊测试。

奖励函数的可信度取决于解析器的鲁棒性——正则解析自然语言 Markdown 是
reward-hacking 的最大攻击面。本脚本对有效蓝图施加系统性变异，要求：
  1. 解析器在任何变异下不崩溃（硬性）
  2. 语义保持类变异（空白/换行/引号风格）下模块/接口计数不变（软性）
  3. 破坏类变异（截断/段落删除）下解析器要么报结构错误要么数量单调减少（软性）

用法:
  python scripts/fuzz_parser.py --n 500 [--seed 42]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_blueprint import parse_file  # noqa: E402

MUTATIONS = [
    "crlf", "tabs", "fullwidth_colon", "bom", "unicode_space", "header_case",
    "insert_md_header", "insert_table_row", "insert_code_fence", "truncate",
    "drop_section", "dup_section", "reorder_lines", "inject_at_line",
    "strip_indent", "extra_blank", "zwsp", "long_line",
]


def mutate(text, kind, rng):
    lines = text.splitlines()
    if kind == "crlf":
        return text.replace("\n", "\r\n")
    if kind == "tabs":
        return "\n".join(("    " + l) if l.startswith("  ") else l for l in lines)
    if kind == "fullwidth_colon":
        return text.replace(": ", "：").replace(":", "：", 1) if rng.random() < 0.5 else text.replace("：", ":")
    if kind == "bom":
        return "﻿" + text
    if kind == "unicode_space":
        return text.replace(" ", " ", rng.randint(1, 10))
    if kind == "header_case":
        return "\n".join(l.upper() if l.strip().startswith("@") else l for l in lines)
    if kind == "insert_md_header":
        pos = rng.randrange(len(lines) + 1)
        return "\n".join(lines[:pos] + ["## 注入的标题", "---"] + lines[pos:])
    if kind == "insert_table_row":
        pos = rng.randrange(len(lines) + 1)
        return "\n".join(lines[:pos] + ["| a | b |", "|---|---|"] + lines[pos:])
    if kind == "insert_code_fence":
        pos = rng.randrange(len(lines) + 1)
        return "\n".join(lines[:pos] + ["```"] + lines[pos:])
    if kind == "truncate":
        return "\n".join(lines[: rng.randrange(1, len(lines))])
    if kind == "drop_section":
        idx = [i for i, l in enumerate(lines) if l.strip().startswith("@")]
        if not idx:
            return text
        s = rng.choice(idx)
        e = min(s + rng.randint(1, 10), len(lines))
        return "\n".join(lines[:s] + lines[e:])
    if kind == "dup_section":
        idx = [i for i, l in enumerate(lines) if l.strip().startswith("@")]
        if not idx:
            return text
        s = rng.choice(idx)
        e = min(s + rng.randint(2, 8), len(lines))
        return "\n".join(lines[:e] + lines[s:e] + lines[e:])
    if kind == "reorder_lines":
        body = lines[:]
        head, tail = body[:2], body[2:]
        rng.shuffle(tail)
        return "\n".join(head + tail)
    if kind == "inject_at_line":
        pos = rng.randrange(len(lines) + 1)
        return "\n".join(lines[:pos] + ["@FAKE_SECTION some content"] + lines[pos:])
    if kind == "strip_indent":
        return "\n".join(l.lstrip() for l in lines)
    if kind == "extra_blank":
        out = []
        for l in lines:
            out.append(l)
            if rng.random() < 0.15:
                out.append("")
        return "\n".join(out)
    if kind == "zwsp":
        pos = rng.randrange(len(text) + 1)
        return text[:pos] + "​" + text[pos:]
    if kind == "long_line":
        pos = rng.randrange(len(lines) + 1)
        return "\n".join(lines[:pos] + ["x" * 5000] + lines[pos:])
    return text


def counts(text):
    issues = []
    bp = parse_file(text, issues)
    n_iface = sum(len(m.ifaces) for m in bp.modules.values())
    errors = sum(1 for i in issues if i[0] == "error")
    return {"modules": len(bp.modules), "ifaces": n_iface,
            "flows": len(bp.flows), "errors": errors}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="蓝图解析器模糊测试")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--blueprints", nargs="*", default=None)
    args = ap.parse_args()

    base_files = args.blueprints or [
        str(Path(__file__).parent.parent / "examples" / "task-cli" / "BLUEPRINT.md"),
        str(Path(__file__).parent.parent / "test-project" / "url-shortener" / ".arch" / "BLUEPRINT.md"),
    ]
    corpus = [(Path(f).name, Path(f).read_text(encoding="utf-8")) for f in base_files]

    rng = random.Random(args.seed)
    crashes, semantic_breaks = [], []
    for i in range(args.n):
        name, text = corpus[i % len(corpus)]
        kind = MUTATIONS[i % len(MUTATIONS)]
        mutated = mutate(text, kind, rng)
        base = counts(text)
        try:
            got = counts(mutated)
        except Exception as e:  # noqa: BLE001
            crashes.append((i, name, kind, repr(e)[:120]))
            continue
        # 语义保持类变异不允许改变计数
        if kind in ("crlf", "tabs", "bom", "unicode_space", "zwsp", "extra_blank", "fullwidth_colon"):
            if (got["modules"], got["ifaces"], got["flows"]) != (base["modules"], base["ifaces"], base["flows"]):
                semantic_breaks.append((i, name, kind, base, got))

    print(f"变异 {args.n} 次（{len(corpus)} 个基线蓝图 × {len(MUTATIONS)} 种变异）")
    print(f"崩溃: {len(crashes)}")
    for c in crashes:
        print("  CRASH", c)
    print(f"语义保持类计数漂移: {len(semantic_breaks)}")
    for s in semantic_breaks:
        print("  SEMANTIC", s)
    if crashes or semantic_breaks:
        return 1
    print("PASS：解析器在全部变异下不崩溃且语义稳定")
    return 0


if __name__ == "__main__":
    sys.exit(main())
