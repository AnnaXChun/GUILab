# 复现状态

2026-10-19 更新：用户无法提供 KVM。本机 ARM 原生 QEMU/TCG 已启动官方 x86 VM、controller 和 FreeCAD GUI；第三次 FreeCADCmd 通过原生参数化保存重开。真实 baseline 阶段仍未验收。最新证据见 [原生 QEMU 检查](MAC_NATIVE_QEMU_SMOKE.md)，早期 Docker 失败见 [Mac VM 验证](MAC_VM_SMOKE.md)。

| 检查项 | 状态 | 证据与影响 |
| --- | --- | --- |
| pinned upstream | PASS | `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`；原始 tracked 文件未修改 |
| 本项目依赖 | PASS | Python 3.12.14；`uv sync --frozen` |
| upstream 全量依赖 | BLOCKED_BY_ENV | 本机 Darwin arm64；只执行 `uv sync --frozen --dry-run`，预览 405 包，未把预览算作安装完成 |
| upstream CLI unittest | PASS | 7 tests；原始 `CLI.test_terminal_agent`，使用本项目轻量环境 |
| upstream CLI dry-run | FAIL | 原始脚本 exit 1：`ModuleNotFoundError: No module named 'dotenv'`；依赖阻塞，未经过 VM/API |
| 本项目 deterministic tests | PASS | 本轮 `77 passed in 7.52s`；新增 hash/端口保护、QMP framing、trace 脱敏与 headless 超时不重发检查 |
| mock pair campaign | PASS | 9 synthetic 场景；完整 JSONL、冻结契约、状态差异与失败记录见 `../results/final_artifacts/`，版本化副本在 `evidence/mock_smoke/` |
| 官方 VM 与 controller（TCG） | PASS_CONTROLLER_TRANSPORT_ONLY | ARM 原生 QEMU 11.1.2；无 KVM；首次 119.566 秒，第三次 119.615 秒，HTTP/execute/鼠标响应成功 |
| FreeCAD 原生文件（可信 headless） | PASS_NATIVE_HEADLESS_ONLY | FreeCAD 1.1.0；Sketch→Pad，Length 10→12，保存关闭重开两次，宿主 ZIP/结构/SHA 校验通过；不是 agent 产物 |
| 参考 Linux x86_64/KVM 环境 | BLOCKED_BY_ENV | 用户确认不可提供 KVM；转为独立 TCG 探索环境验收，参考 gate 不手改 PASS |
| 模型服务 | BLOCKED_BY_CREDENTIALS | 本轮未收集 endpoint/model/key、未读取 `.env`、未请求模型；由远程模型实验会话收集 |
| 正式 GUI/API smoke 与模型 baseline | BLOCKED_BY_ENV | 原生 QEMU 尚未接 baseline runner；两次 GUI 宏超时，GUI bridge/TypedWorker/同步未验收；模型任务 N=0、pair N=0 |
| 付费调用 / 24-pair pilot / full-200 | NOT_RUN_BUDGET | 实际 model calls=0，未下载模型；已显式下载官方 VM。远程首批小样本授权仍按 `docs/NEXT_BASELINE_RUN.md` 执行 |
| P4 router 训练 / P5 veRL | NOT_IMPLEMENTED | 本轮仅提供 predictor 接口与实验计划，未接训练框架 |

[上游已存在] 官方 GUI runner、CLI runner、diagnostics 保持原样。命令、exit code、耗时和原始输出保存于 `reports/commands.json`；环境清单为 `reports/preflight.json`。

[本项目新增] 协议、受限 typed tools、FreeCAD worker、GUI 主线程桥接、native/backend 接口、clone/S0 验证、单次执行账本、public-contract verifier、配对采集、单路径 router、分组 split 和离线分析已实现。本轮固定可信 FreeCADCmd 脚本已在原生 QEMU overlay 实测；正式 NativeBackend/TypedWorker、GUI 主线程桥和 Docker clone 路径仍待真实验证。

P0 真实模型验收为 NO-GO。P1/P2 静态测试通过；可信 headless save/reopen 已成功，但正式 worker、跨 VM 同 S0 与 GUI 同步仍为 BLOCKED_BY_ENV。P3 的 ≥3 个合法真实 smoke pairs、差异重测和 24 valid pairs 均未完成；P4 为 NO-GO。

SPEC 的“阶段未过则停止下一阶段”用于真实实验门槛；缺环境时继续完成静态代码与 mock，不把后续阶段记作真实 PASS。具体适配见 `DEVIATIONS.md`。

下一步 GO：按 `docs/NO_KVM_RUN.md` 验证远程 TCG。优先复用 upstream Docker provider 的 `CADWORLD_ENABLE_KVM=false`；Docker 不可用时适配原生 QEMU 生命周期。完成无模型 reset/action/close、GUI 文档同步、upstream 依赖与原始 CLI dry-run，再按既有 endpoint 与小批预算执行模型 smoke。NO-GO：当前声称 baseline 复现、启动真实 pairs、24-pair pilot、full-200 或训练。`reports/stages.json` 保持不变。
