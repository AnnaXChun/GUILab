# 失败案例

synthetic 行是明确注入的单测场景。真实模型/pair 样本 N=0。2026-10-16 的真实基础设施失败单列于文末，不当作 Agent 任务错误。

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
