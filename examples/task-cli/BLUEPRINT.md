# 项目蓝图 — Task CLI 命令行任务管理器

@META
  version: 1.0
  skill: arch-first-dev
  created: 2026-05-17

@PROGRESS
  storage        ██████████ [done]
  tasks          ██████████ [done]
  stats          ██████████ [done]
  cli            ██████████ [done]
  ──────────────────────────────
  总计: 4/4 模块完成 (100%)

---

## 模块地图

@MODULE storage
  职责: JSON 文件的读写，任务数据的持久化层
  接口:
    loadTasks() → Task[]
      pre: 无
      post: 返回数组不为 null；文件不存在时返回空数组
      error: 文件损坏（JSON 解析失败）时返回空数组（降级，不抛异常）
      side-effect: 无
    saveTasks(tasks: Task[]) → void
      pre: tasks 不为 null
      post: 数据写入磁盘；写入失败时静默（下次 loadTasks 读到旧数据或空）
      error: 无（降级策略）
      side-effect: 覆盖写入 tasks.json
  状态: [done]

@MODULE tasks
  职责: 任务实体的增删改查和状态变更
  接口:
    addTask(title, description, priority, dueDate, tags) → Task
      pre: title 非空，priority ∈ {high, medium, low}（默认 medium）
      post: 返回的 Task.id 自增唯一，status = todo，createdAt = 当前时间
      error: title 为空时抛 ValueError
      side-effect: 存储中追加一条任务
    listTasks(filter: TaskFilter | null) → Task[]
      pre: filter 可空
      post: 返回数组不为 null；可按 status/priority/tags/keyword/dueDate 筛选排序
      error: 无
      side-effect: 无
    getTask(id) → Task | null
      pre: id > 0
      post: 返回匹配的任务或 null
      error: id ≤ 0 时抛 ValueError
      side-effect: 无
    updateTask(id, fields) → Task | null
      pre: id > 0，fields 至少包含一个可更新字段（title/description/priority/dueDate/tags）
      post: 返回更新后的 Task；id 不存在时返回 null
      error: id ≤ 0 或 fields 全空时抛 ValueError
      side-effect: 存储中更新该任务（如存在）
    deleteTask(id) → void
      pre: id > 0
      post: 若 id 存在则删除；不存在则静默（幂等）
      error: id ≤ 0 时抛 ValueError
      side-effect: 存储中移除该任务（如存在）
    markDone(id) → Task | null
      pre: id > 0
      post: 返回 status=done 且 completedAt=当前时间的 Task；id 不存在时返回 null
      error: id ≤ 0 时抛 ValueError
      side-effect: 存储中更新状态和完成时间
    markInProgress(id) → Task | null
      pre: id > 0
      post: 返回 status=in_progress 的 Task；id 不存在时返回 null
      error: id ≤ 0 时抛 ValueError
      side-effect: 存储中更新状态
  依赖: storage → loadTasks(), saveTasks()
  状态: [done]

@MODULE stats
  职责: 任务完成率统计和逾期检测
  接口:
    getStats(filter: TaskFilter | null) → Stats
      pre: filter 可空
      post: total = todo + inProgress + done + overdue（overdue 为 dueDate < 今天且未完成的计数）
      error: 无
      side-effect: 无
    getOverdue() → Task[]
      pre: 无
      post: 返回所有 dueDate < 今天且 status ≠ done 的 Task 数组
      error: 无
      side-effect: 无
  依赖: tasks → listTasks()
  状态: [done]

@MODULE cli
  职责: 命令行参数解析、命令路由和终端格式化输出
  接口:
    parseArgs(argv: string[]) → Command
      pre: argv 非空
      post: 返回结构化的 Command 对象；无法识别时 action = "help"
      error: 无（容错降级为 help）
      side-effect: 无
    formatTask(task: Task) → string
      pre: task 不为 null
      post: 返回单任务的彩色格式化字符串（含优先级图标、截止日期高亮）
      error: 无
      side-effect: 无
    formatTaskList(tasks: Task[]) → string
      pre: tasks 不为 null
      post: 返回表格形式的任务列表（编号/状态/优先级/标题/截止日期）
      error: 无
      side-effect: 无
    formatStats(stats: Stats) → string
      pre: stats 不为 null
      post: 返回统计面板字符串（总数/各状态数量/完成率进度条/逾期数）
      error: 无
      side-effect: 无
  依赖: tasks → addTask(), listTasks(), getTask(), updateTask(), deleteTask(), markDone(), markInProgress()
        stats → getStats(), getOverdue()
  状态: [done]

---

## 边界矩阵

| 维度 | storage | tasks | stats | cli |
|------|---------|-------|-------|-----|
| 空输入 | ✓ (loadTasks 文件不存在返回[]) | ✓ (addTask title 空抛错; listTasks filter 空时全量) | ✓ (filter 空时全量统计) | ✓ (argv 空时 help) |
| 不存在引用 | ✓ (tasks.json 不存在时降级) | ✓ (getTask/updateTask 返回 null) | ✓ (无任务时全部返回 0) | ✓ (任务不存在时打印提示) |
| 边界值 | ✓ (空数组 saveTasks 正常) | ✓ (id ≤ 0; fields 全空; 空 tags) | ✓ (全部任务 done 时 overdue=0) | ✓ (空列表打印"暂无任务") |
| 重复操作 | ✓ (saveTasks 幂等覆盖) | ✓ (markDone 对已 done 任务幂等; deleteTask 幂等) | ✓ (重复调用结果一致) | — (无副作用) |
| 类型越界 | ✓ (JSON 类型由 Python 保证) | ✓ (priority/status 枚举校验) | ✓ (统计计数不会溢出) | ✓ (action 未知时 help) |
| 依赖故障 | — (无外部依赖) | ✓ (storage 读取失败时降级为空数组) | ✓ (tasks 返回空时正常统计) | ✓ (tasks/stats 抛异常时捕获打印) |

---

## 数据流

@FLOW 添加任务
  步骤: 用户 → cli.parseArgs() → tasks.addTask() → storage.saveTasks() → cli.formatTask() → 终端
  涉及: cli, tasks, storage

@FLOW 列出任务
  步骤: 用户 → cli.parseArgs() → tasks.listTasks() → storage.loadTasks() → cli.formatTaskList() → 终端
  涉及: cli, tasks, storage

@FLOW 查看单个任务
  步骤: 用户 → cli.parseArgs() → tasks.getTask(id) → storage.loadTasks() → cli.formatTask() → 终端
  涉及: cli, tasks, storage

@FLOW 更新任务
  步骤: 用户 → cli.parseArgs() → tasks.updateTask(id, fields) → storage.loadTasks() → storage.saveTasks() → cli.formatTask() → 终端
  涉及: cli, tasks, storage

@FLOW 删除任务
  步骤: 用户 → cli.parseArgs() → tasks.deleteTask(id) → storage.loadTasks() → storage.saveTasks() → 终端
  涉及: cli, tasks, storage

@FLOW 完成任务
  步骤: 用户 → cli.parseArgs() → tasks.markDone(id) → storage.loadTasks() → storage.saveTasks() → cli.formatTask() → 终端
  涉及: cli, tasks, storage

@FLOW 开始任务
  步骤: 用户 → cli.parseArgs() → tasks.markInProgress(id) → storage.loadTasks() → storage.saveTasks() → cli.formatTask() → 终端
  涉及: cli, tasks, storage

@FLOW 查看统计
  步骤: 用户 → cli.parseArgs() → stats.getStats(filter) → tasks.listTasks(filter) → storage.loadTasks() → cli.formatStats() → 终端
  涉及: cli, stats, tasks, storage

@FLOW 查看逾期
  步骤: 用户 → cli.parseArgs() → stats.getOverdue() → tasks.listTasks() → storage.loadTasks() → cli.formatTaskList() → 终端
  涉及: cli, stats, tasks, storage

---

## 数据结构

@DATA Task
  字段: id:int, title:string, description:string, priority:enum[high|medium|low],
        status:enum[todo|in_progress|done], dueDate:date|null, tags:string[],
        createdAt:datetime, completedAt:datetime|null

@DATA TaskFilter
  字段: status:enum|null, priority:enum|null, tags:string[]|null,
        keyword:string|null, dueBefore:date|null, dueAfter:date|null,
        sortBy:enum[priority|dueDate|createdAt]|null, sortDesc:bool

@DATA Stats
  字段: total:int, todo:int, inProgress:int, done:int,
        completionRate:float, overdue:int

@DATA Command
  字段: action:enum[add|list|get|update|delete|done|start|stats|overdue|help],
        params:dict, flags:dict

---

## 构建顺序

@BUILD_ORDER
  第 1 层（无依赖）: storage
  第 2 层（依赖第 1 层）: tasks
  第 3 层（依赖第 2 层）: stats
  第 4 层（依赖第 2、3 层）: cli

---

## 跨切面关注点

@CROSSCUT 错误处理
  策略: 数据层降级不抛异常（文件不存在返回空），业务层参数非法抛 ValueError，
        CLI 层捕获所有异常并打印用户友好的错误信息

@CROSSCUT 数据持久化
  策略: 所有变更操作（add/update/delete/mark）都通过 saveTasks 持久化；
        tasks.json 存储在用户目录 ~/.task-cli/data/

@CROSSCUT CLI 参数约定
  策略: 子命令风格：task add|list|get|update|delete|done|start|stats|overdue
        --priority high|medium|low  --due YYYY-MM-DD  --tag tag1,tag2  --keyword xxx

@CROSSCUT ID 生成
  策略: 自增整数 ID，loadTasks 时取 max(id)+1 作为下一个 ID 的起始值

---

## 错误链映射

@ERROR_CHAIN 存储文件损坏
  源头: storage.loadTasks() → JSON 解析失败
  传播: tasks.listTasks() → 返回空数组（降级，现有数据丢失但可重建）
  终点: 上层正常执行，用户看到空列表（可重新添加任务）

@ERROR_CHAIN 操作不存在的任务
  源头: tasks.getTask(id) → null
  传播: cli.formatTask(null) → 不调用，直接打印"任务 #id 不存在"
  终点: cli 内部闭合

@ERROR_CHAIN 添加任务时存储写入失败
  源头: storage.saveTasks() → 写入失败
  传播: tasks.addTask() → 无法保证持久化，返回 Task 对象但警告用户
  终点: cli 打印"⚠ 保存失败，任务仅在本次会话中有效"

---

## 设计决策

@DECISION_001
  场景: 存储的降级策略
  选择: 文件不存在/损坏时返回空数组而非抛异常
  理由: CLI 工具应始终可启动；首次使用没有文件是正常状态，不应报错
  替代方案考虑过: 抛异常并要求用户初始化 → 对零配置体验不友好
  影响: 所有读取操作需要处理空数组，但逻辑简单

@DECISION_002
  场景: CLI 错误处理策略
  选择: CLI 层统一 try/catch，不向外抛异常
  理由: 命令行工具的任何错误都应翻译为用户可读的信息，而非 Python traceback
  替代方案考虑过: 每个命令自己处理 → 代码重复，错误信息不一致
  影响: cli 模块作为唯一入口，承担所有错误翻译职责

---

## 变更日志

@CHANGE_001
  阶段: Phase 1
  触发: 初始蓝图设计
  原因: 首次创建蓝图
  修改: 无（初始版本）
  影响: 无

@CHANGE_002
  阶段: Phase 2 / tasks
  触发: 实现 addTask 时发现需要 tags 参数默认值
  原因: 原蓝图未指定 tags 默认值
  修改: addTask 的 tags 参数默认值设为空数组 []
  影响: 无（新增参数，不影响已有接口）

@CHANGE_003
  阶段: Phase 2 / stats
  触发: 实现 getStats 时发现需要 filter 参数
  原因: 统计应支持按条件筛选，而非总是全量
  修改: getStats 签名从 getStats() → getStats(filter: TaskFilter | null)
  影响: cli 调用 getStats 时需传入 filter（cli 模块尚未开始，无成本）

@VERIFY
  添加任务:
    run: python src/main.py add "买牛奶" --priority high
    expect-exit: 0
    expect-not-contains: Traceback
  列出任务:
    run: python src/main.py list
    expect-exit: 0
    expect-not-contains: Traceback
  统计:
    run: python src/main.py stats
    expect-exit: 0
    expect-not-contains: Traceback

## 目录结构（约束 5：模块边界）

src/
├── storage/           ← 第 1 层 [empty]
│   └── __init__.py
├── tasks/             ← 第 2 层 [empty]
│   └── __init__.py
├── stats/             ← 第 3 层 [empty]
│   └── __init__.py
├── cli/               ← 第 4 层 [empty]
│   └── __init__.py
├── main.py            ← 入口
└── .arch/
    └── BLUEPRINT.md   ← 本文件