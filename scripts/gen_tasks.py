#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch-first-dev RLVR 任务生成器。

把 patterns 的 crud-cli 模式参数化，批量生成多文件、契约驱动、机器可验证的任务：
每个任务 = 一份规范 BLUEPRINT.md（含 @VERIFY 契约） + task.json（参数与 held-out 标记）。

奖励完全来自确定性验证器（validator / --check-code / --verify），
不需要参考答案——这是多文件 RLVR 任务与传统"带金标答案"任务的核心区别。

用法:
  python scripts/gen_tasks.py --n 12 --seed 42 --out env/tasks
生成的 env/tasks/<task-id>/ 下有 BLUEPRINT.md 与 task.json；held_out 标记的任务
只用于评测，禁止进入任何训练数据（防污染）。
"""

import argparse
import json
import random
import sys
from pathlib import Path

ENTITIES = [
    ("todo", "待办事项", ["title:str", "priority:str", "due:str|null"], ["add", "list", "done"]),
    ("book", "图书", ["title:str", "author:str", "isbn:str"], ["add", "list", "remove"]),
    ("contact", "联系人", ["name:str", "phone:str", "email:str|null"], ["add", "list", "remove"]),
    ("product", "库存商品", ["name:str", "price:float", "stock:int"], ["add", "list", "restock"]),
    ("expense", "记账条目", ["amount:float", "kind:str", "category:str"], ["add", "list", "stats"]),
    ("link", "收藏链接", ["url:str", "tags:str", "note:str|null"], ["add", "list", "remove"]),
]

# 每实体一个"聚合查询"流（统计/汇总），保证任务间存在真实的跨模块数据流差异
AGG = {
    "todo": ("progress", "按状态聚合：done 与未完成各自计数"),
    "book": ("count_by_author", "按作者聚合书目数"),
    "contact": ("count_by_domain", "按 email 域名聚合联系人数"),
    "product": ("inventory_value", "库存总价值（price*stock 求和）"),
    "expense": ("monthly_total", "按月份聚合支出总额"),
    "link": ("tag_cloud", "按 tag 聚合计数"),
}

KIND_RULES = {
    "todo": "priority ∈ {high, medium, low}",
    "book": "isbn 为 10 或 13 位数字/连字符",
    "contact": "phone 为 6-20 位数字/连字符",
    "product": "price >= 0；stock >= 0",
    "expense": "amount > 0；kind ∈ {income, expense}",
    "link": "url 以 http:// 或 https:// 开头",
}


def gen_blueprint(task_id, entity, entity_cn, fields, cmds, agg_name, agg_desc, seed):
    store, svc, cli = f"{entity}_store", f"{entity}_svc", "cli"
    add_cmd, list_cmd, third_cmd = cmds
    req_fields = "、".join(f.split(":")[0] for f in fields)
    field_lines = "\n".join(f"  {n}: {t}" for n, t in (f.split(":") for f in fields))
    third_rule = KIND_RULES[entity]

    return f"""# 项目蓝图 — {entity_cn}管理 CLI（任务 {task_id}）

@META
  version: 1.0
  pattern: crud-cli
  seed: {seed}

@PROGRESS
  {store}   [empty]
  {svc}     [empty]
  {cli}     [empty]

@MODULE {store}
  职责: {entity_cn}记录的 JSON 文件持久化（data/{entity}.json）
  接口:
    load_all() -> list
      post: 返回记录列表；文件不存在返回空列表
      error: 文件损坏（JSON 解析失败）时返回空列表（降级，不抛异常）
      side-effect: 无
    append_one(item: dict) -> int
      pre: item 含必填字段 {req_fields}
      post: 返回自增整数 id（max(现有id)+1，空集为 1）；记录追加进文件
      error: 必填字段缺失抛 ValueError
      side-effect: 持久化文件追加一条记录
    remove_one(rid: int) -> bool
      pre: rid > 0
      post: 存在则删除返回 True；不存在返回 False（幂等）
      side-effect: 删除时持久化文件移除该记录
  状态: [empty]
  依赖: 无（直接使用 @EXTERNAL json 文件）

@MODULE {svc}
  职责: {entity_cn}业务校验与聚合查询
  接口:
    create(items: list, payload: dict) -> dict
      pre: payload 满足：{third_rule}
      post: 校验通过时调用 {store}.append_one 并返回含 id 的完整记录
      error: 校验失败抛 ValueError（消息含字段名）
      side-effect: 经 {store}.append_one 持久化一条记录
    aggregate(items: list) -> dict
      pre: items 中每条记录含聚合所需字段
      post: {agg_desc}；返回 dict 且键为聚合维度
      error: 无
      side-effect: 无
  状态: [empty]
  依赖: {store} → load_all(), append_one()

@MODULE {cli}
  职责: 命令行入口，参数分发与输出
  接口:
    run(argv: list) -> int
      pre: argv 为命令行参数列表
      post: 按 {add_cmd}/{list_cmd}/{third_cmd} 子命令分发；成功 exit 0，业务错误 exit 1 且打印含 "error:" 的提示
      error: 未知子命令 exit 2
      side-effect: {add_cmd} 子命令经 {svc}.create 持久化一条记录
  状态: [empty]
  依赖: {svc} → create(), aggregate()
        {store} → load_all(), remove_one()

@FLOW 新增{entity_cn}
  步骤: 用户 → {cli}.run() → {svc}.create() → {store}.append_one() → 终端
  涉及: {cli}, {svc}, {store}

@FLOW {agg_name}聚合
  步骤: 用户 → {cli}.run() → {svc}.aggregate() → {store}.load_all() → 终端
  涉及: {cli}, {svc}, {store}

@FLOW 删除{entity_cn}
  步骤: 用户 → {cli}.run() → {store}.remove_one() → 终端
  涉及: {cli}, {store}

@DATA {entity_cn.capitalize()}
{field_lines}

@BUILD_ORDER
  第 1 层: {store}
  第 2 层: {svc}
  第 3 层: {cli}

@CROSSCUT 错误处理
  策略: 存储层降级不抛异常；业务层非法参数抛 ValueError；CLI 层捕获后打印 error: 前缀并返回退出码

@EXTERNAL {entity}.json
  类型: 本地 JSON 文件存储
  契约: 记录列表，结构与 @DATA 一致
  幂等性: append_one 非幂等（每次追加）；remove_one 幂等
  重试: 无（本地文件）
  超时: 无
  事务边界: 每次写操作整文件覆盖写
  故障模式: 磁盘满/只读 → 异常向上传播，CLI 打印 error:

@VERIFY
  {add_cmd}成功路径:
    run: python src/main.py {add_cmd} --demo
    expect-exit: 0
    expect-not-contains: Traceback
  {list_cmd}成功路径:
    run: python src/main.py {list_cmd}
    expect-exit: 0
    expect-not-contains: Traceback
  {third_cmd}路径:
    run: python src/main.py {third_cmd} --demo
    expect-exit: 0
    expect-not-contains: Traceback
"""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="RLVR 任务生成器（crud-cli 模式）")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="env/tasks")
    ap.add_argument("--held-out-ratio", type=float, default=0.3)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    tasks = []
    for i in range(args.n):
        entity, entity_cn, fields, cmds = ENTITIES[i % len(ENTITIES)]
        agg_name, agg_desc = AGG[entity]
        # 字段轻微扰动，避免任务同构
        fields = list(fields)
        if rng.random() < 0.5:
            fields.append("note:str|null")
        seed = args.seed * 1000 + i
        task_id = f"crud-{entity}-{i:03d}"
        held_out = (i / max(args.n - 1, 1)) < args.held_out_ratio if args.n > 1 else False
        d = out / task_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "BLUEPRINT.md").write_text(
            gen_blueprint(task_id, entity, entity_cn, fields, cmds, agg_name, agg_desc, seed),
            encoding="utf-8")
        meta = {
            "id": task_id, "pattern": "crud-cli", "seed": seed,
            "entity": entity, "fields": fields, "commands": list(cmds),
            "aggregate": agg_name, "held_out": held_out,
            "task_prompt": (f"根据 .arch/BLUEPRINT.md 的契约，实现 {entity_cn}管理 CLI："
                            f"在项目根创建 src/ 代码与 src/main.py 入口，"
                            f"使命令 python src/main.py {'/'.join(cmds)} 全部可用，"
                            f"并通过 validate_blueprint.py 的全部检查。"),
        }
        (d / "task.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        tasks.append((task_id, held_out))

    n_hold = sum(1 for _, h in tasks if h)
    print(f"已生成 {len(tasks)} 个任务 → {out}（held-out {n_hold} 个，训练时禁用）")
    for tid, h in tasks:
        print(f"  {'[HOLD]' if h else '[train]'} {tid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
