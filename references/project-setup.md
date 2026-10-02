# 项目搭建指南（启动指令 0.1/0.3/0.4 的完整版）

> 从 SKILL.md 迁入（v3.0 减法轮）。启动阶段按需读取。

## 需求澄清（第 0.1 步，需求模糊时触发）

触发条件：用户需求缺少以下任一项 → 用户是谁、核心操作、数据生命周期。
执行方式：向用户提出 3-5 个关键问题，而非自行假设：

- 核心用户是谁？最常用的 3 个操作是什么？
- 数据从哪来？存到哪？保留多久？
- 需要和哪些外部系统交互？
- 有哪些明确的"不能做"约束？

产出：用户确认的需求要点（2-5 句话），作为 Phase 1 的输入。
不触发条件：需求已足够具体（如"做一个 CLI 待办工具，支持增删改查和统计"）。

## 目录结构（第 0.3 步）

每个模块一个目录，入口文件只导出蓝图上定义的接口。
多语言项目（如 Python 后端 + TypeScript 前端）：

- 每种语言一个顶层目录（如 backend/ + frontend/）
- 每种语言内部按模块划分子目录
- 跨语言接口通过 @EXTERNAL 声明（类型: 内部服务，协议: HTTP API / gRPC / CLI 调用）
- 跨语言接口契约格式：

```
@EXTERNAL 前端→后端 API
  类型: 内部服务
  协议: HTTP REST
  契约:
    - GET /api/tasks → list[Task]
    - POST /api/tasks {title, tags} → Task
  故障模式: 网络错误 → 前端显示"加载失败"提示
```

## 产出物清单（第 0.4 步，Phase 3 完成后检查）

代码模块之外，项目通常还需要以下产出物（按需生成，不是每个项目都要）：

- 项目配置：package.json / pyproject.toml / go.mod / Cargo.toml（必须）
- 运行配置：Dockerfile / docker-compose.yml / .env.example（如需容器化）
- CI 配置：.github/workflows / .gitlab-ci.yml（如需持续集成）
- 项目文档：README.md（项目说明，非蓝图） / API 文档（如有 @EXTERNAL API）
- 测试框架配置：pytest / jest / vitest / go test 等（Phase 2 测试策略依赖）
- 部署脚本：deploy.sh / Makefile（如需自动化部署）
- 数据迁移：migrations/（如 @EXTERNAL 包含数据库且需要 schema 变更）

判断规则：

- 有 @EXTERNAL 数据库 → 必须生成 migrations 和 .env.example
- 有 @EXTERNAL 第三方 API → 必须生成 .env.example（API key 配置）
- 多模块项目 → 建议生成 Makefile 或 scripts/（统一入口）
- 单模块 CLI → 只需 package.json / pyproject.toml
