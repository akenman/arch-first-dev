# 项目蓝图 — 收藏链接管理 CLI（任务 crud-link-005）

@META
  version: 1.0
  pattern: crud-cli
  seed: 42005

@PROGRESS
  link_store   [empty]
  link_svc     [empty]
  cli     [empty]

@MODULE link_store
  职责: 收藏链接记录的 JSON 文件持久化（data/link.json）
  接口:
    load_all() -> list
      post: 返回记录列表；文件不存在返回空列表
      error: 文件损坏（JSON 解析失败）时返回空列表（降级，不抛异常）
      side-effect: 无
    append_one(item: dict) -> int
      pre: item 含必填字段 url、tags、note
      post: 返回自增整数 id（max(现有id)+1，空集为 1）；记录追加进文件
      error: 必填字段缺失抛 ValueError
      side-effect: 持久化文件追加一条记录
    remove_one(rid: int) -> bool
      pre: rid > 0
      post: 存在则删除返回 True；不存在返回 False（幂等）
      side-effect: 删除时持久化文件移除该记录
  状态: [empty]
  依赖: 无（直接使用 @EXTERNAL json 文件）

@MODULE link_svc
  职责: 收藏链接业务校验与聚合查询
  接口:
    create(items: list, payload: dict) -> dict
      pre: payload 满足：url 以 http:// 或 https:// 开头
      post: 校验通过时调用 link_store.append_one 并返回含 id 的完整记录
      error: 校验失败抛 ValueError（消息含字段名）
      side-effect: 经 link_store.append_one 持久化一条记录
    aggregate(items: list) -> dict
      pre: items 中每条记录含聚合所需字段
      post: 按 tag 聚合计数；返回 dict 且键为聚合维度
      error: 无
      side-effect: 无
  状态: [empty]
  依赖: link_store → load_all(), append_one()

@MODULE cli
  职责: 命令行入口，参数分发与输出
  接口:
    run(argv: list) -> int
      pre: argv 为命令行参数列表
      post: 按 add/list/remove 子命令分发；成功 exit 0，业务错误 exit 1 且打印含 "error:" 的提示
      error: 未知子命令 exit 2
      side-effect: add 子命令经 link_svc.create 持久化一条记录
  状态: [empty]
  依赖: link_svc → create(), aggregate()
        link_store → load_all(), remove_one()

@FLOW 新增收藏链接
  步骤: 用户 → cli.run() → link_svc.create() → link_store.append_one() → 终端
  涉及: cli, link_svc, link_store

@FLOW tag_cloud聚合
  步骤: 用户 → cli.run() → link_svc.aggregate() → link_store.load_all() → 终端
  涉及: cli, link_svc, link_store

@FLOW 删除收藏链接
  步骤: 用户 → cli.run() → link_store.remove_one() → 终端
  涉及: cli, link_store

@DATA 收藏链接
  url: str
  tags: str
  note: str|null

@BUILD_ORDER
  第 1 层: link_store
  第 2 层: link_svc
  第 3 层: cli

@CROSSCUT 错误处理
  策略: 存储层降级不抛异常；业务层非法参数抛 ValueError；CLI 层捕获后打印 error: 前缀并返回退出码

@EXTERNAL link.json
  类型: 本地 JSON 文件存储
  契约: 记录列表，结构与 @DATA 一致
  幂等性: append_one 非幂等（每次追加）；remove_one 幂等
  重试: 无（本地文件）
  超时: 无
  事务边界: 每次写操作整文件覆盖写
  故障模式: 磁盘满/只读 → 异常向上传播，CLI 打印 error:

@VERIFY
  add成功路径:
    run: python src/main.py add --demo
    expect-exit: 0
    expect-not-contains: Traceback
  list成功路径:
    run: python src/main.py list
    expect-exit: 0
    expect-not-contains: Traceback
  remove路径:
    run: python src/main.py remove --demo
    expect-exit: 0
    expect-not-contains: Traceback
