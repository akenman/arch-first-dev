#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev 小模型语义 linter（可插拔）。

设计立场：工具做确定性检查（validator），小模型做廉价语义判断。
"这条契约是否歧义" 是关键词启发式（--lint）覆盖不了的判断——
一次 GLM-Flash/Qwen 级调用比关键词表鲁棒一个量级。

端点配置（OpenAI 兼容接口，环境变量）:
  LINT_BASE_URL   如 http://localhost:11434/v1（Ollama）或服务方端点
  LINT_API_KEY    令牌（本地服务可任意）
  LINT_MODEL      模型名（如 qwen2.5-coder:7b / glm-4-flash）

未配置端点时优雅退出（exit 0，无判定），不阻塞流程。

用法:
  python scripts/lint_model.py <BLUEPRINT.md> [--json]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_blueprint import parse_file  # noqa: E402

PROMPT = """你是架构契约审查员。判断下面的接口契约声明是否歧义——
歧义的定义：两个合格的实现者读同一句话，可能写出行为不同的代码。

典型的歧义：过滤条件未说 AND/OR；排序未说方向；字符串比较未说大小写；
阈值/时序未说边界含否；计数桶可能重叠；格式未说精度/单位；"合理/适当"类措辞。

只输出 JSON（不要其他文字）：
{"ambiguous": true/false, "issues": [{"text": "歧义的具体短语", "why": "两种实现如何不同", "fix": "建议的精确写法"}]}

契约声明（接口 {iface}）：
{contract}"""


def call_model(contract, iface, base_url, api_key, model):
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(iface=iface, contract=contract)}],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def parse_judgment(raw):
    """从模型输出中提取 JSON（容忍 markdown 代码块包裹）。"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip()
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="小模型语义 linter（可插拔端点）")
    ap.add_argument("blueprint")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    base_url = os.environ.get("LINT_BASE_URL")
    api_key = os.environ.get("LINT_API_KEY", "local")
    model = os.environ.get("LINT_MODEL")
    if not base_url or not model:
        print("未配置 LINT_BASE_URL / LINT_MODEL —— 语义 linter 跳过（不阻塞）。")
        print("本地小模型示例（Ollama）:")
        print("  ollama pull qwen2.5-coder:7b")
        print("  export LINT_BASE_URL=http://localhost:11434/v1")
        print("  export LINT_MODEL=qwen2.5-coder:7b")
        return 0

    path = Path(args.blueprint)
    issues = []
    bp = parse_file(path.read_text(encoding="utf-8"), issues)

    findings = []
    n_contracts = 0
    for mod in bp.modules.values():
        for iface in mod.ifaces:
            if not iface.behaviors:
                continue
            contract = "\n".join(f"{k}: {v}" for k, v in iface.behaviors.items())
            iface_id = f"{mod.name}.{iface.name}"
            n_contracts += 1
            try:
                raw = call_model(contract, iface_id, base_url, api_key, model)
            except Exception as e:  # noqa: BLE001
                print(f"[SKIP] {iface_id}: 端点调用失败（{e}）", file=sys.stderr)
                continue
            judge = parse_judgment(raw)
            if judge is None:
                print(f"[SKIP] {iface_id}: 模型输出非 JSON", file=sys.stderr)
                continue
            if judge.get("ambiguous"):
                findings.append({"interface": iface_id, "issues": judge.get("issues", [])})
                for iss in judge.get("issues", []):
                    print(f"[AMBIG] {iface_id}: {iss.get('text', '')} — {iss.get('why', '')}")
                    print(f"        建议: {iss.get('fix', '')}")
            else:
                print(f"[OK] {iface_id}")

    result = {
        "blueprint": str(path),
        "model": model,
        "contracts_checked": n_contracts,
        "ambiguous": findings,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"语义 lint: {n_contracts} 个契约，{len(findings)} 个歧义")
    return 0


if __name__ == "__main__":
    sys.exit(main())
