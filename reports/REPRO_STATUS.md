# 复现状态

2026-10-15。本轮交付 P0–P3 的静态实现、mock 验证和实验入口。真实阶段验收尚未通过。

| 检查项 | 状态 | 证据与影响 |
| --- | --- | --- |
| pinned upstream | PASS | `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`；原始 tracked 文件未修改 |
| 本项目依赖 | PASS | Python 3.12.14；`uv sync --frozen` |
| upstream 全量依赖 | BLOCKED_BY_ENV | 本机 Darwin arm64；只执行 `uv sync --frozen --dry-run`，预览 405 包，未把预览算作安装完成 |
| upstream CLI unittest | PASS | 7 tests；原始 `CLI.test_terminal_agent`，使用本项目轻量环境 |
| upstream CLI dry-run | FAIL | 原始脚本 exit 1：`ModuleNotFoundError: No module named 'dotenv'`；依赖阻塞，未经过 VM/API |
| 本项目 deterministic tests | PASS | 70 tests；命令和输出见 `commands.json` |
| mock pair campaign | PASS | 9 synthetic 场景；完整 JSONL、冻结契约、状态差异与失败记录见 `../results/final_artifacts/` |
| Linux x86_64 / KVM / QEMU / VM | BLOCKED_BY_ENV | Darwin arm64，无 `/dev/kvm`、QEMU 或 qcow2；Docker daemon 可访问 |
| 模型凭证 | BLOCKED_BY_CREDENTIALS | 当前进程未检测到支持的 provider 密钥；未读取 `.env`，未请求模型 |
| 真实 GUI/API smoke | BLOCKED_BY_ENV | 实际任务数 N=0，真实 pair 数 N=0，FreeCAD 版本及 VM SHA 均为 null |
| 付费调用 / 24-pair pilot / full-200 | NOT_RUN_BUDGET | `ENABLE_PAID_RUNS=0`；实际 model calls=0，未下载模型或 VM |
| P4 router 训练 / P5 veRL | NOT_IMPLEMENTED | 本轮仅提供 predictor 接口与实验计划，未接训练框架 |

[上游已存在] 官方 GUI runner、CLI runner、diagnostics 保持原样。命令、exit code、耗时和原始输出保存于 `reports/commands.json`；环境清单为 `reports/preflight.json`。

[本项目新增] 协议、受限 typed tools、FreeCAD worker、GUI 主线程桥接、native/backend 接口、clone/S0 验证、单次执行账本、public-contract verifier、配对采集、单路径 router、分组 split 和离线分析已实现。原生 FreeCAD、Qt、Docker overlay 路径只做静态编译和接口测试，尚未得到真实运行验证。

P0 真实验收为 NO-GO。P1/P2 静态测试通过，真实 save/reopen、跨 VM clone 与同步仍为 BLOCKED_BY_ENV。P3 的 ≥3 个合法真实 smoke pairs、差异重测和 24 valid pairs 均未完成；P4 为 NO-GO。

SPEC 的“阶段未过则停止下一阶段”用于真实实验门槛；缺环境时继续完成静态代码与 mock，不把后续阶段记作真实 PASS。具体适配见 `DEVIATIONS.md`。

下一步：迁移到 Ubuntu x86_64 + KVM，执行完整 upstream sync 和原始 CLI dry-run；显式取得镜像并记录 SHA；配置实际模型及额度边界；先跑 2 题、3-step 官方 GUI 连接检查。之后验证一个原生工程的 GUI/API 保存重开与隔离恢复，再尝试最多 3 个真实 pairs。24-pair pilot 需要额外明确授权。
