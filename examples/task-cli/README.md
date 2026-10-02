# task-cli 蓝图示例

本目录是**蓝图/签名示例**：BLUEPRINT.md 已通过 validate_blueprint.py 机械校验，
SIGNATURES.json 是对应的签名基线。目录不含实现代码。

从仓库根目录可运行的命令：

```bash
# 结构检查（应 0 错误 0 警告）
python scripts/validate_blueprint.py examples/task-cli/BLUEPRINT.md

# 签名基线比对（应一致 ✓）
python scripts/validate_blueprint.py examples/task-cli/BLUEPRINT.md --check-signatures
```

注意：`@VERIFY` 段与 `--verify` / `--gate phase3` 需要实现代码才会通过，
本目录**预期全部 FAIL**（找不到 src/main.py）。要跑通完整链路：

```bash
python scripts/scaffold.py examples/task-cli/BLUEPRINT.md --out examples/task-cli/src
# 然后填充 src/ 中各 NotImplementedError，逐模块 work.py next → check
```

完整跑通的样例项目见 `test-project/url-shortener/`（蓝图/摘要/签名/实现齐备）。
