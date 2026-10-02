# 跨家族评测矩阵协议（anti-self-eval）

> 动机：v1-v4 轮 eval 全部由 GLM 家族自执行、自评分（n=1/格），存在系统性
> 自评偏差。要出可对外主张的结论（如"Flash+skill ≈ Air 级多文件表现"），
> 必须跨模型家族、多格重复执行本协议。

## 实验矩阵

| 格 | 执行模型 | skill | 目的 |
|----|---------|-------|------|
| A | 目标档弱模型（Qwen2.5-Coder-7B / GLM-4-Flash 档） | ✅ v3.x | 核心主张：skill 补偿能力 |
| B | 同弱模型 | ❌ | 下界 |
| C | 强模型（GLM-5.3 / Claude 级） | ❌ | 上界参照 |
| D | 强模型 | ✅ | 脚手架对强模型的增量（过程产物） |

结论判据：A 的功能正确率（reward.py score）≈ C，且 ≫ B → 能力补偿成立。
跨家族重复：至少两家弱模型（Qwen + DeepSeek/Llama 各一），每格 n≥3 取方差。

## 防污染

- 任务用 `gen_tasks.py --seed <新种子> --held-out-ratio 1.0` 现场生成，禁止使用
  对话中暴露过的 fixture（task-cli / url-shortener / legacy-oms / 已生成 env/tasks）
- 评分只用确定性奖励（reward.py），不用同模型当 judge；如需语义评分，
  judge 模型与执行模型必须异家族
- 执行 agent 的系统提示不得包含任务蓝图以外的契约信息

## 运行步骤（每格）

1. `python scripts/gen_tasks.py --n 12 --seed <S> --out runs/<cell>/tasks --held-out-ratio 1.0`
2. 对每个任务：将执行模型接入外层 harness（OpenAI 兼容 API），
   系统提示 = SKILL.md（A/D 格）或空（B/C 格），运行 task.json 的 task_prompt
3. 解答落盘后：`python scripts/reward.py <task> <solution> --json` 收集分数
4. 汇总：每格 mean±std（pass_rate、L1-L4 分项、tokens、时长）

## 指标

- 主指标：L3 行为分（行为层最难 hack）、总分
- 辅助：L4 覆盖率（agent 是否偷懒删验证）、token 成本、时长
- 过程产物统计：@DEBT 数、@CHANGE 数、特征测试存在性（D 格专项）

## 已知限制

- A 格执行弱模型需要函数调用能力；若弱模型工具调用不稳，改用 L0 模式
  （work.py 驱动 + edge-guide），此时 A 格同时检验工作包信息自足性
- reward.py 的 @VERIFY 是退出码/子串级——对外主张限于"契约机器验证通过"，
  不等价于"人类认可的代码质量"；语义质量需人工抽样 20%
