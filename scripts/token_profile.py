#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev token 经济学剖析器。

读取 work.py --trace 轨迹，估算工作包驱动的上下文成本结构：
  - 每帧（next→check）的工作包字符数/估算 token
  - 服务经济学指标：每请求平均上下文（决定 prefill 成本与 KV 缓存效率）
  - 预算超限告警

估算口径：中文混排按 chars × 0.9 估 token（粗估，真实 usage 需 provider 返回值）。
真正的 serving 数据（prompt/completion、缓存命中）需 provider usage——
本工具是轨迹侧的近似剖析。

用法:
  python scripts/token_profile.py <trace.jsonl> [--budget 8000]
"""

import argparse
import json
import statistics
import sys

TOK_PER_CHAR = 0.9


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="token 经济学剖析器（轨迹侧近似）")
    ap.add_argument("trace")
    ap.add_argument("--budget", type=int, default=8000, help="工作包字符预算（与 work.py 一致）")
    args = ap.parse_args()

    frames = []
    cur = {}
    for line in open(args.trace, encoding="utf-8"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("event") == "next":
            cur = {"package_chars": e.get("package_chars", 0), "blueprint": e.get("blueprint")}
        elif e.get("event") == "check" and cur:
            cur["check_errors"] = e.get("errors", 0)
            frames.append(cur)
            cur = {}

    if not frames:
        print("轨迹中无完整帧（next→check 对）")
        return 0

    chars = [f["package_chars"] for f in frames]
    est_toks = [int(c * TOK_PER_CHAR) for c in chars]
    over = [c for c in chars if c > args.budget]
    err_frames = sum(1 for f in frames if f.get("check_errors", 0) > 0)

    print(f"轨迹: {args.trace}")
    print(f"帧数: {len(frames)}（每帧 = 一个工作包 + 一次全链验证）")
    print(f"工作包字符: mean={int(statistics.mean(chars))} "
          f"median={int(statistics.median(chars))} max={max(chars)} min={min(chars)}")
    print(f"估算 token/帧: mean={int(statistics.mean(est_toks))} max={max(est_toks)}（系数 {TOK_PER_CHAR}）")
    print(f"预算超限: {len(over)}/{len(frames)} 帧 > {args.budget} 字符")
    print(f"含蓝图错误的 check: {err_frames} 帧")
    total_ctx = sum(est_toks)
    print(f"编排器累计注入上下文（估算）: {total_ctx} tokens")
    print("服务视角提示：每请求上下文小而稳定 → prefill 快、KV 缓存友好；")
    print("对比自由发挥式 agent（单请求上下文持续增长至数十万 token），")
    print("本架构把成本从'越来越长的对话'转为'N 个小而重复的请求'。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
