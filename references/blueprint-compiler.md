# 骨架生成约定（蓝图 → 代码骨架）

> 加载条件：Phase 2 开始前，或用户说"生成代码骨架"
> 难度：⭐⭐⭐⭐（高）
>
> 命名说明（v3.0）：可执行版已实现——scripts/scaffold.py（蓝图 → 锁定签名 /
> dataclass / 契约测试桩，py_compile 自检）。本文档保留为生成规则的人类可读说明。

## 概念

蓝图包含了足够的信息来**自动生成代码骨架**。当前 Phase 2 是 AI 手写代码然后对照蓝图，但蓝图本身就可以编译出代码骨架——函数签名、类型定义、BEHAVIOR 断言、依赖桩全部自动生成，AI 只需填充业务逻辑。

```
当前：蓝图 → AI 读蓝图 → AI 写代码（100%）→ 对照验证
未来：蓝图 → 编译器生成骨架（70%）→ AI 填充业务逻辑（30%）→ 对照验证
```

## 核心收益

1. **减少 AI 自由度** → 减少幻觉空间（函数签名已锁定，AI 只填逻辑）
2. **加速 Phase 2** → 骨架已生成，AI 只需填充业务逻辑
3. **强制蓝图-代码一致性** → 骨架从蓝图编译，天然一致
4. **BEHAVIOR 声明变成可执行断言** → 运行时自动检测违反

## 编译规则

### @MODULE → 目录 + 入口文件

```
蓝图:
  @MODULE tasks
    职责: 任务增删改查 + 状态变更
    接口: addTask, listTasks, ...
    依赖: storage

编译产出:
  tasks/
    __init__.py  (或 index.ts)
    # 导出蓝图定义的所有接口
```

### 接口签名 → 函数骨架

```
蓝图:
  addTask(title: str, tags: list) → Task
    pre: title 非空
    post: 返回的 Task.id 自增唯一
    error: title 为空时抛 ValueError
    side-effect: _data 追加一条记录

Python 编译（v2.1 修订：pre 用显式 raise，不用 assert——
  python -O 会剥离 assert，且 AssertionError 与 error 契约声明的类型矛盾；
  契约注释集中放在 docstring/头部，避免出现在 raise 之后的死代码里）:
  def addTask(title: str, tags: list) -> Task:
      """addTask(title, tags) → Task

      契约（唯一真相源见 BLUEPRINT.md @MODULE tasks → addTask）:
        post: 返回的 Task.id 自增唯一
        error: title 为空时抛 ValueError
        side-effect: _data 追加一条记录
      """
      # pre: title 非空
      if not (title and title.strip()):
          raise ValueError("pre condition violated: title 非空")
      # TODO: 实现业务逻辑（实现完成后删除下一行）
      raise NotImplementedError("addTask not implemented")

TypeScript 编译:
  export function addTask(title: string, tags: string[]): Task {
      /** 契约: @see BLUEPRINT.md @MODULE tasks → addTask
        * post: 返回的 Task.id 自增唯一
        * error: title 为空时抛 Error
        * side-effect: _data 追加一条记录 */
      // pre: title 非空
      if (!title || !title.trim()) {
          throw new Error("pre condition violated: title 非空");
      }
      // TODO: 实现业务逻辑（实现完成后删除下一行）
      throw new Error("addTask not implemented");
  }
```

### @DATA → 数据类/类型定义

```
蓝图:
  @DATA Task: {id: int, title: str, done: bool, tags: list, createdAt: str}

Python 编译:
  from dataclasses import dataclass
  from typing import List
  
  @dataclass
  class Task:
      id: int
      title: str
      done: bool
      tags: List[str]
      createdAt: str

TypeScript 编译:
  export interface Task {
      id: number;
      title: string;
      done: boolean;
      tags: string[];
      createdAt: string;
  }
```

### @EXTERNAL → 接口桩（mock）

```
蓝图:
  @EXTERNAL PostgreSQL
    类型: 关系数据库
    契约: 所有持久化操作通过此数据库
    故障模式: 连接失败 → 重试 3 次 → 抛 DatabaseError

Python 编译:
  class PostgreSQL:
      """External dependency: PostgreSQL. @see BLUEPRINT.md @EXTERNAL"""
      def execute(self, sql: str, params: tuple = None):
          raise NotImplementedError("External: PostgreSQL - execute")
      
      def query(self, sql: str, params: tuple = None) -> list:
          raise NotImplementedError("External: PostgreSQL - query")

TypeScript 编译:
  export class PostgreSQL {
      /** External dependency: PostgreSQL. @see BLUEPRINT.md @EXTERNAL */
      execute(sql: string, params?: any[]): Promise<void> {
          throw new Error("External: PostgreSQL - execute");
      }
      query(sql: string, params?: any[]): Promise<any[]> {
          throw new Error("External: PostgreSQL - query");
      }
  }
```

### @CROSSCUT → 跨切面骨架

```
蓝图:
  @CROSSCUT
    错误处理: 统一错误类 + 全局 try/catch
    日志: logger 实例
    配置: config 加载

Python 编译:
  # errors.py
  class AppError(Exception): pass
  class NotFoundError(AppError): pass
  class ValidationError(AppError): pass
  class DatabaseError(AppError): pass
  
  # logger.py
  import logging
  logger = logging.getLogger(__name__)
  
  # config.py
  import os
  def load_config():
      return {k: os.environ.get(k) for k in ["DATABASE_URL", "LOG_LEVEL"]}
```

### 测试骨架 → 契约测试

```
蓝图:
  addTask(title: str, tags: list) → Task
    pre: title 非空
    post: 返回的 Task.id 自增唯一
    error: title 为空时抛 ValueError

Python 编译:
  import pytest
  from tasks import addTask
  
  def test_addTask_post_id_increments():
      """post: 返回的 Task.id 自增唯一"""
      t1 = addTask("task1", [])
      t2 = addTask("task2", [])
      assert t2.id > t1.id
  
  def test_addTask_error_empty_title():
      """error: title 为空时抛 ValueError"""
      with pytest.raises(ValueError):
          addTask("", [])
  
  def test_addTask_side_effect():
      """side-effect: _data 追加一条记录"""
      # TODO: 验证数据追加
      pass
```

## 编译产出结构

```
project/
  .arch/
    BLUEPRINT.md
    SIGNATURES.json
  module_a/
    __init__.py        ← 接口骨架 + BEHAVIOR 断言
    types.py           ← @DATA 编译结果
    errors.py          ← 错误类（来自 @CROSSCUT）
    test_module_a.py   ← 契约测试骨架
  module_b/
    __init__.py
    types.py
    test_module_b.py
  externals/
    database.py        ← @EXTERNAL 接口桩
  shared/
    errors.py          ← 全局错误类
    logger.py          ← 日志
    config.py          ← 配置
```

## AI 的任务变化

```
当前 Phase 2:
  1. 定位 → 确认依赖全 [done]
  2. 加载 → 读取蓝图 + 依赖签名
  3. 实现 → 从零写代码（100% AI 生成）
  4. 验证 → 逐行对照
  5. 标记 → [done]

编译器增强后的 Phase 2:
  1. 定位 → 确认依赖全 [done]
  2. 编译 → 自动生成代码骨架
  3. 填充 → AI 只填充 TODO 标记的业务逻辑（~30%）
  4. 验证 → 骨架中的 BEHAVIOR 断言自动生效
  5. 标记 → [done]
```

## 语言适配

```
Python:
  数据类 → @dataclass
  断言 → assert / pytest.raises
  类型 → typing 模块
  测试 → pytest

TypeScript:
  数据类 → interface / type
  断言 → console.assert / if...throw
  类型 → 原生类型系统
  测试 → jest / vitest

Go:
  数据类 → struct
  断言 → if...panic / errors.Is
  类型 → 原生类型系统
  测试 → testing

Rust:
  数据类 → struct + derive
  断言 → assert! / assert_eq!
  类型 → 原生类型系统
  测试 → #[test]

Java:
  数据类 → record (Java 16+) / Lombok @Data
  断言 → assert / Preconditions
  类型 → 原生类型系统
  测试 → JUnit 5
```

## 与其他特性的关系

```
蓝图编译器 + 蓝图模式库:
  模式库生成蓝图骨架 → 编译器从蓝图生成代码骨架
  两级骨架：架构级（模式库）+ 代码级（编译器）

蓝图编译器 + 蓝图属性测试:
  编译器生成的契约测试骨架 → 属性测试框架自动填充随机输入
  骨架定义"测什么" → 属性测试决定"用什么输入测"

蓝图编译器 + 蓝图漂移检测:
  SIGNATURES.json 由 scripts/validate_blueprint.py --signatures 从蓝图生成
  （确定性生成，蓝图是唯一真相源）
```
