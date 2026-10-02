# edge-guide：本地小模型极简守则

> 你（执行模型）正在受限模式工作：不读 SKILL.md、不读其他 references。
> 你的全部流程由 scripts/work.py 驱动。只记住下面 11 条：

1. 每轮只做 `work.py next` 给你的**一个工作包**，不要提前想后面的模块
2. 只填充工作包里的 TODO 函数体；**函数签名、dataclass 字段、文件路径一律不改**
3. 实现只调用工作包「依赖签名」里列出的函数；需要的 import 自己加在文件顶部
4. 实现必须满足函数 docstring 里的 pre/post/error/side-effect——那是验收标准
5. 不确定怎么实现时，选最简单的能满足 post 的写法；不要发明蓝图上没有的功能
6. 改完文件后，把 BLUEPRINT.md 中本模块状态改为 [done]（@PROGRESS 和 @MODULE 两处）
7. 然后运行工作包给出的 check 命令，**以命令输出为准**：
   - 输出说"尚未完成"→ 继续运行 next
   - 输出列出错误 → 只修错误指的东西，别的大改一律不做
   - [FAIL] 的 @VERIFY → 修对应 @FLOW 的实现，直到 [PASS]
8. 看到骨架未生成的提示 → 先运行它给出的 scaffold 命令
9. 不要重构、不要"顺手优化"、不要改测试桩和 @VERIFY 命令
10. 上下文不够时：重新运行 `work.py next` —— 工作包会重新给你当前需要的一切，
    不依赖你之前"记得"的任何东西
11. check/工作包里给出的命令**原样运行**（含完整路径）；@CHANGE 新条目格式
    模仿 BLUEPRINT.md 里已有的条目；蓝图语义有歧义时选最简单的解释并记 @CHANGE

## 一页命令卡

```
python scripts/work.py next <BLUEPRINT.md>      # 我现在该做什么（含全部所需上下文）
python scripts/work.py check <BLUEPRINT.md>     # 我做完了吗（validator+verify，输出下一步）
python scripts/scaffold.py <BLUEPRINT.md> --out src   # 生成/重新生成骨架
```
