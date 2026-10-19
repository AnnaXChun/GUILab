# 失败案例

synthetic 行是明确注入的单测场景。早期报告的模型/pair 样本为 0；最新真实模型失败见末节，真实 pair 仍为 0。基础设施失败单列，不当作 Agent 任务错误。

| 样本 | 观察结果 | Trace |
| --- | --- | --- |
| case_01_gui_target_miss | GUI 未满足公开目标；target_progress=0，标签 api | `results/final_artifacts/case_01_gui_target_miss/trajectory.jsonl` |
| case_02_different_s0 | InvalidPair: different_S0: canonical state differs | `results/final_artifacts/case_02_different_s0/trajectory.jsonl` |
| case_03_stale_screenshot | InvalidPair: different_S0: screenshot differs | `results/final_artifacts/case_03_stale_screenshot/trajectory.jsonl` |
| case_04_execution_timeout | ExecutionUncertain: injected /execute timeout: no replay | `results/final_artifacts/case_04_execution_timeout/trajectory.jsonl` |
| case_05_api_preservation | API 改动非目标对象；preservation=0，标签 gui | `results/final_artifacts/case_05_api_preservation/trajectory.jsonl` |
| case_06_unknown_target | unknown public target; no directional supervision | `results/final_artifacts/case_06_unknown_target/trajectory.jsonl` |
| case_07_unknown_validity | quality evidence unavailable | `results/final_artifacts/case_07_unknown_validity/trajectory.jsonl` |
| case_08_invalid_native | API 原生重算失败；validity=0，保留失败证据 | `results/final_artifacts/case_08_invalid_native/trajectory.jsonl` |

## Mac 无模型基础设施失败

| 尝试 | 实测失败与处置 | 证据 |
| --- | --- | --- |
| `boot_001` | 官方容器默认 `tini -s` 在 amd64 user translation 下报 `PR_SET_CHILD_SUBREAPER is unavailable`，立即退出；没有 guest 动作或模型请求 | `evidence/mac_vm_20261016/boot_001/` |
| `boot_002` | 直接原入口后 QEMU 运行；iptables 初始化失败导致自动退回 user 网络，未转发 controller 5000。捕获 UEFI 截图后主动停止该独立容器，用新 overlay 显式配置 user forwarding | `evidence/mac_vm_20261016/boot_002/` |
| `boot_003` | 显式 user forwarding 后进入内核与 Ubuntu 动画，但 guest 出现设备 UUID 等待超时、`/boot/efi` 挂载依赖失败；900.001 秒后 controller 未就绪。`/platform` 也超时，未发 `/execute`；根因未完全确定 | `evidence/mac_vm_20261016/boot_003/` |

启动时限与最终结果见 [Mac VM 验证](MAC_VM_SMOKE.md)。这些失败均不产生 preference 标签，不计入官方 GUI-only、CLI 或 Hybrid 的 task success 分母。

## 原生 QEMU 的 GUI 宏失败

2026-10-19 用 ARM 原生 QEMU 启动同一官方 VM，三个独立 clone 的 controller 均成功；以下失败保留，不能被第三次 headless 成功覆盖。

| 尝试 | 观察与处置 | 证据 |
| --- | --- | --- |
| native `boot_001` | GUI 可见；可信宏 300 秒无 native JSON，终态未知，不重发、停机隔离。日志有 Wayland/DBus 警告，根因未确定 | `evidence/native_qemu_20261019/boot_001/` |
| native `boot_002` | 私有 overlay 改为 GDM X11 并 reset；宏仍超时，DBus portal NoReply。连续两路截图相同，未证实显示通道错误；同样不重发 | `evidence/native_qemu_20261019/boot_002/` |
| native `boot_002` 只读诊断 | VM 停止后一次 `/execute` 连接失败，ledger 记 uncertain；未重发，不能作为 CAD 动作失败或宏根因 | 同目录 `execute_trace.jsonl` 的 `macro-diagnostic-once` |

第三次 `boot_003` 在新 overlay 使用 FreeCADCmd，通过保存重开和参数修改；这不代表前两次 GUI 失败已修复。三次模型调用与 task episode 均为 0。详见 [原生 QEMU 报告](MAC_NATIVE_QEMU_SMOKE.md)。

## 2026-10-19 后续 GUI 与模型运行

本节覆盖前文“真实模型样本 N=0”和“GUI 尚未有成功路径”的历史状态。全部结果与分母见 `BASELINE_RUNTIME_SMOKE.md`，pair 数仍为 0。

| 尝试 | 实际观察 | 证据与分类 |
| --- | --- | --- |
| `desktop_env_acceptance_001` | 原始 reset/action/close PASS 后，诊断发现两个 FreeCAD GUI | 基础设施验收不足；新 gate 要求 singleton，不据此启用模型 |
| `desktop_env_acceptance_002` | GUI 单实例成功，但序列化写入字面换行，主机 JSONDecodeError | 工程故障，全次 FAIL；畸形 bytes 保存为 `gui_ready.malformed.txt`，修复后 003 通过 |
| 002 停机后的只读诊断 | 一次连接拒绝，ledger uncertain；未重发 | 不算 CAD 动作失败，也不能据此归因 GUI 宏 |
| `endpoint_live_001` | GPT 图片请求 HTTP 500，usage unknown | 1 次真实生成；原 body/request ID 未采集，不能追补。用户改选 Qwen 后保留失败并记录 correction |
| `endpoint_qwen_001` | 账本尚未恢复，本地 reserve 拒绝 | 0 次模型网络生成，不算第二次 API 故障；原结果保留 |
| `baseline_gui_sketch_001` | Qwen 连续 3 次点击 `(842,737)`，欢迎页未关闭，无输出文件；官方 strict=0 | 真实 GUI-only 任务失败，API 三次成功、219 输出 tokens；不是 run_error。截图为 1920×1080，按 0..1000 映射约为 `(1617,796)`，落在 Done 按钮附近，提示坐标约定不匹配，尚未用独立合同验证 |

第一道 GUI 的坐标错误原样保留，没有在评分后修正轨迹或补原生文件。GUI 宏修复证明图形进程和可信脚本可工作，不能由此推断模型已经具备可靠 GUI 定位能力。未打开 hidden reference 为模型生成答案。

`baseline_gui_part_001` 也连续 3 次点击 `(842,737)`，strict=0、`failure_class=no_output_file`，输出 196 tokens。它复现了首题的坐标问题；两题均有完整 screenshot/traj/result/evaluation，没有 API error。两题 creation 任务都未开始实际建模，不能据此估计 CAD 几何推理能力。

`baseline_cli_sketch_001` 是独立的工程失败：pinned `CLI/run_cli.py:100` 要求 `--results-dir` 位于 `CLI/` 边界内，原包装层给出项目 results，参数解析 exit=2。该尝试未启动 VM、未发模型生成请求，不计 episode 分母。修复为先在 `vendor/CADWORLD/CLI/results/actc/<run_id>` 运行，结束后复制原始产物到项目 `results/official_cli/<run_id>`；拒绝重复 run ID，保留这次失败，用 `_002` 新目录继续。实际 pinned CLI 计划已再次通过无模型 dry-run。

CLI `_002` 最终完成 7 轮，7 个 terminal 返回码均为 1；前三类具体错误为 `PrimitivePy` 没有 `Point1`、`Part::LineSegment` 不是文档对象类型、`doc.save(path)` 不接受路径参数。后者在后几轮重复出现，没有保存文件。官方评估 strict=0、termination=turn_limit、failure_class=no_output_file；没有 API/VM 超时或 pipeline error。它是 1 个真实 episode 内的 7 个失败命令，不扩大 episode 分母。当前 3 个真实 baseline episode 全部保留；真实 pair 仍为 0。
