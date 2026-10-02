# arch-first-dev

**架构优先的 AI 编程方法论。先画蓝图，再逐模块实现。**

> **版本：v3.2.0** — 蓝图歧义 lint（P2）：
> `--lint` 标记弱模型无法猜惯例的措辞：模糊量词（"合理/适当/类似"）、求和桶未声明
> 互斥、排序未声明方向、匹配未声明大小写、时序/阈值未声明边界含否。
> advisory 不改退出码；规则刻意保守（正则已给字符类则不报大小写、已用不等号则不报边界）。
> 实测：task-cli 命中 4 处（含受限模拟痛的 getStats 互斥性与 listTasks 方向/大小写），
> url-shortener 零误报，精确构造蓝图零命中。
> v3.1.0 — 漂移检测闭环 + 骨架入口桩：
> ① `--check-code`：AST 扫描真实代码签名 vs SIGNATURES.json 基线，抓"手改代码未同步蓝图"
>    （与 --check-signatures 合起来把漂移的双向都堵死；实测抓到 test-project 一处真实不一致）；
> ② scaffold 从 @VERIFY 命令反推生成入口桩（main.py 等），并为未覆盖的 @FLOW 输出
>    @VERIFY 建议骨架——受限模拟暴露的两个工作包矛盾就此消除。
> v3.0.0 — 减法轮（slim）：
> 五轮 eval 证明价值在工具链后，文档层按同一标准审计：SKILL.md 734→269 行
> （触发成本 -63%），未验证特性移入 references/attic.md，三处内容重复收敛为单源，
> README 新增「特性 × 证据」矩阵——哪些被实证、哪些是设想，一目了然。
> v2.7.0 — 本地小模型模式（work 驱动编排）：
> 7B-14B 量化模型读不完也记不住任何流程文档——v2.7 把流程知识从模型上下文
> **搬进脚本**：`scripts/work.py next` 每轮输出一个 ≤8K 字符的最小工作包
> （模块蓝图条目 + 依赖签名 + 全局约定 + 待填 TODO 块 + 内联规则），
> `work.py check` 全链验证并给出下一步。模型只做三件事：读包 → 填函数体 →
> 听 check 输出。守则仅 11 条（references/edge-guide.md），
> 每条 @FLOW 的 @VERIFY 让验证不依赖模型能力。
> v2.6.0 — 能力补偿架构（让弱模型拥有强模型的结果）：
> ① **判断变程序**：`--gate phase1/2/3` 阶段门禁——进入下一阶段的机械前置条件，
>    红了就给出明确的缺失清单，不依赖模型自觉；
> ② **验证变事实**：蓝图新增 `@VERIFY` 段（每条 @FLOW 的 run/expect 命令），
>    `--verify` 执行机器验证——Phase 3 ⑦ 从"模型看一眼"变成脚本红绿；
> ③ **自由度变模板**：`scripts/scaffold.py` 骨架生成器——蓝图→锁定签名 + dataclass +
>    契约测试桩（契约原文进 docstring，py_compile 自检），弱模型只填 TODO，
>    接口签名幻觉机制上不可能；
> ④ 弱模型默认档：全量对照 + 每阶段门禁 + 骨架先行，自评不可信、降档须用户明示。
> v2.5.0 — 有状态契约 + 框架感知考古 + git 轻量协作：
> ① @EXTERNAL 有状态依赖（数据库/API/队列）必填四槽位：幂等性/重试/超时/事务边界
>    （validator 缺槽位告警；示例蓝图已补齐）；
> ② 屎山考古新增框架惯例识别表（Django/FastAPI/NestJS/Spring/Go/Rails/前端）——
>    有框架就用框架的模块边界，不要自己发明；
> ③ @DATA 字段变更必须关联 migration；@ERROR_CHAIN 支持异步补偿事件；
> ④ git 轻量协作：蓝图 commit 引用 @CHANGE 编号、PR 描述由 @CHANGE/@DECISION 生成、
>    合并前跑 --check-signatures 门禁。
> v2.4.0 — 真实工程化（屎山模式 + 单一真相源 + 质量门接入）：
> ① **屎山模式**（references/legacy-mode.md）：五步协议（考古→安全网→选缝→绞杀迁移→
>    收尾展望）+ 规模护栏（>50 文件禁全读）+ 影响面四问（改动前强制，防局部盲改）+
>    @DEBT 腐点台账（债可见、可追踪、受控偿还——"放眼未来"的落点）；
> ② **外部契约单一真相源**：@EXTERNAL 支持引用 openapi/proto/schema 等契约文件，
>    蓝图只存引用+摘要，冲突以引用文件为准；validator 校验存在性、sha256 入签名快照；
> ③ **仓库级蓝图守卫**：新增 `--check-signatures` CI 门禁（代码接口变更未同步蓝图即
>    拦下）+ templates/ci-blueprint.yml 模板；Phase 3 ⑦ 优先跑项目自己的质量门；
> ④ 安全运维基线入验收清单（secrets/PII/幂等/migration）；多会话 LOCKS.md 建议
>    用 git 分支替代。
> v2.3.0 — 速度分档 + eval 第二轮教训：
> ① 新增「微项目档」（≤8 接口）：知会门代替阻塞确认、同层 ≤3 批量填充、测试仅跨模块
>    接口、CHECKPOINT 仅 Phase 切换、validator 蓝图未改不重跑（实测目标：把 3 模块小工具
>    的 with-skill 开销从 ~21 分钟压到与直接实现同量级）；
> ② 契约修复升级为「三要件」判据（属主边界收口 + 消费方零改动 + @DECISION 点名被否决
>    方案）——eval 第二轮发现正确的修复若不留痕，无法与运气区分；
> ③ eval 第二轮成本验证：局部逆向使 eval-1 型任务 tokens -44% / 时间 -47%；早退机制使
>    单文件任务开销与基线持平（144.6s vs 155.0s）。
> v2.2.0 — eval 驱动优化（第一轮 A/B eval，4 用例 7 runs）：
> ① 顶部「快速适用性判断」——简单任务读 ~15 行即退出（实测简单任务通读全文开销 ~5.4×）；
> ② 迭代模式新增「契约修复优先序」——跨模块不一致默认在数据属主边界收口，
>    而非消费方就地打补丁（实测中唯一的质量区分点：就地修补能骗过全部功能验证，
>    但混格式数据继续落盘）；
> ③ G2/修 bug 场景允许「局部逆向蓝图」（实测全项目逆向耗 ~1.6M tokens）；
> ④ BEHAVIOR 声明两处精确化——写文件接口必须声明父目录行为、数值格式化必须
>    指明舍入模式（两者均为 eval 中 Phase 3 实际抓到的缺陷类型）。
> v2.1.0：工程化加固（蓝图静态检查器、spec 矛盾修复、不可实现机制移除）。
> v2.0.0：按需加载路由器、6 大创新特性（漂移检测/专长分工/模式库/属性测试/骨架生成/知识图谱）

---

用 AI 写代码有个很常见的坑：代码能跑，逻辑是断的。

比如你让 AI 做一个记账工具。它生成了四个模块——数据存储、账目管理、统计分析、命令行界面——每个看起来都没问题，跑起来也不报错。但统计模块调用的函数返回值结构和账目模块实际返回的不一样，数据流在某一步悄悄断了。不报错，只是结果不对。

这类问题靠"跟 AI 说仔细一点"解决不了。因为上下文一长，AI 自己也会忘。

这份 skill 的思路是：**别让 AI 一上来就写代码。先让它把架构画清楚。**

## 怎么做的

整个过程分三个阶段：

**Phase 1 — 画蓝图。** AI 把所有模块、接口、数据流、依赖关系写进一份 `BLUEPRINT.md`。这不是设计文档，是**可验证的契约**——每个接口必须写明：

- `pre` — 调用前什么条件必须成立
- `post` — 返回后什么条件一定成立
- `error` — 什么情况下抛什么错
- `side-effect` — 这个函数改变了什么状态

**Phase 2 — 逐模块实现。** 按依赖顺序从底层往上填。底层模块没做完，上层不开始。每个模块实现完后，把代码和契约逐行对照——不是问"你觉得对吗"，而是"声明的每一项，代码里有对应行吗"。找不到就是漏了。

**Phase 3 — 验证。** 跑一遍所有数据流，确认没有 import 错误、没有未捕获的异常、接口签名对得上。

全部做完后，`BLUEPRINT.md` 留在项目里，就是你的项目架构文档。

## 一个例子

用这套方法从零构建了一个命令行任务管理器（Task CLI）。蓝图长这样：

```
@PROGRESS
  storage        ██████████ [done]
  tasks          ██████████ [done]
  stats          ██████████ [done]
  cli            ██████████ [done]

@MODULE storage      ← JSON 文件读写
@MODULE tasks         ← 增删改查 + 状态变更
@MODULE stats         ← 完成率统计 + 逾期检测
@MODULE cli           ← 命令行解析 + 格式化输出

9 条 @FLOW，15 个接口，每个都有完整的 pre/post/error/side-effect 声明
```

完整蓝图见 [examples/task-cli/BLUEPRINT.md](examples/task-cli/BLUEPRINT.md)。

## 不是什么项目都要走完整流程

分三层，灵活选用：

| 层级 | 什么时候用 | 产出 |
|------|-----------|------|
| G1 | 设计接口、review 代码 | 每个接口的 pre/post/error/side-effect |
| G2 | 重构、检查接口一致性 | G1 + 7 条约束检查 |
| G3 | 新项目、大型重构 | 完整蓝图 → 逐模块实现 → 验证 |

一个接口级别的 review 用 G1，五分钟的事，不需要画蓝图。

## 7 条硬约束

这些规则是用来防止 AI 在长上下文里自己把自己搞乱的：

1. 蓝图没确认就不写代码
2. 一次只做一个模块
3. 依赖的模块没做完，上层不开始
4. 改蓝图必须记录变更原因
5. 模块之间只通过接口通信，不直接访问内部文件
6. 每个接口必须在至少一条数据流中被使用
7. 依赖模块只读接口签名，不读实现源码

## 蓝图是可以机械校验的

skill 附带一个零依赖的静态检查器，把"模型自觉遵守"变成"脚本确定性地查"：

```bash
python scripts/validate_blueprint.py .arch/BLUEPRINT.md             # 结构/依赖/循环/消费者/状态一致性
python scripts/validate_blueprint.py .arch/BLUEPRINT.md --signatures # 同时生成签名快照（漂移检测基准）
python scripts/validate_blueprint.py --selftest                      # 检查器自测
```

检查覆盖 Phase 1 预检 ②③⑥⑦（构建顺序、幽灵依赖、循环依赖、接口唯一）、
约束 6（每个接口必须在 @FLOW 中出现）、@PROGRESS 与 @MODULE 状态一致性。
退出码非 0 即失败，可以直接接进 CI：

```yaml
# .github/workflows/blueprint.yml 片段
- run: python scripts/validate_blueprint.py .arch/BLUEPRINT.md
```

## 快速体验（3 分钟）

```
1. 想一个小需求（如"命令行待办事项"、"简单的记账工具"）
2. 说: "用 arch-first-dev G1 设计接口"
   → AI 输出每个接口的 pre/post/error/side-effect 行为声明
3. 说: "继续，G3 完整流程"
   → AI 画蓝图 → 校验 → 逐模块填充 → 运行验证 → 生成 SUMMARY.md
4. 看一眼 .arch/SUMMARY.md，30 行看懂整个项目架构
```

## 跨平台 & 跨模型

这套方法本身不绑定任何 AI 工具。skill 文件里有平台工具映射表（DeepSeek TUI、Claude Code、Trae、Cursor、Codex CLI）和模型适配参数（包括新模型自动分类逻辑），在不同环境下会自动调整执行策略。

## 特性 × 证据（v3.0 审计）

| 证据 | 特性 |
|------|------|
| ✅ eval 实证 | 蓝图/BEHAVIOR 契约、三阶段填充、validate_blueprint.py、三档模式、G2/G3、快速适用性判断、迭代模式、局部逆向、契约修复三要件、屎山五步协议、特征测试、scaffold、work.py、@VERIFY/--verify |
| 🔧 工具新增（本轮） | --lint（蓝图歧义 lint，弱模型项目必开） |
| ⚪ 设计存在，未验证 | 微项目档（未触发过）、G1、知识图谱（实验）、模式库（抽象模式）、蓝图修正协议、Rollback、并行填充/专长分工（attic）、差异测试/属性测试（attic 前身）、健康度语义评估、git 协作约定 |
| ⚰️ 废弃 | 多会话 LOCKS（git 替代）、上下文预算管理器（上下文纪律替代）、MoE 槽位（按需读取替代）、能力探针缓存项 |
| 🔧 工具（不占上下文） | validate_blueprint.py / scaffold.py / work.py / ci-blueprint.yml |

## 什么时候不适合

- 改个配置、修个单行 bug、换个颜色——不需要架构设计
- 已经有一个很好的架构文档，只是加个小功能——没必要重新画蓝图
- 原型阶段，想快速试一下可行性——先跑起来再说

## 安装

```bash
# DeepSeek TUI
cp -r arch-first-dev ~/.deepseek/skills/

# Claude Code
cp -r arch-first-dev ~/.claude/skills/

# Trae CN
cp -r arch-first-dev ~/.trae-cn/skills/   # 项目级：放在项目根目录 .trae-cn/skills/

# Cursor
cp -r arch-first-dev .cursor/skills/       # 项目级：放在项目根目录 .cursor/skills/

# Codex CLI
cp -r arch-first-dev ~/.codex/skills/
```

然后在 AI 编程工具里输入：

> 用 arch-first-dev 帮我做一个 ________

## 速度设计（体感时间从哪省出来）

- **分层加载，未命中不读**：主文件约 280 行；references 按触发条件读取（eval 实测：
  简单任务通读全文的上下文开销是直接完成的 ~5.4×）。references 按阶段拆分为聚焦文件，
  每次触发只加载 80-150 行而非一个大杂烩。
- **微项目速通（≤8 接口）**：确认门降级为知会门、同层全部批量填充、SUMMARY 一句话版、
  回顾可省、蓝图段落可省——目标 ~12 轮工具调用内完成（advisory）。
- **一次成稿 + 速通开关**：需求清晰时蓝图单轮产出、不分步提问；说"速通/自治/别等我"
  可跳过所有阻塞确认（门禁与 --verify 照跑，只免等待）。
- **机械门禁替代反复人工检查**：validate_blueprint.py 的 --gate/--verify/--check-signatures
  秒级出结果，模型不做主观复检；省的是仪式，不是验证。

## 目录

```
arch-first-dev/
├── SKILL.md                      # 核心流程
├── README.md
├── LICENSE
├── scripts/
│   ├── validate_blueprint.py     # 蓝图静态检查器（拓扑/约束6/状态/契约文件/--gate/--verify/--check-signatures）
│   ├── scaffold.py               # 骨架生成器（蓝图→锁定签名/dataclass/测试桩/入口桩/@VERIFY 建议）
│   ├── work.py                   # 本地小模型编排器（最小工作包 next / 全链验证 check）
│   ├── archaeology.py            # 考古辅助器（依赖图/fan-in 榜/循环依赖/影响面四问①②③）
│   ├── gen_tasks.py              # RLVR 任务生成器（crud-cli 参数化，held-out 防污染）
│   ├── reward.py                 # 分层确定性奖励（结构/一致/行为/覆盖）
│   ├── fuzz_parser.py            # 解析器模糊测试（防 reward-hacking 面）
│   ├── lint_model.py             # 可插拔小模型语义 linter（OpenAI 兼容端点）
│   └── token_profile.py          # 轨迹 token 经济学剖析
├── templates/
│   └── ci-blueprint.yml          # 蓝图守卫 CI 模板（结构门+签名门+契约门）
├── examples/
│   └── task-cli/
│       ├── BLUEPRINT.md          # 完整蓝图示例（已通过机械校验）
│       ├── SIGNATURES.json       # 签名快照示例
│       └── README.md             # 运行说明（@VERIFY 需先 scaffold + 填充）
├── test-project/
│   └── url-shortener/            # 真实跑通的样例项目（蓝图/摘要/签名齐备）
└── references/
    ├── legacy-mode.md               # 屎山模式（考古/安全网/防腐层/绞杀迁移/@DEBT 台账）
    ├── edge-guide.md                # 本地小模型 11 条守则（L0 模式）
    ├── project-setup.md             # 需求澄清/目录结构/产出物清单（启动明细）
    ├── attic.md                     # 未验证特性存档（多会话/Rollback/大型分解/专长分工）
    ├── platform-adaptation.md       # 各平台工具映射
    ├── model-adaptation.md          # 模型适配 + 新模型自分类
    ├── context-discipline.md        # Phase 2 填充纪律（上下文/逐行对照/检查点/测试策略）
    ├── verification.md              # 验证与修复（验收清单/健康度/漂移检测/契约修复）
    ├── blueprint-ops.md             # 蓝图运维（逆向 8 步/@EXTERNAL 格式/git 协作/修正协议）
    ├── patterns.md                  # 蓝图模式库（CRUD/认证/事件驱动/防腐层/绞杀者）
    ├── blueprint-compiler.md        # 骨架生成约定（蓝图→代码骨架）
    ├── knowledge-graph.md           # 蓝图知识图谱（实验性，默认关闭）
    ├── priority-table.md            # 特性优先序 + 冲突解决
    └── quick-reference.md           # 速查表（触发词/约束/Phase/信号）
```

## License

MIT