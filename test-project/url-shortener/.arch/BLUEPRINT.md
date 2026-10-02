# 项目蓝图 — URL 短链服务

@META
  version: 2.0
  skill: arch-first-dev
  created: 2026-05-17
  updated: 2026-08-29

@PROGRESS
  storage        ██████████ [done]
  encoder        ██████████ [done]
  analytics      ██████████ [done]
  api            ██████████ [done]
  cli            ██████████ [done]

@MODULE storage
  职责: 长 URL 与短码映射关系的持久化（SQLite 单文件）
  接口:
    save_mapping(short_code: str, long_url: str, ttl: int | null) → bool
      pre: short_code 与 long_url 非空
      post: 成功时 url_mappings 存在该映射并返回 True；short_code 已存在时返回 False
      error: 无（唯一性冲突降级为返回 False，不抛异常）
      side-effect: url_mappings 插入一行；ttl 非空时写入 expires_at
    get_long_url(short_code: str) → str | null
      post: 存在且未过期返回 long_url；不存在或已过期返回 null
      side-effect: 无
    delete_mapping(short_code: str) → bool
      post: 存在则删除并返回 True；不存在返回 False
      side-effect: url_mappings 删除该行
  依赖: 无（直接使用 @EXTERNAL sqlite3）
  状态: [done]

@MODULE encoder
  职责: 长 URL 合法性校验与 Base62 随机短码生成
  接口:
    encode(long_url: str) → str
      pre: long_url 是合法的 http(s) URL
      post: 返回 6 位 Base62（a-zA-Z0-9）随机短码
      error: URL 非法 → ValueError
      side-effect: 无
    is_valid_code(short_code: str) → bool
      post: short_code 匹配 [a-zA-Z0-9]{6,8} 时返回 True
      side-effect: 无
  依赖: 无
  状态: [done]

@MODULE analytics
  职责: 短码点击计数与最后点击时间统计（直接读写共享 SQLite）
  接口:
    record_click(short_code: str, ip: str | null, user_agent: str | null) → None
      pre: short_code 存在于 url_mappings
      post: click_count 加 1，且 click_events 插入一条记录
      side-effect: 同步写 SQLite（在重定向路径上，见 @DECISION_003）
    get_stats(short_code: str) → dict
      post: 返回 {clicks: int, last_click: datetime | null}；短码不存在返回 {clicks: 0, last_click: null}
      side-effect: 无
  依赖: 无（直接使用 @EXTERNAL sqlite3，与 storage 共库）
  状态: [done]

@MODULE api
  职责: HTTP API 层（FastAPI），路由绑定见 @CROSSCUT
  接口:
    shorten_url(request: ShortenRequest) → ShortenResponse
      post: 返回 {short_code, short_url}
      error: 重试 3 次仍冲突 → HTTP 409
      side-effect: 调用 encoder.encode() 与 storage.save_mapping()
    redirect_url(short_code: str, request: Request) → RedirectResponse
      post: 302 重定向到 long_url
      error: 短码格式非法 → HTTP 400；不存在或已过期 → HTTP 404
      side-effect: 调用 analytics.record_click()
    delete_url(short_code: str) → None
      post: HTTP 204
      error: 短码格式非法 → HTTP 400；不存在 → HTTP 404
      side-effect: 调用 storage.delete_mapping()
  依赖: storage → save_mapping(), get_long_url(), delete_mapping()
        encoder → encode(), is_valid_code()
        analytics → record_click()
  状态: [done]

@MODULE cli
  职责: 命令行入口，argparse 子命令分发
  接口:
    main() → int
      pre: 无（参数经 argparse 从 sys.argv 读取）
      post: 按 shorten | stats | delete 子命令分发执行并打印结果
      error: 短码不存在或短码生成冲突 → stderr 提示 + 退出码 1
      side-effect: shorten/delete 子命令修改数据库；delete 无 --force 时交互确认
  依赖: storage → save_mapping(), get_long_url(), delete_mapping()
        analytics → get_stats()
        encoder → encode()
  状态: [done]

@DATA URLMapping
  short_code: str    // [a-zA-Z0-9]{6}，主键
  long_url: str      // 合法 http(s) URL
  created_at: datetime
  expires_at: datetime | null
  click_count: int = 0

@DATA ClickEvent
  short_code: str
  ip: str | null
  user_agent: str | null
  timestamp: datetime

@FLOW 创建短链（API）
  步骤: 客户端 → api.shorten_url() → encoder.encode() → storage.save_mapping() → 返回 {short_code, short_url}
  涉及: api, encoder, storage

@FLOW 创建短链（CLI）
  步骤: 用户 → cli.main() → encoder.encode() → storage.save_mapping() → 终端
  涉及: cli, encoder, storage

@FLOW 重定向
  步骤: 客户端 → api.redirect_url() → encoder.is_valid_code() → storage.get_long_url() → analytics.record_click() → 302
  涉及: api, encoder, storage, analytics

@FLOW 删除短链（API）
  步骤: 客户端 → api.delete_url() → encoder.is_valid_code() → storage.delete_mapping() → 204
  涉及: api, encoder, storage

@FLOW 删除短链（CLI）
  步骤: 用户 → cli.main() → storage.get_long_url() → storage.delete_mapping() → 终端
  涉及: cli, storage

@FLOW 查询统计（CLI）
  步骤: 用户 → cli.main() → storage.get_long_url() → analytics.get_stats() → 终端
  涉及: cli, storage, analytics

@BUILD_ORDER
  第 1 层（无依赖）: storage, encoder, analytics
  第 2 层（依赖第 1 层）: api, cli

@CROSSCUT HTTP 绑定
  策略: POST /shorten → api.shorten_url；GET /{short_code} → api.redirect_url；
        DELETE /{short_code} → api.delete_url（FastAPI + Pydantic + Uvicorn，
        框架属于技术栈而非故障源，不列入 @EXTERNAL）

@CROSSCUT CLI 参数约定
  策略: shorten <url> [--ttl N] | stats <short_code> | delete <short_code> [--force]

@CROSSCUT 短码冲突重试
  策略: 生成冲突最多重试 3 次；api 与 cli 各自实现该循环（已知重复，v2 待收敛）

@EXTERNAL sqlite3
  类型: 本地关系数据库（单文件 urls.db）
  契约: url_mappings 与 click_events 两张表，结构与 @DATA 一致；
        storage 与 analytics 直连同一库文件
  故障模式: 连接/SQL 失败 → sqlite3 异常向上传播（当前实现未捕获，已知缺口）
  幂等性: save_mapping 靠主键约束天然幂等（重复写返回 False）；record_click 非幂等（每次调用计数 +1）
  重试: 无（本地单机库，连接失败不重试，直接抛出）
  超时: 依赖 sqlite3 默认 5 秒锁等待
  事务边界: 每个接口函数内 commit（save_mapping/record_click 单语句事务；
        未使用显式 BEGIN，多写操作间无原子性保证——已知缺口）

@ERROR_CHAIN 短码生成冲突
  源头: encoder.encode() → 随机短码碰撞（概率低但存在）
  传播: storage.save_mapping() → 唯一约束冲突 → 返回 False
  终点: 重试最多 3 次 → 仍冲突则 HTTP 409 / CLI 退出码 1

@ERROR_CHAIN 短码无效或不存在
  源头: encoder.is_valid_code() → False / storage.get_long_url() → null
  传播: api 层翻译为 HTTP 400 / 404；cli 层翻译为 stderr + 退出码 1
  终点: 调用方（客户端/用户）得到明确错误，无未捕获异常

@DECISION_001
  场景: 短码生成策略
  选择: Base62 随机编码（a-zA-Z0-9）6 位
  理由: 6 位约 568 亿组合，个人/小团队场景足够；实现简单
  替代方案考虑过: 自增 ID + Base62（可枚举、易被遍历）、哈希截断（需处理冲突）
  影响: encoder 无状态；冲突靠重试解决

@DECISION_002
  场景: 存储后端
  选择: SQLite 本地单文件
  理由: 零配置、单文件部署，匹配 CLI + 本地服务的使用场景
  替代方案考虑过: PostgreSQL（需额外服务）、Redis（内存限制）
  影响: 未来分布式部署需要迁移层

@DECISION_003
  场景: record_click 的写入方式
  选择: 同步写入（v1 蓝图误标为"异步"，与实现不符，本次修正）
  理由: 实现即同步；诚实记录现状，异步化列为后续优化而非既成事实
  替代方案考虑过: 后台队列异步写（增加复杂度，当前流量下无必要）
  影响: 重定向路径上多一次 SQLite 写延迟

@VERIFY
  创建短链（CLI 冒烟）:
    run: python src/cli.py shorten https://example.com --ttl 3600
    expect-exit: 0
    expect-contains: Short URL
  无效短码查询（错误链闭合）:
    run: python src/cli.py stats ZZZZZZZZ
    expect-exit: 1
    expect-contains: not found
    expect-not-contains: Traceback

@CHANGE
  - 2026-05-17: 初始版本（v1 接口计数标注为 12，计数有误）
  - 2026-08-29: 规范化修订（version 1.0.0 → 2.0）：接口计数修正为 11；
    api 模块接口从 HTTP 路由名改写为处理函数名（与代码导出一致）；
    record_click 行为声明从"异步写入"修正为"同步写入"；
    cli 三个子命令合并为 main() 一个接口（与 argparse 分发实现一致）；
    补全 @PROGRESS 状态、@ERROR_CHAIN、@EXTERNAL 故障模式、@BUILD_ORDER 分层
