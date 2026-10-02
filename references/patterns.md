# 蓝图模式库

> 加载条件：Phase 1 画蓝图时，或用户说"用模式设计"
> 难度：⭐⭐⭐（中）

## 概念

80% 的项目架构是相似模式的组合。蓝图模式库将常见架构抽象为参数化模板，Phase 1 从"从零设计"降级为"组装+微调"，蓝图生成速度提升 5-10 倍。

```
当前：用户说"做一个博客" → AI 从零设计模块/接口/数据流（10-15 分钟）
未来：用户说"做一个博客" → 匹配 "CRUD + 用户认证 + 内容发布" 模式组合
      → 3 秒生成 80% 完成度的蓝图骨架 → 用户微调 → Phase 2
```

## 模式格式

每个模式包含 4 部分：参数、产出、约束、组合规则。

```
@PATTERN <name>
  描述: 一句话说明适用场景
  参数: {param: type, ...}
  产出:
    @MODULE: 模块列表（含接口签名和 BEHAVIOR 骨架）
    @DATA: 数据结构列表
    @FLOW: 标准数据流列表
    @EXTERNAL: 外部依赖（如有）
  约束: 使用此模式时必须满足的条件
  组合: 与其他模式的兼容性和冲突说明
```

## 内置模式

### @PATTERN crud

```
描述: 单实体的增删改查，最基础的架构模式
参数: {entity: string, fields: Field[], storage: "memory"|"file"|"db"}

产出:
  @MODULE {entity}Storage
    接口:
      save{entity}(item: {Entity}) → {Entity}
        pre: item 的必填字段非空
        post: 返回的 item.id 已赋值
        error: 必填字段缺失 → ValueError
        side-effect: 持久化存储写入一条记录
      get{entity}(id: int) → {Entity} | null
        pre: id > 0
        post: 返回对应记录或 null
      list{entity}s(filter: {Entity}Filter | null) → list[{Entity}]
        post: 返回匹配的记录列表
      delete{entity}(id: int) → bool
        post: 返回是否删除成功
    依赖: @EXTERNAL 存储

  @MODULE {entity}Service
    接口:
      create(params: dict) → {Entity}
        pre: params 含所有必填字段
        post: 返回已持久化的 {Entity}
        error: 字段校验失败 → ValueError
        side-effect: 调用 {entity}Storage.save{entity}
      read(id: int) → {Entity}
        pre: id > 0
        error: 记录不存在 → NotFoundError
      update(id: int, params: dict) → {Entity}
        pre: id > 0 且记录存在
        post: 返回更新后的 {Entity}
      delete(id: int) → bool
        pre: id > 0
    依赖: {entity}Storage

  @DATA {Entity}: {fields}
  @DATA {Entity}Filter: {field: value, ...}（可选过滤条件）

  @FLOW 创建{entity}: 用户 → Service.create → Storage.save → 返回
  @FLOW 读取{entity}: 用户 → Service.read → Storage.get → 返回
  @FLOW 更新{entity}: 用户 → Service.update → Storage.save → 返回
  @FLOW 删除{entity}: 用户 → Service.delete → Storage.delete → 返回
  @FLOW 列表{entity}: 用户 → Service.list → Storage.list → 返回

约束:
  - Service 层做业务校验，Storage 层只做持久化
  - Filter 的字段必须是 {Entity} 的子集

组合:
  - 可与 user-auth 组合（给 CRUD 加权限控制）
  - 可与 event-driven 组合（给 CRUD 加事件通知）
  - 多次实例化：一个项目可以有多个 CRUD 实体
```

### @PATTERN user-auth

```
描述: 用户注册/登录/鉴权，几乎所有应用都需要
参数: {method: "jwt"|"session"|"oauth", storage: "db"|"redis"|"memory"}

产出:
  @MODULE auth
    接口:
      login(credentials: Credentials) → Token
        pre: credentials 非空
        post: 返回有效 token
        error: 凭据无效 → AuthError
        side-effect: 记录登录时间
      logout(token: string) → None
        pre: token 有效
        side-effect: 使 token 失效
      validateToken(token: string) → UserInfo
        pre: token 非空
        post: 返回用户信息
        error: token 过期/无效 → AuthError
      refreshToken(token: string) → Token
        pre: token 在刷新窗口内
        post: 返回新 token
        error: token 已过期无法刷新 → AuthError
    依赖: users

  @MODULE users
    接口:
      createUser(data: UserData) → User
        pre: data.username 和 data.password 非空
        post: 返回已创建的 User（id > 0）
        error: 用户名已存在 → DuplicateError
      getUser(id: int) → User
        pre: id > 0
        error: 用户不存在 → NotFoundError
      updateUser(id: int, data: Partial<UserData>) → User
        pre: id > 0 且用户存在

  @DATA User: {id, username, email, createdAt, lastLogin}
  @DATA Credentials: {username, password}
  @DATA Token: {accessToken, refreshToken, expiresIn}
  @DATA UserInfo: {userId, username, role}

  @FLOW 登录: 用户 → auth.login → users.getUser → 生成 token → 返回
  @FLOW 注册: 用户 → users.createUser → auth.login → 返回 token
  @FLOW 鉴权: 请求 → auth.validateToken → 放行/拒绝
  @FLOW 刷新: 请求 → auth.refreshToken → 返回新 token

  @ERROR_CHAIN
    源头: auth.validateToken → token 过期
    传播: 调用方收到 AuthError → 决定是否刷新
    终点: 刷新成功继续 / 刷新失败重定向登录

约束:
  - 密码不明文存储（必须 hash）
  - token 有过期时间
  - 仅 auth 模块可以生成/验证 token

组合:
  - 可与 crud 组合（给实体加权限：仅创建者可修改）
  - 可与 event-driven 组合（登录成功发布 UserLoggedIn 事件）
```

### @PATTERN event-driven

```
描述: 异步事件驱动架构，适用于解耦模块间通信
参数: {events: Event[], handlers: Handler[]}

产出:
  @MODULE eventBus
    接口:
      publish(event: Event) → None
        pre: event.type 已注册
        post: 所有订阅者收到事件
        side-effect: 触发订阅者处理
      subscribe(eventType: string, handler: Function) → Subscription
        pre: eventType 非空
        post: 返回可取消的订阅
      unsubscribe(subscription: Subscription) → None
        post: 订阅者不再收到事件

  @DATA Event: {type: string, payload: dict, timestamp: datetime, source: string}
  @DATA Subscription: {id: string, eventType: string, handler: string}

  @FLOW 事件发布: 模块 → eventBus.publish → [订阅者1.handle, 订阅者2.handle, ...]
  @FLOW 事件订阅: 模块 → eventBus.subscribe → 返回 Subscription
  @FLOW 事件取消订阅: 模块 → eventBus.unsubscribe → 取消

约束:
  - 发布者不知道订阅者是谁（完全解耦）
  - 事件处理失败不影响发布者
  - 事件顺序不保证（如需顺序，用同步 @FLOW）

组合:
  - 可与 crud 组合（CRUD 操作发布事件：EntityCreated / EntityUpdated / EntityDeleted）
  - 可与 user-auth 组合（登录/登出发布事件）
  - 补偿模式：事件处理失败时发布补偿事件（如 OrderCreated → 库存不足 → OrderCancelled）
```

### @PATTERN cli-frontend

```
描述: 命令行界面，CLI 工具的标准前端模式
参数: {commands: Command[], globalOptions: Option[]}

产出:
  @MODULE cli
    接口:
      parseArgs(argv: list[string]) → Command
        pre: argv 非空
        post: 返回解析后的命令对象
        error: 未知命令/参数 → UsageError
      formatOutput(data: any, format: string) → string
        post: 返回格式化的输出字符串
      handleError(error: Exception) → None
        post: 输出用户友好的错误信息
        side-effect: 设置退出码非零

  @DATA Command: {name: string, args: dict, options: dict}
  @DATA Option: {name: string, shortName: string, type: string, default: any, description: string}

  @FLOW 命令执行: 用户 → cli.parseArgs → 业务模块.方法 → cli.formatOutput → 终端
  @FLOW 错误处理: 业务模块.异常 → cli.handleError → 终端（退出码非零）

约束:
  - CLI 层不做业务逻辑，只做解析和格式化
  - 所有错误统一由 handleError 处理，不向用户暴露 traceback
  - 退出码: 0=成功, 1=业务错误, 2=参数错误

组合:
  - 可与 crud 组合（CLI 命令映射到 CRUD 操作）
  - 可与 user-auth 组合（CLI 支持登录/登出命令）
```

### @PATTERN api-frontend

```
描述: HTTP API 前端，Web 服务的标准接口层
参数: {routes: Route[], auth: bool, format: "json"|"xml"}

产出:
  @MODULE api
    接口:
      handleRequest(method: string, path: string, body: dict, headers: dict) → Response
        pre: method ∈ {GET, POST, PUT, DELETE, PATCH}
        post: 返回标准 Response
        error: 路由不存在 → 404, 鉴权失败 → 401, 参数错误 → 400
      validateInput(schema: Schema, data: dict) → dict
        pre: schema 已定义
        post: 返回校验后的数据
        error: 校验失败 → ValidationError

  @DATA Response: {status: int, body: dict, headers: dict}
  @DATA Route: {method: string, path: string, handler: string, auth: bool}

  @FLOW API 请求: 客户端 → api.handleRequest → [auth.validateToken] → 业务模块 → api 返回 Response
  @FLOW 错误响应: 业务异常 → api 格式化为 {error: {code, message}} → 返回对应 HTTP 状态码

约束:
  - API 层不做业务逻辑，只做路由、鉴权、校验、格式化
  - 所有响应使用统一格式
  - 错误响应不暴露内部实现细节

组合:
  - 可与 crud 组合（RESTful API 映射到 CRUD 操作）
  - 可与 user-auth 组合（API 鉴权）
  - 可与 event-driven 组合（API 请求触发异步事件）
```

### @PATTERN legacy-seam（防腐层/接缝）

```
描述: 在腐化代码与新代码之间插入一层稳定接口，让新逻辑不依赖屎山的内部结构
适用: 屎山模式第 3 步"选缝"（见 legacy-mode.md）
参数: {target: 被包裹的腐化模块, surface: 新代码需要的最小接口列表}

产出:
  @MODULE {target}Seam（适配器）
    接口:
      每个 seam 方法 → 转发到旧实现
        post: 转发语义与旧实现现状一致（包括怪异行为——先固化再谈修正）
        side-effect: 无（纯转发层，不做业务）
    依赖: {target}
    状态: [empty]

  @DATA SeamContract: {surface 中每个方法的签名与现状行为描述}

约束:
  - seam 不做"顺手修复"——发现的行为问题记 @DEBT（类型: 行为可疑），按迭代偿还
  - seam 是暂时的：绞杀完成后 seam 退役（[removed] + @CHANGE）
  - seam 接口按新代码的需要设计（面向未来），转发实现面向现状（如实）

组合:
  - 与 strangler 组合：seam 后面逐单元替换实现
  - 与 crud 组合：缝后面重建的第一个模块常是规范的 CRUD
```

### @PATTERN strangler（绞杀者迁移）

```
描述: 不重写。新实现与旧实现并存，按功能单元逐块切换，旧实现逐步退役
适用: 屎山模式第 4 步"小步迁移"；也适用于任何"边跑边换引擎"的演进式重构
参数: {units: 迁移单元列表（按影响面从小到大排序）, switch: 切换机制（路由/配置/特性开关）}

产出:
  新模块若干：按目标蓝图正常设计（走 G3/迭代流程）
  @MODULE switch（路由/开关层）
    接口:
      route(unit: string, request) → Response
        pre: unit ∈ units
        post: 按开关状态转发到新实现或旧实现
        side-effect: 无
  @FLOW 每个迁移单元一条:
    入口 → switch.route → 新实现.方法（旧实现.方法 [deprecated, 并行保留]）

约束:
  - 迁移单元按影响面从小到大排序，第一个单元必须最小且可回滚
  - 同一时刻只有一个单元处于切换态
  - 每步迁移前：安全网（特征测试）全绿 + validate_blueprint.py 通过 + 项目质量门通过
  - 旧实现退役必须显式（[removed] + @CHANGE），禁止"先留着以后删"
  - 切换机制本身要简单到不需要测试策略（配置项/一行路由）

组合:
  - 与 legacy-seam 组合：seam 是绞杀的手术入口
  - 单元内部是完整的 G3/迭代小循环
```

## 模式组合规则

```
1. 模式间通过 @EXTERNAL 声明引用
   例: crud 模式的 {entity}Storage 依赖 @EXTERNAL 存储
       user-auth 模式的 auth 依赖 users 模块

2. 同名接口自动合并
   例: 两个模式都需要 auth.validateToken → 只保留一份
   合并条件: 签名完全一致
   签名冲突 → 报错，需用户手动解决

3. 模式实例化
   一个模式可以多次实例化：
   @PATTERN crud → {entity: "Task"} → TaskStorage + TaskService
   @PATTERN crud → {entity: "Category"} → CategoryStorage + CategoryService
   实例之间完全独立，无依赖

4. 模式组合示例：博客系统
   @PATTERN user-auth → {method: "jwt", storage: "db"}
   @PATTERN crud → {entity: "Post", fields: [...], storage: "db"}
   @PATTERN crud → {entity: "Comment", fields: [...], storage: "db"}
   @PATTERN api-frontend → {routes: [...], auth: true}

   自动合并后的蓝图：
   - auth + users 模块（来自 user-auth）
   - postStorage + postService 模块（来自 crud:Post）
   - commentStorage + commentService 模块（来自 crud:Comment）
   - api 模块（来自 api-frontend）
   - @EXTERNAL 数据库（合并自所有模式的存储依赖）
```

## 使用方式

```
Phase 1 启动时：
  1. 分析用户需求，识别可复用的模式
  2. 列出推荐的模式组合，让用户确认
  3. 实例化模式，生成蓝图骨架
  4. 用户微调（增删模块、修改接口签名、调整 @FLOW）
  5. 补充模式未覆盖的个性化需求
  6. 执行 Phase 1 →2 预检

触发词：
  "用模式设计" → 强制使用模式库
  "做一个 XXX" → 自动匹配模式，无匹配则回退到手动设计
```
