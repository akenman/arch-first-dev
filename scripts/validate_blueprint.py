#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev 蓝图静态检查器。

把 SKILL.md 中原本依赖"模型自觉"的机械检查变成确定性代码：
预检 ②③⑥⑦、约束 6（接口有消费者）、@PROGRESS 与 @MODULE 状态一致性、
BUILD_ORDER 逆依赖、签名快照生成。零第三方依赖，Python 3.8+。

用法:
  python scripts/validate_blueprint.py <path/to/BLUEPRINT.md> [--signatures] [--lenient] [--json]
  python scripts/validate_blueprint.py <BLUEPRINT.md> --verify            # 执行 @VERIFY 机器验证
  python scripts/validate_blueprint.py <BLUEPRINT.md> --gate phase2      # 阶段门禁
  python scripts/validate_blueprint.py <BLUEPRINT.md> --check-code    # 代码签名 vs 基线（反向漂移门禁）
  python scripts/validate_blueprint.py <BLUEPRINT.md> --lint           # 歧义 lint（弱模型项目建议）
  python scripts/validate_blueprint.py --selftest

退出码: 0 = 无错误（警告不算）；1 = 存在错误；2 = selftest 失败。

错误（阻断）:
  E_MISSING_SECTION   缺少 @MODULE / @FLOW / @BUILD_ORDER 必需段落
  E_GHOST_DEP         依赖指向不存在的模块（预检 ③）
  E_CYCLE             模块依赖存在环（预检 ⑥）
  E_DUP_IFACE         接口名全局重复（预检 ⑦）
  E_IFACE_NO_CONSUMER 接口未出现在任何 @FLOW（约束 6；--lenient 降级为警告）
  E_STATE_MISMATCH    @PROGRESS 与 @MODULE 状态不一致，或 PROGRESS 引用不存在的模块
  E_STATE_INVALID     模块状态不在枚举内（预检 ①）
  E_MODULE_NO_STATUS  @MODULE 缺少 状态 字段（预检 ①）
  E_BUILD_ORDER       @BUILD_ORDER 出现逆依赖（预检 ②）
  E_FLOW_UNKNOWN_MODULE @FLOW「涉及」的模块不存在（预检 ④）
  E_DEBT_MISSING_FIELD @DEBT_NNN 条目缺少必填字段（位置/类型/证据/影响/状态）
  E_DEBT_STATE_INVALID @DEBT 状态不在 open|repaying|retired（屎山台账）

警告（不阻断）:
  W_NO_BEHAVIOR        接口没有任何 pre/post/error/side-effect 声明
  W_DEP_FUNC_UNKNOWN   依赖声明的函数在目标模块接口中不存在（签名漂移信号）
  W_NO_FAULT_MODE      @EXTERNAL 未声明故障模式
  W_CONTRACT_FILE_MISSING  @EXTERNAL 契约文件引用在磁盘上找不到
  W_NO_VERSION         @META 缺少 version
  W_LAYER_NONMINIMAL   @BUILD_ORDER 层号大于依赖推导的最小层号
  W_IFACE_STYLE        接口行不符合 name(params) → ret 约定
  W_MODULE_NO_DESC     @MODULE 缺少 职责 字段
  W_UNKNOWN_SECTION    未知的 @段落（拼写错误？）
  W_DEBT_UNKNOWN_TYPE  @DEBT 类型不在标准枚举（上帝模块/循环依赖/…）

签名门禁:
  --check-signatures   将当前蓝图生成的签名/契约 hash 与既有 SIGNATURES.json
                       比对，发现漂移（新增/删除/变更）则退出码 1 —— 供 CI
                       强制"代码接口变更必须同步蓝图"
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {"empty", "in progress", "done", "deferred", "wontfix", "removed"}
DEBT_STATES = {"open", "repaying", "retired"}
DEBT_TYPES = {"上帝模块", "循环依赖", "越界调用", "死代码", "魔法常量", "行为可疑", "无测试热区"}
DEBT_REQUIRED_FIELDS = ("位置", "类型", "证据", "影响", "状态")
BEHAVIOR_KEYS = {"pre", "post", "error", "side-effect", "side_effect"}
REQUIRED_SECTIONS = {"MODULE", "FLOW", "BUILD_ORDER"}

SECTION_RE = re.compile(r"^@([A-Z][A-Z_]*?)(?:_(\d+))?(?:\s+(.*))?$")
FIELD_RE = re.compile(r"^(职责|接口|依赖|状态)\s*[:：]\s*(.*)$")
IFACE_RE = re.compile(
    r"^-?\s*([A-Za-z_]\w*)\s*\((.*)\)\s*(?:→|->)\s*(.+)$"
)
IFACE_NO_ARROW_RE = re.compile(r"^-?\s*([A-Za-z_]\w*)\s*\(")
BEHAVIOR_RE = re.compile(r"^(pre|post|error|side-effect|side_effect)\s*[:：]")
CALL_RE = re.compile(r"([A-Za-z_]\w*)\s*\(")
DEP_RE = re.compile(r"([A-Za-z_]\w*)\s*(?:→|->)")
LAYER_CN_RE = re.compile(r"^第\s*(\d+)\s*层[^:：]*[:：]\s*(.+)$")
LAYER_NUM_RE = re.compile(r"^(\d+)\.\s*([A-Za-z_]\w*)")
PROGRESS_RE = re.compile(r"^([A-Za-z_]\w*)\s*:?\s*(?:[█▓▒░ ]*\[(.+?)\])?\s*$")
DEBT_FIELD_RE = re.compile(r"^(位置|类型|证据|影响|偿还计划|状态)\s*[:：]\s*(.*)$")


def norm_status(raw):
    s = raw.strip().strip("[]").strip().lower().replace("_", " ")
    return s


class Interface:
    def __init__(self, name, params, ret, line):
        self.name = name
        self.params = params.strip()
        self.ret = ret.strip()
        self.line = line
        self.behaviors = {}  # key -> 原文（pre/post/error/side-effect）

    @property
    def sig(self):
        arrow = "->" if self.ret else ""
        return f"{self.name}({self.params}) {arrow} {self.ret}".replace("  ", " ").strip()


class Module:
    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.desc = ""
        self.ifaces = []
        self.deps = {}          # dep_module -> set(func names)
        self.status = None


class Flow:
    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.lines = []
        self.involves = []


class Blueprint:
    def __init__(self):
        self.version = None
        self.progress = {}       # name -> raw status
        self.modules = {}
        self.flows = []
        self.layers = {}         # module -> layer
        self.externals = []      # (name, has_fault_mode, line)
        self.verifies = []       # @VERIFY 条目: {name, run, expect_exit, contains, not_contains}
        self.sections = set()
        self.unknown_sections = []   # (name, line)
        self.debts = []          # @DEBT_NNN 条目: {id, line, fields}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="arch-first-dev 蓝图静态检查器")
    ap.add_argument("blueprint", nargs="?", help="BLUEPRINT.md 路径")
    ap.add_argument("--signatures", action="store_true",
                    help="生成/更新同目录 SIGNATURES.json（含 @EXTERNAL 契约文件 sha256）")
    ap.add_argument("--check-signatures", action="store_true",
                    help="CI 门禁：签名/契约 hash 对比既有 SIGNATURES.json，漂移则退出码 1")
    ap.add_argument("--verify", action="store_true",
                    help="执行蓝图 @VERIFY 段的机器可验证命令（Phase 3 ⑦ 脚本化）")
    ap.add_argument("--gate", choices=["phase1", "phase2", "phase3"],
                    help="阶段门禁：进入下一阶段的机械前置条件检查")
    ap.add_argument("--check-code", action="store_true",
                    help="代码侧漂移门禁：AST 实际函数签名 vs SIGNATURES.json（仅 Python）")
    ap.add_argument("--code-root", default=None,
                    help="代码根目录（默认 = 蓝图上级项目根）")
    ap.add_argument("--lint", action="store_true",
                    help="蓝图歧义 lint：标记弱模型无法猜惯例的措辞（advisory，不改退出码）")
    ap.add_argument("--export-json", action="store_true",
                    help="导出结构化 JSON（typed schema，供机器消费/约束解码）")
    ap.add_argument("--lenient", action="store_true",
                    help="E_IFACE_NO_CONSUMER 降级为警告（渐进采用期使用）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--selftest", action="store_true", help="运行内置自测")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if not args.blueprint:
        ap.error("需要 BLUEPRINT.md 路径，或 --selftest")

    path = Path(args.blueprint)
    if not path.exists():
        print(f"文件不存在: {path}")
        sys.exit(1)

    issues = []
    bp = parse_file(path.read_text(encoding="utf-8"), issues)
    contracts = resolve_contracts(bp, path, issues)

    # ---- 拓扑与一致性检查 ----
    run_checks(bp, issues, lenient=args.lenient)
    if args.lint:
        lint_ambiguity(bp, issues)

    errors = [i for i in issues if i[0] == "error"]
    warnings = [i for i in issues if i[0] == "warning"]

    n_ifaces = sum(len(m.ifaces) for m in bp.modules.values())
    if n_ifaces <= 8:
        mode = "微项目档（速度优先）"
    elif n_ifaces <= 15:
        mode = "简化模式"
    else:
        mode = "完整模式"

    if args.signatures:
        sig_path = write_signatures(path, bp, contracts)
        if not args.json:
            print(f"已生成 {sig_path}")

    if args.check_signatures:
        sys.exit(check_signatures(path, bp, contracts))

    if args.verify:
        sys.exit(run_verify(path, bp))

    if args.gate:
        sys.exit(gate(path, bp, args.gate, issues))

    if args.check_code:
        root = Path(args.code_root) if args.code_root else             (path.parent.parent if (path.parent.parent / "src").exists()
             or (path.parent.parent / "main.py").exists() else path.parent)
        sys.exit(check_code(path, root))

    if args.export_json:
        out = export_json(path, bp)
        print(f"已导出结构化蓝图: {out}")
        return 0

    if args.json:
        print(json.dumps({
            "file": str(path),
            "mode": mode,
            "stats": {
                "modules": len(bp.modules),
                "interfaces": n_ifaces,
                "flows": len(bp.flows),
            },
            "errors": [fmt_issue(i) for i in errors],
            "warnings": [fmt_issue(i) for i in warnings],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"蓝图: {path}")
        print(f"模块 {len(bp.modules)} | 接口 {n_ifaces} | 数据流 {len(bp.flows)} | 判定: {mode}")
        for sev, items in (("错误", errors), ("警告", warnings)):
            for _, code, line, msg in items:
                print(f"  [{sev}] {code} (line {line}): {msg}")
        if not errors and not warnings:
            print("  全部检查通过 ✓")
        print(f"结果: {len(errors)} 错误, {len(warnings)} 警告")

    sys.exit(1 if errors else 0)


# ---- 解析器（单遍状态机，段落名用局部变量传递） ----

INVISIBLE_CHARS = ("​", "‌", "‍", "﻿")
SPACE_CHARS = {" ": " ", "　": " "}


def normalize(text):
    """归一化：剥离零宽字符、统一非常规空白。

    防两类风险：隐形字符注入使接口静默脱离解析（奖励漏洞）；
    全角/不间断空格导致的解析不稳定。
    """
    for ch in INVISIBLE_CHARS:
        text = text.replace(ch, "")
    for ch, rep in SPACE_CHARS.items():
        text = text.replace(ch, rep)
    return text


def parse_file(text, issues):
    """真正的解析入口：把 parse() 的段落名问题在这里收拢。"""
    text = normalize(text)
    bp = Blueprint()
    section_name = None
    cur_module = None
    cur_flow = None
    cur_external = None
    cur_debt = None
    in_fence = False
    field = None
    field_indent = 0

    def add(sev, code, line, msg):
        issues.append((sev, code, line, msg))

    for idx, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped == "---":
            continue

        m = SECTION_RE.match(stripped)
        if m:
            base = m.group(1)
            rest = (m.group(3) or "").strip()
            bp.sections.add(base)
            section_name = base
            cur_module, cur_flow, cur_external, cur_debt = None, None, None, None
            field, field_indent = None, 0
            known = {
                "META", "PROGRESS", "MODULE", "FLOW", "DATA", "BUILD_ORDER",
                "CROSSCUT", "EXTERNAL", "ERROR_CHAIN", "DECISION", "CHANGE",
                "RESTRUCTURE", "CHECKPOINT", "HEALTH_SCORE", "DEBT", "VERIFY",
            }
            if base not in known:
                bp.unknown_sections.append((base, idx))
                add("warning", "W_UNKNOWN_SECTION", idx, f"未知段落 @{base}")
            if base == "MODULE":
                if not rest:
                    add("error", "E_MODULE_NO_STATUS", idx, "@MODULE 缺少模块名")
                else:
                    cur_module = Module(rest, idx)
                    bp.modules[rest] = cur_module
            elif base == "FLOW":
                cur_flow = Flow(rest or "(未命名)", idx)
                bp.flows.append(cur_flow)
            elif base == "EXTERNAL":
                cur_external = {"name": rest, "fault": False, "contract": None, "line": idx}
                bp.externals.append(cur_external)
            elif base == "DEBT" and m.group(2):
                # @DEBT_001 即台账条目；裸 @DEBT 只当段落头（格式见 references/legacy-mode.md）
                cur_debt = {"id": f"DEBT_{m.group(2)}", "line": idx, "fields": {}}
                bp.debts.append(cur_debt)
            continue

        if section_name == "META":
            vm = re.match(r"version\s*[:：]\s*(\S+)", stripped)
            if vm:
                bp.version = vm.group(1)
            continue

        if section_name == "PROGRESS":
            pm = PROGRESS_RE.match(stripped)
            if pm and pm.group(2):
                bp.progress[pm.group(1)] = pm.group(2)
            continue

        if section_name == "BUILD_ORDER":
            lm = LAYER_CN_RE.match(stripped)
            if lm:
                layer = int(lm.group(1))
                for name in re.split(r"[,，、]", lm.group(2)):
                    name = name.strip()
                    if name:
                        bp.layers[name] = layer
                continue
            lm = LAYER_NUM_RE.match(stripped)
            if lm:
                bp.layers[lm.group(2)] = int(lm.group(1))
            continue

        if section_name == "VERIFY":
            em = re.match(r"^(.+?)\s*[:：]\s*$", stripped)
            fm2 = re.match(r"^(run|expect-exit|expect-contains|expect-not-contains)\s*[:：]\s*(.*)$", stripped)
            if fm2 and bp.verifies:
                key, val = fm2.group(1), fm2.group(2).strip()
                if key == "run":
                    bp.verifies[-1]["run"] = val
                elif key == "expect-exit":
                    bp.verifies[-1]["expect_exit"] = int(val) if val.strip().isdigit() else val
                elif key == "expect-contains":
                    bp.verifies[-1]["contains"].append(val)
                else:
                    bp.verifies[-1]["not_contains"].append(val)
            elif em and not stripped.startswith(("run", "expect")):
                bp.verifies.append({"name": em.group(1).strip(), "run": None,
                                    "expect_exit": 0, "contains": [], "not_contains": []})
            continue

        if section_name == "DEBT" and cur_debt is not None:
            dm = DEBT_FIELD_RE.match(stripped)
            if dm:
                cur_debt["fields"][dm.group(1)] = dm.group(2).strip()
            continue

        if cur_module is not None:
            fm = FIELD_RE.match(stripped)
            if fm:
                field = fm.group(1)
                field_indent = len(line) - len(line.lstrip())
                value = fm.group(2).strip()
                if field == "职责":
                    cur_module.desc = cur_module.desc or value
                elif field == "状态":
                    cur_module.status = value
                elif field == "依赖":
                    _parse_dep(cur_module, value)
                continue
            if field == "接口":
                indent = len(line) - len(line.lstrip())
                if indent <= field_indent:
                    continue
                bm = re.match(r"^(pre|post|error|side-effect|side_effect)\s*[:：]\s*(.*)$", stripped)
                if bm and cur_module.ifaces:
                    key = bm.group(1)
                    triple_dq, triple_sq = chr(34) * 3, chr(39) * 3
                    text = bm.group(2).strip().replace(triple_dq, triple_sq)
                    cur_module.ifaces[-1].behaviors[
                        "side-effect" if key.startswith("side") else key
                    ] = text
                    continue
                im = IFACE_RE.match(stripped)
                if im:
                    cur_module.ifaces.append(
                        Interface(im.group(1), im.group(2), im.group(3), idx)
                    )
                    continue
                im2 = IFACE_NO_ARROW_RE.match(stripped)
                if im2:
                    add("warning", "W_IFACE_STYLE", idx,
                        f"接口 {im2.group(1)} 缺少 '→ 返回类型'")
                    cur_module.ifaces.append(Interface(im2.group(1), "", "", idx))
                    continue
                add("warning", "W_IFACE_STYLE", idx,
                    f"接口行不符合 name(params) → ret 约定: {stripped[:60]}")
            elif field == "依赖":
                indent = len(line) - len(line.lstrip())
                if indent > field_indent:
                    _parse_dep(cur_module, stripped)
            continue

        if cur_flow is not None:
            cur_flow.lines.append(stripped)
            iv = re.match(r"涉及\s*[:：]\s*(.+)$", stripped)
            if iv:
                cur_flow.involves = [
                    x.strip() for x in re.split(r"[,，、]", iv.group(1)) if x.strip()
                ]
            continue

        if cur_external is not None:
            if stripped.startswith("故障模式"):
                cur_external["fault"] = True
            elif stripped.startswith("契约文件"):
                cm = re.match(r"契约文件\s*[:：]\s*(\S+)", stripped)
                if cm:
                    cur_external["contract"] = cm.group(1)
            elif stripped.startswith("类型"):
                tm = re.match(r"类型\s*[:：]\s*(.+)$", stripped)
                if tm:
                    cur_external["type"] = tm.group(1).strip()
            elif re.match(r"^(幂等|重试|超时|事务)", stripped):
                cur_external.setdefault("slots", set()).add(stripped.split(":")[0].split("：")[0].strip())

    return bp


def _parse_dep(module, text):
    dm = DEP_RE.search(text)
    if not dm:
        return
    dep = dm.group(1)
    tail = text.split(dm.group(0), 1)[1]
    funcs = set(CALL_RE.findall(tail))
    module.deps.setdefault(dep, set()).update(funcs)


def run_checks(bp, issues, lenient=False):
    def add(sev, code, line, msg):
        issues.append((sev, code, line, msg))

    for sec in REQUIRED_SECTIONS:
        if sec not in bp.sections:
            add("error", "E_MISSING_SECTION", 0, f"缺少必需段落 @{sec}")
    if bp.version is None:
        add("warning", "W_NO_VERSION", 0, "@META 缺少 version")

    # 预检 ③ 幽灵依赖
    for mod in bp.modules.values():
        for dep in mod.deps:
            if dep not in bp.modules:
                add("error", "E_GHOST_DEP", mod.line,
                    f"模块 {mod.name} 依赖不存在的模块 {dep}")

    # 预检 ⑥ 循环依赖（DFS）
    color = {n: 0 for n in bp.modules}
    stack = []

    def dfs(n):
        color[n] = 1
        stack.append(n)
        for dep in bp.modules[n].deps:
            if dep not in bp.modules:
                continue
            if color[dep] == 1:
                cyc = stack[stack.index(dep):] + [dep]
                add("error", "E_CYCLE", bp.modules[n].line,
                    "循环依赖: " + " → ".join(cyc))
            elif color[dep] == 0:
                dfs(dep)
        stack.pop()
        color[n] = 2

    for n in bp.modules:
        if color[n] == 0:
            dfs(n)

    # 预检 ⑦ 接口名唯一
    seen = {}
    for mod in bp.modules.values():
        for iface in mod.ifaces:
            if iface.name in seen:
                add("error", "E_DUP_IFACE", iface.line,
                    f"接口 {iface.name} 同时定义于 {seen[iface.name]} 和 {mod.name}")
            else:
                seen[iface.name] = mod.name

    # 约束 6 接口有消费者
    called = set()
    for flow in bp.flows:
        for text in flow.lines:
            called.update(CALL_RE.findall(text))
    for mod in bp.modules.values():
        for iface in mod.ifaces:
            if iface.name not in called:
                sev = "warning" if lenient else "error"
                add(sev, "E_IFACE_NO_CONSUMER", iface.line,
                    f"接口 {mod.name}.{iface.name} 未出现在任何 @FLOW（约束 6）")

    # 状态一致性与枚举
    for mod in bp.modules.values():
        if mod.status is None:
            add("error", "E_MODULE_NO_STATUS", mod.line,
                f"模块 {mod.name} 缺少 状态 字段（预检 ①）")
        elif norm_status(mod.status) not in STATUSES:
            add("error", "E_STATE_INVALID", mod.line,
                f"模块 {mod.name} 状态非法: {mod.status}")
        if not mod.desc:
            add("warning", "W_MODULE_NO_DESC", mod.line,
                f"模块 {mod.name} 缺少 职责 字段")
        for iface in mod.ifaces:
            if not iface.behaviors:
                add("warning", "W_NO_BEHAVIOR", iface.line,
                    f"接口 {mod.name}.{iface.name} 没有任何行为声明")
        for dep, funcs in mod.deps.items():
            if dep in bp.modules:
                dep_names = {i.name for i in bp.modules[dep].ifaces}
                for f in funcs:
                    if f not in dep_names:
                        add("warning", "W_DEP_FUNC_UNKNOWN", mod.line,
                            f"{mod.name} 依赖声明的 {dep}.{f}() 不在其接口中（签名漂移？）")

    prog_norm = {}
    for name, st in bp.progress.items():
        if name not in bp.modules:
            add("error", "E_STATE_MISMATCH", 0,
                f"@PROGRESS 中的 {name} 不存在于 @MODULE")
        else:
            prog_norm[name] = norm_status(st)
    for name, mod in bp.modules.items():
        if mod.status is None:
            continue
        ms = norm_status(mod.status)
        if name not in prog_norm:
            add("warning", "W_STATE_NOT_IN_PROGRESS", mod.line,
                f"模块 {name} 未出现在 @PROGRESS")
        elif prog_norm[name] != ms:
            add("error", "E_STATE_MISMATCH", mod.line,
                f"模块 {name} 状态不一致: @PROGRESS={prog_norm[name]} vs @MODULE={ms}")

    # 预检 ④ @FLOW 涉及的模块存在
    for flow in bp.flows:
        for name in flow.involves:
            if name not in bp.modules:
                add("error", "E_FLOW_UNKNOWN_MODULE", flow.line,
                    f"@FLOW {flow.name} 涉及不存在的模块 {name}")

    # 预检 ② BUILD_ORDER（bp.layers 在解析阶段已填充）
    for mod_name, layer in bp.layers.items():
        if mod_name not in bp.modules:
            add("error", "E_BUILD_ORDER", 0,
                f"@BUILD_ORDER 包含不存在的模块 {mod_name}")
            continue
        max_dep_layer = 0
        for dep in bp.modules[mod_name].deps:
            if dep in bp.layers:
                max_dep_layer = max(max_dep_layer, bp.layers[dep])
        if layer <= max_dep_layer:
            add("error", "E_BUILD_ORDER", 0,
                f"@BUILD_ORDER 逆依赖: {mod_name} 在第 {layer} 层，"
                f"但其依赖在第 {max_dep_layer} 层")
        elif layer > max_dep_layer + 1:
            add("warning", "W_LAYER_NONMINIMAL", 0,
                f"{mod_name} 层号 {layer} 大于最小可行层 {max_dep_layer + 1}")
    for name in bp.modules:
        if name not in bp.layers and bp.layers:
            add("warning", "W_NO_LAYER", 0, f"模块 {name} 未出现在 @BUILD_ORDER")

    # @EXTERNAL 故障模式 + 有状态槽位
    STATEFUL = ("数据库", "API", "消息队列", "队列", "MQ", "缓存")
    for ext in bp.externals:
        if not ext["fault"]:
            add("warning", "W_NO_FAULT_MODE", ext["line"],
                f"@EXTERNAL {ext['name']} 未声明故障模式")
        etype = ext.get("type") or ""
        if any(s in etype for s in STATEFUL):
            slots = ext.get("slots", set())
            if len(slots) < 4:
                add("warning", "W_EXTERNAL_STATE_SLOTS", ext["line"],
                    f"@EXTERNAL {ext['name']}（{etype}）状态槽位不足 "
                    f"{len(slots)}/4（需：幂等性/重试/超时/事务边界）")

    # @DEBT 台账结构（屎山模式；格式见 references/legacy-mode.md）
    for debt in bp.debts:
        fields = debt["fields"]
        for req in DEBT_REQUIRED_FIELDS:
            if req not in fields:
                add("error", "E_DEBT_MISSING_FIELD", debt["line"],
                    f"{debt['id']} 缺少「{req}」字段")
        st = fields.get("状态")
        if st is not None and norm_status(st) not in DEBT_STATES:
            add("error", "E_DEBT_STATE_INVALID", debt["line"],
                f"{debt['id']} 状态非法: {st}（open|repaying|retired）")
        t = fields.get("类型")
        if t is not None:
            unknown = [tok.strip() for tok in re.split(r"[|｜]", t)
                       if tok.strip() and tok.strip() not in DEBT_TYPES]
            if unknown:
                add("warning", "W_DEBT_UNKNOWN_TYPE", debt["line"],
                    f"{debt['id']} 类型「{unknown[0]}」不在标准枚举"
                    f"（上帝模块/循环依赖/越界调用/死代码/魔法常量/行为可疑/无测试热区）")


def resolve_contracts(bp, blueprint_path, issues):
    """解析 @EXTERNAL 的「契约文件: <path>」引用：存在性检查 + sha256 快照。

    解析顺序：蓝图所在目录 → 项目根（蓝图上一级）→ 当前工作目录。
    找不到 → W_CONTRACT_FILE_MISSING（不阻断：蓝图与代码可能分仓）。
    """
    import hashlib
    contracts = {}
    bases = [blueprint_path.parent, blueprint_path.parent.parent, Path.cwd()]
    for ext in bp.externals:
        ref = ext.get("contract")
        if not ref:
            continue
        for base in bases:
            cand = (base / ref).resolve()
            if cand.exists():
                contracts[ext["name"]] = {
                    "file": ref,
                    "resolved": str(cand),
                    "sha256": hashlib.sha256(cand.read_bytes()).hexdigest(),
                }
                break
        else:
            issues.append(("warning", "W_CONTRACT_FILE_MISSING", ext["line"],
                           f"@EXTERNAL {ext['name']} 契约文件 {ref} 未找到"
                           f"（相对蓝图目录/项目根/CWD 均不存在）"))
    return contracts


def write_signatures(path, bp, contracts=None):
    sig = {
        "_meta": {
            "tool": "scripts/validate_blueprint.py",
            "blueprint": path.name,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
        "_contracts": contracts or {},
    }
    for mod in bp.modules.values():
        sig[mod.name] = {i.name: i.sig for i in mod.ifaces}
    out = path.parent / "SIGNATURES.json"
    out.write_text(
        json.dumps(sig, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out


def check_signatures(path, bp, contracts):
    """CI 门禁：当前蓝图签名/契约 hash vs 既有 SIGNATURES.json，漂移则退出码 1。

    用于强制"代码接口变更必须同步蓝图"：正常流程是改代码的人同时改蓝图并
    --signatures 重新生成快照提交；漏改的人会被此检查拦下。
    """
    existing_path = path.parent / "SIGNATURES.json"
    if not existing_path.exists():
        print("无 SIGNATURES.json 基准 —— 先运行 --signatures 生成并提交，然后此检查才可门禁")
        return 1
    try:
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"SIGNATURES.json 不可读: {e}")
        return 1

    drift = []
    fresh = {m.name: {i.name: i.sig for i in m.ifaces} for m in bp.modules.values()}
    ex_modules = {k: v for k, v in existing.items() if not k.startswith("_")}
    for mod, ifaces in fresh.items():
        if mod not in ex_modules:
            drift.append(f"新增模块 {mod}")
            continue
        ex_if = ex_modules[mod]
        for name, sig in ifaces.items():
            if name not in ex_if:
                drift.append(f"新增接口 {mod}.{name}")
            elif ex_if[name] != sig:
                drift.append(f"签名变更 {mod}.{name}: {ex_if[name]} → {sig}")
        for name in ex_if:
            if name not in ifaces:
                drift.append(f"删除接口 {mod}.{name}")
    for mod in ex_modules:
        if mod not in fresh:
            drift.append(f"删除模块 {mod}")

    ex_contracts = existing.get("_contracts", {})
    for name, c in (contracts or {}).items():
        if name not in ex_contracts:
            drift.append(f"新增契约引用 {name} ({c['file']})")
        elif ex_contracts[name].get("sha256") != c["sha256"]:
            drift.append(f"契约文件内容变更 {name} ({c['file']})")
    for name in ex_contracts:
        if name not in (contracts or {}):
            drift.append(f"契约引用移除 {name}")

    if drift:
        print("签名/契约漂移 —— 代码或契约文件已变而蓝图未同步：")
        for d in drift:
            print(f"  - {d}")
        print("处理：更新 BLUEPRINT.md 后运行 --signatures 重新生成快照提交")
        return 1
    print("签名/契约与基线一致 ✓")
    return 0


def run_verify(path, bp):
    """执行蓝图 @VERIFY 中的机器可验证命令——Phase 3 ⑦ 从模型判断变成脚本事实。"""
    if not bp.verifies:
        print("蓝图无 @VERIFY 段 —— Phase 3 ⑦ 需模型执行（弱模型建议补 @VERIFY）")
        return 0
    cwd = path.parent.parent if (path.parent.parent / "src").exists() or         (path.parent.parent / "main.py").exists() else path.parent
    failed = 0
    for e in bp.verifies:
        if not e["run"]:
            print(f"[SKIP] {e['name']}: 缺 run 命令")
            continue
        r = subprocess.run(e["run"], shell=True, cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        problems = []
        want = e["expect_exit"]
        if isinstance(want, int) and r.returncode != want:
            problems.append(f"exit={r.returncode} (期望 {want})")
        for s in e["contains"]:
            if s not in out:
                problems.append(f"输出缺少 {s!r}")
        for s in e["not_contains"]:
            if s in out:
                problems.append(f"输出不应包含 {s!r}")
        status = "PASS" if not problems else "FAIL"
        if problems:
            failed += 1
        print(f"[{status}] {e['name']}: {e['run']}")
        for pr in problems:
            print(f"       {pr}")
    print(f"verify: {len(bp.verifies) - failed}/{len(bp.verifies)} 通过")
    return 1 if failed else 0


def gate(path, bp, which, issues):
    """阶段门禁：进入下一阶段的机械前置条件。弱模型从这里拿到明确的下一步。"""
    errors = [i for i in issues if i[0] == "error"]
    if which == "phase1":
        req = []
        if errors:
            req.append(f"蓝图检查错误 {len(errors)} 条（先修复）")
        if bp.version is None:
            req.append("@META 缺 version")
        if not bp.flows:
            req.append("无 @FLOW")
        if req:
            print(f"GATE phase1: 未通过")
            for r in req:
                print(f"  - {r}")
            return 1
        print("GATE phase1: 通过 ✓（可进入 Phase 2）")
        return 0
    if which == "phase2":
        req = [r for r in [f"蓝图检查错误 {len(errors)} 条（先修复）"] if errors]
        def _norm(s):
            return (s or "").strip().strip("[]").lower().replace("_", " ")
        open_mods = [n for n, m in bp.modules.items()
                     if _norm(m.status) in ("empty", "in progress")]
        if open_mods:
            req.append(f"未完成模块: {open_mods}（实现或标 [deferred] 并记 @CHANGE）")
        if req:
            print("GATE phase2: 未通过")
            for r in req:
                print(f"  - {r}")
            return 1
        print("GATE phase2: 通过 ✓（可进入 Phase 3）")
        return 0
    if which == "phase3":
        req = [r for r in [f"蓝图检查错误 {len(errors)} 条（先修复）"] if errors]
        sig = path.parent / "SIGNATURES.json"
        if not sig.exists():
            req.append("SIGNATURES.json 不存在（先 --signatures 生成并提交）")
        if not bp.verifies:
            req.append("无 @VERIFY 段（弱模型必须补：把每条 @FLOW 的验证命令写进蓝图）")
        if req:
            print("GATE phase3: 未通过")
            for r in req:
                print(f"  - {r}")
            return 1
        print("GATE phase3: 前置 ✓（执行 --verify 跑机器验证）")
        return run_verify(path, bp)
    print(f"未知门禁: {which}（phase1|phase2|phase3）")
    return 2


AMBIG_TERMS = ["合理", "适当", "一些", "若干", "尽快", "及时", "大约", "左右",
               "类似", "正常", "常规", "等等", "必要时", "相关"]


def lint_ambiguity(bp, issues):
    """蓝图歧义 lint（--lint，advisory）：标记弱模型无法猜惯例的措辞。

    依据：受限模拟实测——强模型能脑补的约定（过滤 AND/OR、大小写、排序方向、
    边界含否、求和桶互斥性），小模型会各自发明实现。规则刻意保守，宁可少报。
    """
    for mod in bp.modules.values():
        for iface in mod.ifaces:
            for key in ("pre", "post", "error", "side-effect"):
                text = iface.behaviors.get(key)
                if not text:
                    continue
                where = f"{mod.name}.{iface.name} {key}"
                for term in AMBIG_TERMS:
                    if term in text:
                        issues.append(("warning", "W_AMBIG_TERM", iface.line,
                                       f"{where} 含模糊措辞「{term}」——改成可判定的条件"))
                        break
                if key != "post":
                    continue
                if re.search(r"=\s*\w+\s*\+\s*\w+", text):
                    issues.append(("warning", "W_AMBIG_SUM", iface.line,
                                   f"{where} 求和各桶需声明互斥/归属规则（弱模型无法猜）"))
                if re.search(r"排序|sort", text, re.I) and not re.search(r"升序|降序|asc|desc", text, re.I):
                    issues.append(("warning", "W_AMBIG_SORT", iface.line,
                                   f"{where} 涉及排序未声明方向（升序/降序）"))
                has_match = re.search(r"搜索|匹配|关键字|keyword|查找", text, re.I)
                regex_given = re.search(r"\[a-z|\[A-Z|\[0-9|\^|\$", text, re.I)
                if has_match and not regex_given and                         not re.search(r"忽略大小写|区分大小写|大小写", text):
                    issues.append(("warning", "W_AMBIG_CASE", iface.line,
                                   f"{where} 涉及匹配未声明大小写敏感性"))
                if re.search(r"之前|之后|超过|以上|以下|以内", text) and                         not re.search(r"含|≥|≤|<|>|大于|小于|边界", text):
                    issues.append(("warning", "W_AMBIG_BOUNDARY", iface.line,
                                   f"{where} 涉及时序/阈值未声明边界含否"))


def check_code(path, code_root):
    """代码侧漂移门禁：AST 扫描实际函数签名 vs SIGNATURES.json（蓝图派生基线）。

    堵住反向盲区：--check-signatures 只能抓"蓝图改了代码没改"；
    本命令抓"代码被手改而蓝图未同步"。
    覆盖：接口未实现 / 签名不一致（参数名按序比对）/ 未声明的公开函数。
    已知边界：仅 Python；忽略 _ 前缀、dunder、入口名 main、tests/。
    """
    import json as _json
    sig_path = path.parent / "SIGNATURES.json"
    if not sig_path.exists():
        print("无 SIGNATURES.json 基线 —— 先运行 --signatures 生成并提交")
        return 1
    sig = _json.loads(sig_path.read_text(encoding="utf-8"))
    expected = {}
    for mod, ifaces in sig.items():
        if mod.startswith("_"):
            continue
        for name, s in ifaces.items():
            m = re.match(r"^\s*\w+\s*\((.*)\)", s)
            params = []
            if m and m.group(1).strip():
                depth, cur = 0, ""
                pieces = []
                for ch in m.group(1):
                    if ch in "([{":
                        depth += 1
                    elif ch in ")]}":
                        depth -= 1
                    if ch == "," and depth == 0:
                        pieces.append(cur)
                        cur = ""
                    else:
                        cur += ch
                if cur.strip():
                    pieces.append(cur)
                for piece in pieces:
                    token = piece.strip().split(":")[0].split("=")[0].strip()
                    if token:
                        params.append(token)
            expected[name] = params

    actual = {}
    skip_dirs = {".arch", ".git", "__pycache__", "tests", "node_modules", "venv", ".venv", "attic"}
    for py in Path(code_root).rglob("*.py"):
        if any(part in skip_dirs or part.startswith("test_") or part == "conftest.py"
               for part in py.parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in list(node.args.posonlyargs) + list(node.args.args)
                          + list(node.args.kwonlyargs) if a.arg not in ("self", "cls")]
                actual.setdefault(node.name, []).append((str(py.relative_to(code_root)), params))

    drift = []
    for name, params in expected.items():
        if name not in actual:
            drift.append(f"接口未实现: {name}（蓝图有，代码无）")
            continue
        for rel, code_params in actual[name]:
            if code_params != params:
                drift.append(f"签名不一致: {name} 蓝图({','.join(params)}) vs "
                             f"代码({','.join(code_params)}) @{rel}")
    allowed_extra = {"main"}
    for name, sites in actual.items():
        if name in expected or name.startswith("_") or name in allowed_extra:
            continue
        if name.startswith("__"):
            continue
        for rel, _ in sites:
            drift.append(f"未声明函数: {name} @{rel}（公开函数不在蓝图——补蓝图或改名 _ 前缀）")

    if drift:
        print(f"check-code: 代码与签名基线漂移 {len(drift)} 处 ——")
        for d in drift:
            print(f"  [DRIFT] {d}")
        print("处理：改代码 → 同步 BLUEPRINT.md → --signatures 重新生成基线提交")
        return 1
    print(f"check-code: 代码与签名基线一致 ✓（比对 {len(expected)} 个接口）")
    return 0


def export_json(path, bp, out_path=None):
    """蓝图 → 结构化 JSON（typed schema 演进第一步）。

    Markdown 是人读视图；机器消费（RLVR 奖励/工具链/未来约束解码）应使用本导出。
    schema 见 schema/blueprint.schema.json。
    """
    from scaffold import parse_data_sections  # 惰性导入避免循环
    data = parse_data_sections(path.read_text(encoding="utf-8"))
    doc = {
        "schema": "arch-first-dev/blueprint@1",
        "meta": {"version": bp.version, "source": path.name},
        "progress": dict(bp.progress),
        "modules": [
            {"name": m.name, "description": m.desc, "status": m.status,
             "deps": sorted(m.deps), "interfaces": [
                 {"name": i.name, "params": i.params, "returns": i.ret,
                  "behaviors": dict(i.behaviors)} for i in m.ifaces]}
            for m in bp.modules.values()],
        "flows": [{"name": f.name, "involves": f.involves, "steps": f.lines} for f in bp.flows],
        "build_order": bp.layers,
        "externals": [{"name": e["name"], "type": e.get("type"), "fault_mode": e["fault"],
                       "contract_file": e.get("contract")} for e in bp.externals],
        "data": data,
        "verify": bp.verifies,
    }
    out = Path(out_path) if out_path else path.parent / "blueprint.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    return out


def fmt_issue(issue):
    sev, code, line, msg = issue
    return {"severity": sev, "code": code, "line": line, "message": msg}


def selftest():
    """内置自测：坏蓝图必须命中全部植入错误，好蓝图必须零错误。"""
    bad = """\
# 测试蓝图（坏）
@META
  version: 1.0

@PROGRESS
  alpha: [done]
  ghost_mod: [empty]

@MODULE alpha
  职责: 测试模块 A
  接口:
    fa() -> int
      post: 返回 1
    shared() -> int
      post: 返回 2
  依赖: beta → fb()
  状态: [done]

@MODULE beta
  职责: 测试模块 B
  接口:
    fb() -> int
      post: 返回 2
  依赖: alpha → fa()
  状态: [done]

@MODULE gamma
  职责: 测试模块 C
  接口:
    orphan() -> int
      post: 返回 3
    shared() -> int
      post: 返回 4
  依赖: delta → foo()
  状态: [黄了]

@EXTERNAL 支付网关
  类型: 第三方 API
  契约文件: contracts/payment.yaml
  故障模式: 超时 → 重试 1 次 → 抛 PaymentError

@DEBT_001
  类型: 上帝模块
  证据: fan-in 12 / 零测试覆盖
  影响: 任何改动波及 12 个消费方
  状态: [半还]

@BUILD_ORDER
  第 1 层: alpha, beta
  第 2 层: gamma

@FLOW 测试流
  步骤: 用户 → alpha.fa() → beta.fb() → 完成
  涉及: alpha, beta, delta
"""
    good = """\
@META
  version: 1.0

@PROGRESS
  core: [done]

@MODULE core
  职责: 核心逻辑
  接口:
    run(x: int) -> int
      pre: x > 0
      post: 返回 x 的两倍
      error: x <= 0 时抛 ValueError
  状态: [done]

@BUILD_ORDER
  第 1 层: core

@FLOW 主流程
  步骤: 用户 → core.run() → 终端
  涉及: core

@DEBT_001
  位置: src/core.py
  类型: 死代码
  证据: 全仓零引用
  影响: 无运行时影响
  状态: [open]
"""
    issues = []
    bad_bp = parse_file(bad, issues)
    resolve_contracts(bad_bp, Path("BLUEPRINT.md"), issues)
    run_checks(bad_bp, issues)
    codes = {i[1] for i in issues if i[0] == "error"}
    expected = {
        "E_GHOST_DEP", "E_CYCLE", "E_DUP_IFACE", "E_IFACE_NO_CONSUMER",
        "E_STATE_MISMATCH", "E_STATE_INVALID", "E_BUILD_ORDER",
        "E_FLOW_UNKNOWN_MODULE", "E_DEBT_MISSING_FIELD", "E_DEBT_STATE_INVALID",
    }
    missing = expected - codes
    unexpected = codes - expected

    issues2 = []
    good_bp = parse_file(good, issues2)
    run_checks(good_bp, issues2)
    good_errors = [i for i in issues2 if i[0] == "error"]

    warns = {i[1] for i in issues if i[0] == "warning"}
    ok = True
    if "W_CONTRACT_FILE_MISSING" not in warns:
        print("FAIL: 契约文件缺失警告未触发")
        ok = False
    if "W_EXTERNAL_STATE_SLOTS" not in warns:
        print("FAIL: 有状态外部依赖槽位警告未触发")
        ok = False
    if missing:
        print(f"FAIL: 坏蓝图未命中预期错误: {sorted(missing)}")
        ok = False
    if unexpected:
        print(f"FAIL: 坑蓝图出现非预期错误: {sorted(unexpected)}")
        ok = False
    if good_errors:
        print(f"FAIL: 好蓝图被误报: {good_errors}")
        ok = False
    if ok:
        print(f"selftest PASS: 植入错误全部命中 {sorted(expected)}，好蓝图零误报")
        return 0
    for i in issues:
        print("  ", i)
    return 2


if __name__ == "__main__":
    main()
