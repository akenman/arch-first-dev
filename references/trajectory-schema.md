# 轨迹事件格式标准（trajectory schema, v1）

> 用途：work.py `--trace` 采集的编排器轨迹，是 RLVR 训练帧与过程蒸馏的数据底座。
> 本文件是数据契约——采集端（work.py）与消费端（训练/分析流水线）共同遵守。

## 事件模型

每行一条 JSON 事件（JSONL），按时间序追加。字段：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| ts | ISO-8601 UTC | ✓ | 事件时间 |
| event | enum | ✓ | `next` \| `check` \| `verify` |
| blueprint | str | ✓ | 蓝图绝对路径（任务标识） |
| package_chars | int | next | 工作包字符数（上下文成本度量） |
| open_modules | str[] | next/check | 未完成模块（进度状态） |
| errors | int | check | 蓝图错误数 |
| exit | int | verify | verify 阶段退出码（0=全过） |

## 完整轨迹 = 编排器事件 + 外层 harness 事件

work.py 只看得到"状态与奖励"（观测：工作包 / 奖励：check 红绿）。
**动作**（模型实际写了什么文件）由外层 harness（ZCode / Claude Code / 自研 loop）
的 transcript 捕获，通过 `blueprint` + `ts` 区间对齐。两者合并后才是一条完整
RL 轨迹：`state（工作包） → action（文件编辑 diff） → reward（check 红绿）`。

## SFT/RL 消费约定

- 训练帧切分：一次 `next → (edits) → check` 为一帧；check 退出码 0/1 为奖励
- 弱模型+强脚手架轨迹用于过程蒸馏；强模型自由轨迹用于对比基线
- `package_chars` 是"信息自足性"指标：在达到同等通过率的前提下越小越好
- held_out 任务（task.json 标记）的轨迹禁止进入训练集

## 已知限制

- 不含模型侧 token 用量（外层 harness 才有 usage；token_profile.py 做估算近似）
- 文件编辑 diff 依赖 harness 导出，格式由各家自定（对齐键：路径 + 时间戳）
