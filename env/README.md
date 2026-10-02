# arch-first-dev RLVR 环境

多文件、契约驱动、零参考答案、全确定性奖励的强化学习任务环境。
模型公司可直接将其接入 RLVR/评测流水线；分层奖励设计使 reward-hacking 有纵深防御。

## 任务生成

```bash
python scripts/gen_tasks.py --n 60 --seed 42 --out env/tasks
# env/tasks/<task-id>/
#   BLUEPRINT.md   任务契约（含 @VERIFY 机器验证命令）
#   task.json      参数元数据 + held_out 标记 + task_prompt
```

held_out=true 的任务只用于评测，禁止进入任何训练集（防污染）。
新任务形态：在 gen_tasks.py 中新增 pattern 函数（下一个建议：multi-crud 组合、event-driven）。

## 执行者接口

执行者（agent 或裸模型）拿到的只有 task.json 的 task_prompt 和任务蓝图。
产出约定：解答放在一个目录中，包含 .arch/BLUEPRINT.md（可复制任务蓝图后按契约实现）
与代码（默认 src/）。

## 分层奖励

```bash
python scripts/reward.py env/tasks/<id> <solution_dir> --json
```

| 层 | 权重 | 内容 | 防 hack 作用 |
|----|------|------|--------------|
| L1 结构 | 0.25 | 解答蓝图通过 validator（拓扑/约束/状态一致） | 结构完整性 |
| L2 一致 | 0.25 | --check-code：代码签名与解答蓝图基线一致 | 防接口幻觉 |
| L3 行为 | 0.40 | --verify：@VERIFY 机器命令通过率 | 行为层兜底（最难 hack） |
| L4 覆盖 | 0.10 | @VERIFY 对 @FLOW 的覆盖率 | 防删验证逃奖励 |

反 reward-hacking 纵深：agent 可以"迁就烂代码改蓝图"骗过 L1/L2，
但 L3 要求 @VERIFY 命令真实运行通过（行为层），L4 要求验证覆盖全部数据流——
改蓝图迁就代码的同时必须让机器验证仍然通过，等价于把代码写对。

## 已知边界

- 仅 Python 任务；--check-code 仅扫描 Python AST
- @VERIFY 为退出码/子串级验证（行为层），语义级奖励可叠加项目质量门
- 分数与人类"代码好不好"不必一致——它度量的是"契约被机器验证满足的程度"
