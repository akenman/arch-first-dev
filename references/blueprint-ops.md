# 蓝图运维（逆向 / 外部契约格式 / 协作 / 修正协议）

> 加载条件：逆向现有项目、@EXTERNAL 完整格式参考、git 协作约定、蓝图修正协议。
> 特性分诊标签：【已验证】= 有 eval 实证；【未验证】= 设计存在但从未被 eval 触达，
> 使用前请自行验证。证据矩阵见 README.md「特性 × 证据」。按 SKILL.md L3 路由器读取，未命中不读。

## 逆向蓝图（8 步完整流程）【已验证】

> 加载条件：现有项目需要逆向蓝图时。腐化/超大项目先用 legacy-mode.md 的考古协议。

```
第 0 步：运行时探针（可选）：能运行的项目先跑起来，从日志提取 @FLOW 雏形与边界条件
第 1 步：列出项目文件（排除测试/配置/生成文件）
第 2 步：按目录/框架惯例识别模块（框架边界惯例表见 legacy-mode.md）
第 3 步：提取接口签名（只读入口文件导出，不读内部实现）
第 4 步：从 import/require/use 推断依赖（跨模块引用，不含标准库与第三方包）
第 5 步：生成 @DATA（跨模块共享的类型才进蓝图）
第 6 步：生成 @FLOW（从入口追踪调用链，核心路径即可）
第 7 步：标注 [done] / [done]+@UNCLEAR / [empty]（需补充实现的部分）
第 8 步：整理为 BLUEPRINT.md。模块状态按第 7 步结果标注；
        整理完成后运行 validate_blueprint.py 校验格式与拓扑
```

逆向蓝图完成后，修改需求进入迭代模式。并非从 Phase 1 重新开始。

## @EXTERNAL 完整格式示例【已验证】

```
@EXTERNAL PostgreSQL
  类型: 关系数据库
  连接: DATABASE_URL 环境变量
  契约:
    - 所有持久化操作通过此数据库，不使用 ORM（直接 SQL）
    - 表结构与 @DATA 一一对应
    - 连接池: min=2, max=10
  幂等性: INSERT 带 ON CONFLICT DO NOTHING（重复提交安全）；DELETE 幂等
  重试: 连接失败重试 3 次（指数退避 1s/2s/4s）；查询超时不重试
  超时: 连接 5s / 查询 30s
  事务边界: Service 层开启事务、提交/回滚；Storage 层不开事务
  故障模式: 连接失败 → 重试 3 次 → 抛 DatabaseError

@EXTERNAL Stripe API
  类型: 第三方支付
  认证: STRIPE_SECRET_KEY
  契约:
    - createPayment(amount, currency) → PaymentIntent
    - 仅 payments 模块可以调用
  幂等性: 传 Idempotency-Key（订单号 + 尝试次数）
  重试: 网络错误重试 1 次；429 按响应头退避
  超时: 10s
  事务边界: 外部调用不参与本地事务——本地先落 pending 记录，回调后更新
  故障模式: API 超时 → 重试 1 次 → 返回 pending 状态
```

## Git 轻量协作【未验证-约定】

```
- 蓝图修改建议独立 commit，message 引用 @CHANGE 编号（如 "blueprint: @CHANGE_007 提取支付路由"）
- PR 描述可直接由本次 @CHANGE/@DECISION 汇总生成（改了什么 / 为什么 / 影响面）
- 会话并行用分支隔离，合并前跑 validate_blueprint.py --check-signatures
- 跨模块改动前先过影响面四问——git 只记录改动，不替你思考波及面
```

## 蓝图修正协议【未验证】

Phase 2 发现蓝图设计本身有问题（非单接口缺失）时触发。触发条件（任一）：
同一模块连续 3 个接口的依赖走不通；传递依赖比预期深 ≥ 2 层；用户反馈模块划分
不合理；@EXTERNAL 实际访问权限与契约不一致。

```
1. 暂停 Phase 2，进度记 CHECKPOINT.md（状态 [restructuring]）
2. 记 @RESTRUCTURE 条目（触发/分析/操作）
3. 重新执行 Phase 1 ④-⑦
4. 级联更新 @MODULE/@BUILD_ORDER/@FLOW 受影响条目
5. 受影响模块及其下游 → [empty]
6. 用户确认新蓝图 → 恢复 Phase 2
```

与普通异常的区别：单接口缺失 → 填充异常微调；单模块太大 → 局部拆分；
蓝图问题 → 本协议（回 Phase 1，级联多模块）。
