#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev RLVR 分层奖励函数。

对 <task_dir>（含任务蓝图）与 <solution_dir>（执行者的产出）计算分层奖励：

  L1 结构（0.25）   解答的 BLUEPRINT.md 通过 validate_blueprint.py（0 错误）
  L2 一致（0.25）   --check-code：代码签名与解答蓝图的 SIGNATURES.json 基线一致
  L3 行为（0.40）   --verify：蓝图中 @VERIFY 机器命令的通过率
  L4 覆盖（0.10）   @VERIFY 对 @FLOW 的覆盖率（未写验证的流是奖励漏洞）

奖励全部来自确定性脚本，零 LLM 偏差；反 reward-hacking 纵深：
结构（可由"迁就烂代码改蓝图"骗过）← 行为层（@VERIFY 必须真实运行通过）兜底。
退出码恒为 0，分数即信号（RL 用）；--min-score 可选阈值门禁。

用法:
  python scripts/reward.py <task_dir> <solution_dir> [--json]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).parent
WEIGHTS = {"l1_structure": 0.25, "l2_consistency": 0.25, "l3_behavior": 0.40, "l4_coverage": 0.10}


def _run(cmd, cwd):
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def layer1_structure(solution):
    bp = solution / ".arch" / "BLUEPRINT.md"
    if not bp.exists():
        for alt in solution.rglob("BLUEPRINT.md"):
            bp = alt
            break
    if not bp.exists():
        return False, "解答中无 BLUEPRINT.md", bp
    r = _run(f'"{sys.executable}" "{SKILL_SCRIPTS / "validate_blueprint.py"}" "{bp}"', solution)
    ok = r.returncode == 0
    return ok, (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "", bp


def layer2_consistency(solution, bp):
    r = _run(f'"{sys.executable}" "{SKILL_SCRIPTS / "validate_blueprint.py"}" "{bp}" --check-code',
             solution)
    return r.returncode == 0, (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""


def layer3_and_4(solution, bp):
    """--verify 通过率（L3）与 @FLOW 覆盖率（L4）。"""
    r = _run(f'"{sys.executable}" "{SKILL_SCRIPTS / "validate_blueprint.py"}" "{bp}" --verify',
             solution)
    out = r.stdout or ""
    passed = fails = 0
    for line in out.splitlines():
        if line.startswith("[PASS]"):
            passed += 1
        elif line.startswith("[FAIL]"):
            fails += 1
    total_runs = passed + fails
    behavior = (passed / total_runs) if total_runs else 0.0

    covered = uncovered = 0
    vb = bp.read_text(encoding="utf-8")
    vsec = None
    flow_names = []
    for raw in vb.splitlines():
        s = raw.strip()
        if s.startswith("@VERIFY"):
            vsec = True
            continue
        if re.match(r"^@[A-Z]", s):
            vsec = None
        if vsec is None and s.startswith("@FLOW"):
            flow_names.append(s[5:].strip().split("（")[0])
        if vsec and s.endswith(":") and not s.startswith(("run", "expect")):
            nm = s[:-1].strip()
            if nm in " ".join(flow_names):
                covered += 1
            else:
                uncovered += 1
    total_flows = len(flow_names) or 1
    coverage = covered / total_flows
    return behavior, coverage, r.returncode, out


import re  # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="RLVR 分层奖励")
    ap.add_argument("task_dir")
    ap.add_argument("solution_dir")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-score", type=float, default=None,
                    help="门禁阈值：低于该分数时退出码 1（CI 用）")
    args = ap.parse_args()

    task = Path(args.task_dir).resolve()
    solution = Path(args.solution_dir).resolve()
    if not (task / "task.json").exists():
        print(f"任务目录无效: {task}")
        return 2

    ok1, msg1, bp = layer1_structure(solution)
    ok2, msg2 = (layer2_consistency(solution, bp) if ok1 else (False, "L1 未通过，跳过"))
    if ok1 and ok2:
        behavior, coverage, vrc, vout = layer3_and_4(solution, bp)
    else:
        behavior, coverage, vrc, vout = 0.0, 0.0, 1, ""

    layers = {
        "l1_structure": 1.0 if ok1 else 0.0,
        "l2_consistency": 1.0 if ok2 else 0.0,
        "l3_behavior": round(behavior, 4),
        "l4_coverage": round(coverage, 4),
    }
    score = round(sum(layers[k] * WEIGHTS[k] for k in WEIGHTS), 4)
    result = {
        "task": task.name,
        "score": score,
        "weights": WEIGHTS,
        "layers": layers,
        "details": {"l1": msg1, "l2": msg2,
                    "verify_passed": vout.count("[PASS]"), "verify_failed": vout.count("[FAIL]")},
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"任务: {task.name}")
        for k, v in layers.items():
            print(f"  {k:<16} {v}  (权重 {WEIGHTS[k]})")
        print(f"总分: {score}")
        if vout:
            for line in vout.splitlines():
                if line.startswith(("[PASS]", "[FAIL]", "verify:")):
                    print("  " + line)
    if args.min_score is not None and score < args.min_score:
        print(f"低于门禁阈值 {args.min_score}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
