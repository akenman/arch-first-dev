#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev 工作包编排器（本地小模型模式的核心）。

设计立场：本地小模型（7B-14B 量化，有效上下文 ≤32K，指令遵循弱）读不完
SKILL.md，也不该读。流程知识全部住在本脚本里：

  python scripts/work.py next  <BLUEPRINT.md>
      → 输出下一个最小工作包（当前模块条目 + 依赖签名 + @CROSSCUT + 待填 TODO 块
        + 内联规则），模型只看这一包、只做这一件事
  python scripts/work.py check <BLUEPRINT.md>
      → 全链验证（validator / 阶段门禁 / --verify / 测试），输出明确的下一步

模型永远不需要记住流程——每轮工作包里都写着"完成后运行什么"。
字节预算：工作包默认超过 ~8000 字符会告警（小模型上下文珍贵）。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_blueprint import parse_file, run_verify  # noqa: E402

BUDGET_CHARS = 8000


def slice_section(text, header_prefix):
    """截取从 '@<header_prefix>' 行开始到下一个顶层 @SECTION 的原文。"""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines)
              if l.strip().startswith("@" + header_prefix)
              and re.match(r"^@[A-Z]", l.strip())]
    if not starts:
        return None
    chunks = []
    for start in starts:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            s = lines[j].strip()
            if re.match(r"^@[A-Z]", s) or re.match(r"^#{1,6} ", s):
                end = j
                break
        chunks.append("\n".join(lines[start:end]).rstrip())
    return "\n\n".join(chunks)


def dep_signature_block(bp, text):
    """依赖模块的接口签名 + 行为原文（压缩格式，省 token）。"""
    blocks = []
    for name in bp.modules:
        mod = bp.modules[name]
        if not mod.ifaces:
            continue
        lines = [f"[{name}]"]
        for i in mod.ifaces:
            lines.append(f"  {i.sig}")
            for key in ("pre", "post", "error", "side-effect"):
                if key in i.behaviors:
                    lines.append(f"    {key}: {i.behaviors[key]}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def todo_blocks(src_file, ifaces):
    """从骨架文件里抽出含 NotImplementedError 的待填函数块。"""
    if not src_file or not src_file.exists():
        return None
    src = src_file.read_text(encoding="utf-8", errors="replace")
    blocks = []
    lines = src.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("def "):
            j = i
            while j < len(lines) and not lines[j].lstrip().startswith("raise NotImplementedError"):
                j += 1
            if j < len(lines):
                end = j + 1
                blocks.append("\n".join(lines[i:end]))
                i = end
                continue
        i += 1
    wanted = [b for b in blocks if any(f"def {i.name}(" in b for i in ifaces)]
    return "\n\n\n".join(wanted) if wanted else None


def open_modules(bp):
    def norm(s):
        return (s or "").strip().strip("[]").lower().replace("_", " ")
    opens = [n for n, m in bp.modules.items() if norm(m.status) in ("empty", "in progress")]
    # 按构建层排序，层内按名称
    opens.sort(key=lambda n: (bp.layers.get(n, 99), n))
    return opens


def build_package(bp, text, project_root):
    opens = open_modules(bp)
    parts = []
    if not opens:
        return None
    name = opens[0]
    mod = bp.modules[name]
    layer = bp.layers.get(name, "?")
    parts.append(f"== 工作包：实现模块 [{name}]（构建层 {layer}）==")
    parts.append("规则（必须遵守）：")
    parts.append("  1. 只填充下述函数体，不改任何函数签名、不改 dataclass 字段")
    parts.append("  2. 实现须满足函数 docstring 里的 pre/post/error/side-effect")
    parts.append("  3. 只使用「依赖签名」中列出的函数，不 import 其他模块内部")
    parts.append("  4. 完成后运行下面给出的 check 命令，不要自行判断是否完成")
    parts.append("  5. 实现通过后，把蓝图中本模块状态改为 [done]（@PROGRESS 与 @MODULE 两处都改）")
    entry = slice_section(text, f"MODULE {name}")
    if entry:
        parts.append("-- 本模块蓝图条目 --")
        parts.append(entry)
    deps = getattr(mod, "deps", {})
    if deps:
        parts.append("-- 依赖签名（只能调用这些）--")
        all_sig = dep_signature_block(bp, text)
        for dep in deps:
            m = re.search(rf"\[{re.escape(dep)}\]\n((?:[ \t].*\n?|\n)*?)(?=\n\[|\Z)", all_sig)
            if m:
                parts.append(m.group(0).rstrip())
    cc = slice_section(text, "CROSSCUT")
    if cc:
        parts.append("-- 全局约定 @CROSSCUT --")
        parts.append(cc)
    src_file = None
    for cand in (project_root / "src" / f"{name}.py", project_root / f"{name}.py",
                 project_root / "src" / name / "__init__.py"):
        if cand.exists():
            src_file = cand
            break
    if src_file is None:
        parts.append("-- 骨架未生成，先运行 --")
        parts.append(f"  python scripts/scaffold.py \"{(project_root / 'BLUEPRINT.md')}\" --out \"{project_root / 'src'}\"")
        parts.append(f"  然后填充 src/{name}.py 中的: {', '.join(i.name for i in mod.ifaces)}")
    else:
        todo = todo_blocks(src_file, mod.ifaces)
        if todo:
            rel = src_file.relative_to(project_root) if src_file.is_relative_to(project_root) else src_file
            parts.append(f"-- 待填函数（文件 {rel}，填充后删除 NotImplementedError）--")
            parts.append(todo)
        else:
            parts.append(f"-- src/{name}.py 已无待填函数，确认实现满足契约后进入 check --")
    missing_entries = []
    for v in bp.verifies:
        for m in re.finditer(r"([\w./\-]+\.py)", v.get("run") or ""):
            ref = project_root / m.group(1).replace("/", os.sep)
            if not ref.exists() and m.group(1) not in missing_entries:
                missing_entries.append(m.group(1))
    if missing_entries and name == opens[0] and "cli" in name.lower() or missing_entries and layer in ("3", "4"):
        parts.append("-- 注意：@VERIFY 引用了尚不存在的文件 —— 实现本模块时一并创建 --")
        for me in missing_entries:
            parts.append(f"  {me}（参考蓝图「目录结构」节的入口定义；记录 @CHANGE）")
    parts.append("-- 完成后运行 --")
    parts.append(f"  python scripts/work.py check \"{project_root / 'BLUEPRINT.md'}\"")
    return "\n".join(parts)


def _trace_emit(trace_path, event):
    """追加一条轨迹事件（JSONL）。格式见 references/trajectory-schema.md。"""
    if not trace_path:
        return
    from datetime import datetime, timezone
    rec = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    line = json.dumps(rec, ensure_ascii=False)
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(line + chr(10))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="工作包编排器（本地小模型模式）")
    ap.add_argument("command", choices=["next", "check"])
    ap.add_argument("blueprint", type=Path)
    ap.add_argument("--trace", default=None,
                    help="轨迹事件 JSONL 路径（RLVR/蒸馏数据采集；格式见 references/trajectory-schema.md）")
    args = ap.parse_args()
    path = args.blueprint.resolve()
    if not path.exists():
        print(f"蓝图不存在: {path}")
        return 1
    project_root = path.parent.parent if (path.parent.parent / "src").exists() else path.parent
    text = path.read_text(encoding="utf-8")
    issues = []
    bp = parse_file(text, issues)
    errors = [i for i in issues if i[0] == "error"]

    if args.command == "check":
        hard = list(errors)
        _trace_emit(args.trace, {"event": "check", "blueprint": str(path),
                                 "errors": len(errors), "open_modules": open_modules(bp)})
        if hard:
            print(f"check: 蓝图错误 {len(hard)} 条 —— 先修蓝图：")
            for _, code, line, msg in hard:
                print(f"  [{code}] line {line}: {msg}")
            print("下一步：修复后重新运行 check")
            return 1
        opens = open_modules(bp)
        if opens:
            print(f"check: 蓝图 OK；尚未完成的模块: {opens}")
            print("下一步：python scripts/work.py next <BLUEPRINT.md>")
            return 0
        print("check: 蓝图 OK；全部模块完成 → 进入 Phase 3 机器验证")
        rc = run_verify(path, bp)
        _trace_emit(args.trace, {"event": "verify", "blueprint": str(path), "exit": rc})
        print("下一步（原样运行）：")
        print(f'  python scripts/validate_blueprint.py "{path}" --signatures')
        print("  然后在 BLUEPRINT.md 末尾的 @CHANGE 段追加一条，格式模仿已有条目：")
        print("    @CHANGE_00N / 阶段: Phase 3 / 触发: 实现完成 / 修改: 无 / 影响: 无")
        print("  若上面有 [FAIL]，先修复对应 @FLOW 的实现再重跑 check")
        return rc

    # next
    if errors:
        print("当前蓝图有错误，先修复再开发：")
        for _, code, line, msg in errors:
            print(f"  [{code}] line {line}: {msg}")
        return 1
    opens = open_modules(bp)
    if not opens:
        print("全部模块已完成 → 运行 check 进入 Phase 3 机器验证")
        return 0
    pkg = build_package(bp, text, project_root)
    if pkg is None:
        print("无待办模块")
        return 0
    _trace_emit(args.trace, {"event": "next", "blueprint": str(path),
                             "package_chars": len(pkg),
                             "open_modules": open_modules(bp)})
    print(pkg)
    size = len(pkg)
    if size > BUDGET_CHARS:
        print(f"\n[警告] 工作包 {size} 字符，超过小模型预算 {BUDGET_CHARS} —— "
              f"考虑把模块拆小或压缩蓝图条目")
    return 0


if __name__ == "__main__":
    sys.exit(main())
