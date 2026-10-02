---
name: arch-first-dev
description: 架构优先的AI编程方法。先构建完整产品架构蓝图，再进行模块化实现，通过级联契约记忆系统(Cascading Contract Memory)确保全局逻辑无断裂、无幻觉。使用场景：(1) 预计跨越多个模块的编程任务（新项目、跨模块新功能、多模块修复或重构）。(2) 当用户说"先设计再写代码"、"架构不合理"、"代码太零散"、"逻辑有漏洞"或类似表述。(3) 当用户没有明确要求但任务复杂度明显需要全局设计时主动提议使用。(4) 改造/扩展现有项目时，先逆向重建架构契约再修改。(5) 祖传/屎山代码（无文档、腐化、不敢动）——先用屎山模式考古建账（影响面+腐点台账），再经安全网、防腐层与绞杀迁移逐步重构，不做局部盲改。
metadata:
  short-description: 先蓝图后代码，全局逻辑零断裂
---

# 架构优先开发

## 快速适用性判断（最先读这节；不适用就到此为止）

触发后先回答 3 个问题，任何一个为"是"才继续使用本 skill，否则直接完成任务、
不要画蓝图、不要读 references（eval 实测：简单任务通读全文的开销是直接完成的 ~5.4×）：

```
1. 任务会触碰 ≥ 2 个模块，或要新建多模块项目吗？
2. 用户关心跨模块一致性 / 接口约定 / 架构梳理吗（或说了"先设计再写代码"）？
3. 这不是纯原型速通（"先跑通就行，不用管质量"）吗？
```

不适用示例：单文件脚本、改配置、修单点 bug、加注释、格式化、数据小加工、快速原型。
适用但想控制成本：修复/重构用 G2（局部逆向），接口设计 / Review 用 G1。

## 核心：蓝图填充模型

先画完整蓝图（BLUEPRINT.md），再从底层向上逐格填充。蓝图是三个角色的合一：全局导航、空位标记、进度追踪。快速上手见 README.md；速查见 references/quick-reference.md。

## 分层加载

### L1 核心（本文件，~300 行）
快速适用性判断 / 路由 / 7 约束 / 3 层幻觉防护 / 启动指令 / 三档模式 / Phase 1-3 / 迭代模式。
（v3.0 减法：细则是 references 的事，本文件只留主流程。）

### L2 条件加载

| 触发条件 | 加载内容 |
|---------|---------|
| 平台工具与映射表不符，或工具调用失败 | [平台适配](references/platform-adaptation.md) |
| 需要模型适配参数 / 本地小模型档 | [模型适配](references/model-adaptation.md) |
| 需求模糊 / 目录结构 / 产出物清单 | [项目搭建](references/project-setup.md) |

### L3 按需加载路由器

> 本表只回答一个问题：当前阶段出现什么条件时，Read 哪个 reference。
> 条件未命中就不读——这是上下文节省的全部来源。

```
Phase 1（画蓝图）:
  用户说"用模式设计" → references/patterns.md
  腐化/超大存量项目 → references/legacy-mode.md（屎山模式）
  Phase 1 完成后 → references/verification.md §健康度自诊（可选）
Phase 2（逐格填充）:
  上下文纪律 / 压力信号 / 逐行对照 / 模块 [done] 后动作
    → references/context-discipline.md
  下游无法对接 → references/verification.md §契约修复优先序（Rollback 已移 attic）
Phase 3（连通验证）:
  完成后 → references/verification.md §验收清单 / §漂移检测 / §失败恢复
迭代模式:
  读取蓝图时 → references/verification.md §漂移检测
  影响面/腐点 → references/legacy-mode.md
跨 Phase:
  契约测试进阶 → references/verification.md；蓝图修正协议 / 逆向 8 步 / git 协作 /
  @EXTERNAL 完整格式 → references/blueprint-ops.md
  需求澄清 / 产出物清单 → references/project-setup.md
  快速查阅 → references/quick-reference.md；特性冲突 → references/priority-table.md
  未验证特性（多会话/Rollback/大型分解/专长分工）→ references/attic.md（主路径不引用）
```

### L0 本地小模型模式（7B-14B 量化模型，有效上下文 ≤32K）

本地小模型不要读本文件其余部分——流程知识已全部搬进脚本：

```
python scripts/work.py next  <BLUEPRINT.md>   # 输出下一个最小工作包（含所需全部上下文+内联规则）
python scripts/work.py check <BLUEPRINT.md>   # 全链验证并输出下一步
python scripts/scaffold.py  <BLUEPRINT.md> --out src   # 骨架生成（签名锁定）
```

模型只做三件事：读工作包 → 填 TODO 函数体 → 运行 check 并遵循其输出。
行为守则（11 条）：references/edge-guide.md。强模型不适用本模式（工作包会人为限制视野）。

读取纪律：条件未命中就不读；同一轮最多读 1 个 reference；用户显式点名的特性优先；
已读过的文件本会话内不重读；不要在回复中复述蓝图/契约原文——工具输出即记录；
文件读入后没有"释放"——腾上下文用 /compact 或 CHECKPOINT + 新会话。

## 约束系统（7 条硬规则，不可绕过）

| # | 约束 | 一句话 |
|---|------|--------|
| 1 | 用户确认门 | 蓝图未确认不进 Phase 2（微项目档例外：展示要点后知会即续） |
| 2 | 一次一格 | 同时只能一个 [in progress]（例外：同层可并行；微项目/简化档同层 ≤3 可批量填充） |
| 3 | 依赖先填 | 上层模块等下层 [done] 后才能开始 |
| 4 | 变更有痕 | 改蓝图必须有 @CHANGE |
| 5 | 模块边界 | 不直接访问其他模块的内部文件 |
| 6 | 接口有消费者 | 每个接口必须在 @FLOW 中出现 |
| 7 | 一次读取 | 依赖模块只读接口签名，不读实现源码 |

违规处理：停止 → 回退 → 纠正 → 记录 @CHANGE → 恢复。
约束 3/5/6 的结构部分由 scripts/validate_blueprint.py 确定性检查；1/2/4/7 是行为纪律。

## 逻辑幻觉防护（3 层）

**第 1 层 — BEHAVIOR 声明**：每个接口四段 `pre / post / error / side-effect`。
简化格式：纯函数只写 post；UI 组件写 post + side-effect；配置声明只写 post。
两条精确化要求（eval 实测缺陷）：写文件的接口必须声明父目录不存在时的行为；
数值格式化必须指明舍入模式（"四舍五入"不可测——Python round 是银行家舍入）。

**第 2 层 — 边界矩阵**：每模块检查 6 维度——空输入 / 不存在引用 / 边界值 /
重复操作 / 类型越界 / 依赖故障，每项 ✓ 或 —，不允许空 ❌。

**第 3 层 — 错误链映射**：跨模块错误传播路径显式列出（源头 → 传播 → 终点）；
异步流支持补偿事件分支。

三个防护任一不完整 → 不进入 Phase 3。

## 能力补偿（为弱模型设计）

1. **判断变程序**：能脚本化的检查不交给模型——--gate / --verify / --check-signatures 是权威
2. **自由度变模板**：Phase 2 前先 scaffold 生成骨架（签名锁定 + 契约原文进 docstring），只填 TODO
3. **验证变事实**：每条 @FLOW 写 @VERIFY 命令，Phase 3 ⑦ 用 --verify 执行
弱模型默认档：全量对照 + 微批量 + 每阶段过门禁 + 骨架先行 + 蓝图过 --lint 消歧
（强模型能脑补的惯例——排序方向、大小写、边界含否、求和互斥——小模型会各自发明实现）；
降档须用户明示"模型很强"。

## 启动指令

```
第 0 步：判断
  ├── 新项目 → Phase 1
  ├── 现有项目 → 逆向蓝图 → Phase 2
  ├── 祖传/腐化项目（屎山）→ references/legacy-mode.md 五步协议
  └── 简单任务（3 文件以内、单模块）→ 不要触发本 skill

第 0.1 步：需求模糊时先问 3-5 个关键问题（清单见 references/project-setup.md）；
          需求清晰（有明确功能清单/输入输出）就跳过提问，不要为了问而问
第 0.2 步：粒度——G1 行为契约（设计接口/Review）| G2 约束驱动（重构/修不一致，
          可局部逆向）| G3 完整流程（新项目/大重构）。
          按当下可判断的任务形态选，拿不准 → G3；G3 画完发现只有 1-2 个模块
          可与用户确认后收缩为 G2。过渡只补缺失部分，不重做已有产出。
          预估接口数 ≤ 8 → 直接按微项目档画蓝图（段落可省，见 0.5），不画完再降档
第 0.3/0.4 步：目录结构与产出物清单 → references/project-setup.md
第 0.5 步：规模模式（Phase 1 完成后由 validate_blueprint.py 按接口数自动判定）：
    ≤ 8  接口 → 微项目档：确认门降级为知会门（展示要点后直接进 Phase 2）；
              同层全部批量填充；测试仅跨模块接口；CHECKPOINT 仅 Phase 切换；
              蓝图未改不重跑 validator；@CROSSCUT 一行版、@ERROR_CHAIN 无复杂
              跨模块传播时可省（validator 只强制 @MODULE/@FLOW/@BUILD_ORDER）
    9-15 接口 → 简化模式：边界矩阵可省、@ERROR_CHAIN 1-2 条、每接口 happy-path、
              Phase 3 验证 ①⑤⑥⑦+⑨（⑧ 照常）；确认门阻塞
    > 15 接口 → 完整模式：全量仪式，Phase 3 验证 ①-⑨
    轮次预算（advisory，超 1.5× 时先省仪式——合并对照/省回顾；门禁与 --verify 永不省）：
    微项目 ~12 轮 | 简化 ~20 轮

第 0.6 步：工程化检查点（validate_blueprint.py = 机械检查器，三个介入点）
    a. Phase 1 预检后：脚本执行预检 ②③⑥⑦，模型只做 ①④⑤ 语义合理性
    b. Phase 3 前：全量复检 + --signatures 生成漂移基准
    c. CI / 迭代：蓝图修改后运行，退出码非 0 即失败
  命令（.arch/BLUEPRINT.md 按实际路径替换）：
    python scripts/validate_blueprint.py <BP>                    # 检查
    python scripts/validate_blueprint.py <BP> --gate phase2      # 阶段门禁（phase1/2/3）
    python scripts/validate_blueprint.py <BP> --verify           # 执行 @VERIFY 机器验证
    python scripts/validate_blueprint.py <BP> --signatures       # 生成签名快照（含契约文件 sha256）
    python scripts/validate_blueprint.py <BP> --check-signatures # CI 门禁：蓝图漂移则退出码 1
    python scripts/validate_blueprint.py <BP> --check-code       # CI 门禁：代码手改未同步蓝图则退出码 1
    python scripts/validate_blueprint.py <BP> --lint             # 歧义 lint：标记弱模型无法猜惯例的措辞
    python scripts/scaffold.py <BP> --out src                    # 骨架生成（签名锁定）
    python scripts/work.py next|check <BP>                       # 本地小模型编排器（L0）
    python scripts/archaeology.py <项目根> [--impact <符号>]     # 考古：依赖图/fan-in/循环；--impact 出影响面四问①②③
  CI 模板：templates/ci-blueprint.yml。
  自治模式（无交互用户）：确认门不阻塞——展示蓝图要点、默认选择记 @CHANGE 后继续。
  用户说"速通/自治/别等我"时同样适用（门禁与 --verify 照跑，只免阻塞等待）。
```

## Phase 1：画蓝图

七步分解：

```
① 实体抽取 → @DATA
② 行为识别 → @FLOW
③ 模块划分 → @MODULE
④ 依赖标注 → 写清"依赖 B → getX()"（含调用路径），不只写"依赖 B"
⑤ 构建排序 → @BUILD_ORDER（层号 = max(直接依赖层号)+1；无依赖为第 1 层）
⑥ 覆盖率检查 → 每个功能点→@FLOW→@MODULE 接口的链完整
⑦ 用户确认 → 展示蓝图，等待确认
```

> ⚡ 一次成稿：需求清晰时 ①-⑥ 单轮直接产出完整蓝图全文，随后一并展示确认/知会；
> 不要分步提问、逐段征求确认。只有需求模糊才回第 0.1 步。

Phase 1→2 预检（②③⑥⑦ 交给 validate_blueprint.py，模型做 ①④⑤ 并复核脚本输出）：
① @MODULE 字段齐全 ② 无逆依赖 ③ 无幽灵依赖 ④ @FLOW 模块/接口可解析
⑤ @FLOW 引用的实体在 @DATA 中 ⑥ 无循环依赖 ⑦ 接口名全局唯一。
失败恢复：脚本报什么修什么；⑥ 循环依赖 → 合并模块或抽公共模块。

**BLUEPRINT.md 结构**：

```
@META（version、scope: partial?；主版本=修正协议触发，次版本=模块/签名/FLOW 变更）
@PROGRESS（进度条）
@MODULE（职责、接口、依赖、状态 [empty|in progress|done|deferred|wontfix|removed]）
@FLOW（同步格式: 步骤: 用户 → a.f() → b.g() → 终端 + 涉及: 模块列表；
      异步格式加 事件: 与 补偿: 行）
@DATA（字段名和类型；字段变更必须在 @CHANGE 关联 migration）
@BUILD_ORDER（按层）
@CROSSCUT（错误处理、日志、配置等跨切面）
@EXTERNAL（外部依赖契约。支持「契约文件: openapi.yaml / *.proto / schema.sql」引用——
  蓝图只存引用+行为摘要，冲突以引用文件为准；validator 校验存在性、sha256 入快照。
  规则：声明可用模块（默认全部可用不安全）；故障模式必写；
  有状态依赖（数据库/API/队列）必填四槽位：幂等性/重试/超时/事务边界）
@ERROR_CHAIN（源头 → 传播 → 终点）
@VERIFY（每条 @FLOW 的机器验证: run + expect-exit/expect-contains/expect-not-contains）
@DEBT（腐点台账，格式见 references/legacy-mode.md）
@CHANGE（变更日志）
```

## Phase 2：逐格填充

> ⚡ 批量填充：微项目/简化档且同层 [empty] ≤ 3 → 连续填充后统一对照与标记。

对每个 [empty] 模块：

```
1. 定位 → 确认依赖全 [done]
2. 加载 → 当前模块条目 + 依赖模块接口签名 + @CROSSCUT（不读依赖源码）
3. 实现 → 按蓝图签名写，落实四段声明；docstring 引用蓝图而非重复录入
3.5 对照 → 微项目档：跨模块全量+内部抽查；简化档全量；完整档风险导向
   （详见 references/context-discipline.md §逐行对照）
4. 标记 → [done]；同层全 done 后批量更新 @PROGRESS
5. 确认 → 蓝图未破坏依赖
6. 收尾 → 压力信号按 references/context-discipline.md §上下文压力感知 的判断逻辑行动
```

填充异常 6 种：模块太大 → 拆分重排记 @CHANGE；缺接口 → 加接口并级联回退下游；
多接口 → 查 @FLOW 后删；依赖不存在 → 移除；接口不匹配 → 确认谁错改谁；
蓝图设计问题 → 蓝图修正协议（references/blueprint-ops.md，回 Phase 1）。

## Phase 3：连通验证

```
① 流验证：每条 @FLOW 的模块和接口存在且 [done]
② 依赖检查：签名匹配 + 调用路径一致（机械部分脚本覆盖）
③ 边界检查：边界矩阵全 ✓ 或 —
④ 错误链检查：源头→传播→终点完整
⑤ 空位检查：无 [empty] 残留
⑥ 变更回溯：逐条 @CHANGE 已整合
⑦ 运行时验证（不可跳过；项目质量门优先）：
   先跑项目自己的 pytest/jest/tsc/lint——红了修本次改动范围的问题，
   既有失败如实记 @CHANGE，不静默跳过；项目门验证"单元"，@FLOW 验证"流"。
   再对每条 @FLOW 主路径执行一次：无 ImportError、无未捕获异常。
   有 @VERIFY → 直接 python scripts/validate_blueprint.py <BP> --verify。
   UI 项目：dev server 编译无报错 + 页面可渲染 + 关键交互一条；
   无浏览器工具降级为 HTTP 200 + 关键路由非 5xx。
   屎山项目无质量门 → 特征测试（legacy-mode.md 第 2 步）就是第一道门。
⑧ 生成 .arch/SUMMARY.md：一句话概述 + 依赖图 + Top @FLOW + @DECISION + @EXTERNAL 故障模式
⑨ 回顾：@CHANGE 分布 / 修正次数 / 关键发现 / 改进建议（3-5 句，追加到 SUMMARY）
```

完整档 ①-⑨；简化档 ①⑤⑥⑦+⑨（⑧ 照常）；微项目档 ①⑤⑥⑦ + ⑧ 一句话版，⑨ 可省。
失败恢复细则见 references/verification.md；原则：①②⑤ 必须修复重验，其余定点重验。

## 增量开发 / 迭代模式

```
1. 读蓝图 → 漂移检测（基准 SIGNATURES.json，--signatures 生成）
   🟡/🔴 有漂移 → 先修复蓝图与代码差异
1.5 影响面四问（跨模块改动前强制；完整版见 legacy-mode.md）：
   ① 谁依赖我要改的符号（fan-in，scripts/archaeology.py --impact 验证）② 我依赖谁（fan-out）
   ③ 波及面有无无测试区（有 → 先补特征测试）④ 本次偿还/新增 @DEBT 哪一笔
   答不出 ① → 先考古（scripts/archaeology.py）。屎山项目必须走完整四问。
2. 影响评估：单模块内部修改 → 直接改；接口签名/模块/FLOW 变更 → 蓝图级，继续
3-5. 标记 [in progress] / [empty] → 更新 @BUILD_ORDER 和 @FLOW
6. 对修改和新增模块执行 Phase 2 填充
7. Phase 3 验证（范围：直接受影响 + 下游 @FLOW；无关 @FLOW 跳过）
```

契约修复三要件（跨模块数据/行为不一致时，详见 references/verification.md）：
属主边界收口 + 消费方零改动或说明 + @DECISION 点名被否决方案——三者齐备才算对齐。

局部逆向（G2/修 bug 控成本）：只对本次变更涉及的 @FLOW 上的模块逆向，
@META 标 scope: partial；越界再扩展。git 协作约定见 references/blueprint-ops.md。

没有蓝图的现有项目：逆向蓝图 8 步流程见 references/blueprint-ops.md，核心思路
列出源文件 → 识别模块 → 提取签名 → 推断依赖 → @DATA → @FLOW → 标注状态 → 整理。
完成后进入迭代模式，并非从 Phase 1 重新开始。
