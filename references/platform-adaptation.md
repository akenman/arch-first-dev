# 平台适配

> 加载条件：非 DeepSeek TUI 环境，或工具调用失败需要查表时

## 平台适配

本 skill 使用行为描述而非具体工具名，跨平台通用。AI 执行时根据当前环境选择对应工具：

| 行为 | DeepSeek TUI | Claude Code | Trae CN | Cursor | Codex CLI |
|------|-------------|-------------|---------|--------|-----------|
| 列出目录内容 | list_dir | LS / Bash ls | LS | list_dir | Bash ls |
| 搜索代码 | grep_files | Grep | Grep | search | Grep |
| 读取文件 | read_file | Read | Read | read_file | Read |
| 写入/编辑文件 | write_file / edit_file | Write / Edit | Write / SearchReplace | edit_file | Write |
| 运行命令 | exec_shell | Bash | RunCommand | terminal | Bash |
| 跟踪进度 | checklist_write | TodoWrite | TodoWrite | —（跳过） | —（跳过） |
| 规划步骤 | update_plan | —（跳过） | —（跳过） | —（跳过） | —（跳过） |
| 启动子任务 | agent_spawn | Task | Task | —（转串行） | —（转串行） |
| 压缩上下文 | /compact | /compact | —（释放模块代码替代） | /compact | —（释放模块代码替代） |

工具不可用时回退策略：
- 进度/计划工具不可用 → 用代码注释或文件记录替代
- 子任务不可用 → 串行填充，同层模块依次实现
- 压缩上下文不可用 → 每个 Phase 切换时写 CHECKPOINT.md，建议用户开新会话恢复
- 浏览器/截图验证不可用 → UI 项目 Phase 3 ⑦ 降级为：dev server 启动无报错 +
  首页 HTTP 200 + 关键路由返回非 5xx；交互与像素验证转人工