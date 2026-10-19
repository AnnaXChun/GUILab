# Mac 原生 QEMU 无 KVM 验证

2026-10-19，用户确认无法提供 KVM 后，继续此前“开始验证”授权下的限时、无模型检查。使用同一官方 x86 VM，改为 ARM 宿主原生 QEMU/TCG，避开 amd64 容器内再做软件转译的路径。

**无 KVM 可以启动本项目的官方 VM，并完成 FreeCAD 原生参数化文件保存重开。baseline 尚未复现。** 三个独立 overlay 中，前两次 GUI 宏超时，第三次 FreeCADCmd 通过。没有运行模型、官方任务、评分或真实 pair。

## 结果与边界

| 检查 | 实测结果 |
| --- | --- |
| 官方 x86 Ubuntu VM | 无 KVM 启动成功；guest `Linux-6.8.0-110-generic-x86_64-with-glibc2.39` |
| controller 与 `/execute` | 三次均有真实 HTTP 200、环境读取和一次鼠标动作响应 |
| FreeCAD GUI | 首次 QMP 截图可见 FreeCAD 1.1.0 完整界面；不等于原生文档同步已通过 |
| GUI 可信宏 | 两次均在 300 秒结果轮询窗口内无 JSON；不重发，终态未知，clone 隔离停机 |
| FreeCADCmd | `/snap/freecad/2266/usr/bin/FreeCADCmd`，版本 1.1.0；第三次单次派发通过 |
| 原生 `.FCStd` | Body→Sketch→Pad，半径 5 mm，Length 10→12 mm；保存、关闭、重开两次，保留 Profile、Body Tip、2 个草图约束 |
| 几何检查 | 初始体积 785.3981633974482，最终 942.4777960769378；有效形体、1 个 solid |
| 宿主文件复核 | 下载 SHA 与 guest 一致；ZIP 校验通过，Document.xml 含 Body、Sketcher、Pad 类型 |
| GUI/API 同步、TypedWorker | 未验收；headless PASS 不作为 P1 或模型 baseline PASS |
| 模型调用 / 官方 episode / real pair | 0 / 0 / 0；strict=null，无 preference 数据 |
| 单测 | `77 passed in 7.52s`，无 VM/模型调用的项目测试 |

第三次原生文件的 SHA256 为 `bba102bed921deccbb43bb1e365743134a0ef452f6c0b50945d04f1431b0dd8c`，本机保存在 `results/mac_native_probe_20261019/boot_003/trusted_infrastructure.FCStd`。这是固定可信脚本生成的环境探针，`agent_generated=false`、`benchmark_success=null`，不是 agent 答案。Git 只归档哈希、结构清单和 trace，不提交 native 文件、qcow2 或固件二进制。

## 环境与资产

| 项目 | 实测值 |
| --- | --- |
| 宿主 | Apple M5 Pro，macOS ARM64，48 GiB RAM |
| QEMU | Homebrew 11.1.2；`qemu-system-x86_64` 与 `qemu-img` 都是 Mach-O arm64 |
| 运行方式 | 宿主原生进程、TCG，2 vCPU、8192 MiB RAM，loopback VNC、user 网络转发 controller |
| 官方 upstream | `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`；tracked 文件未改 |
| 官方 VM | 28,310,503,424 bytes；完整 SHA256 `edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12` |
| 固件来源 | 同一官方容器 digest `happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9` 的 `/usr/share/OVMF/edk2-x86_64-code.fd` |
| 固件哈希 | 3,653,632 bytes；SHA256 `2df617a6fd1bae41ec7c0e3bceca96c928a5a88d8dc198468d34733393ab2792` |

原 VM 已在前次显式下载，本轮未重新下载。固件用停止状态的提取容器复制，未执行该容器。为提取固件短暂启动独立 `cadworld-probe` Colima profile，随后停止；原 `scientific-harness` profile 和默认 Docker context 未切换。VM base 只作 backing file，启动前逐次全量 hash，全部结束后再次 hash 相同。

## 三次实际尝试

| 尝试 | 配置与 controller 用时 | 结果 |
| --- | --- | --- |
| `boot_001` | 无 X11 改动；119.566 秒 | transport 成功，GUI 可见；GUI 宏 300 秒未返回结果，`native_status=BLOCKED_BY_ENV` |
| `boot_002` | 私有 GDM X11 配置，sync 后 QMP reset 一次；两次 OS boot 合计 281.927 秒 | transport 成功；GUI 宏仍 300 秒无结果；X11 设置未证实能解决此问题 |
| `boot_003` | 全新 overlay，无 GDM 改动；FreeCADCmd；119.615 秒 | `PASS_NATIVE_HEADLESS_ONLY`；进入可信几何脚本后 5.966 秒完成；含 runtime 启动与结果轮询约 20 多秒 |

每次都使用新 qcow2 overlay、新工作目录与单次派发账本。GUI 超时后没有重试旧宏，也没有在同一个不确定 clone 中改换执行路径。第三次不是对前两次变更的重放。

`boot_001/result.json` 的历史状态名 `PASS_INFRASTRUCTURE_ONLY` 范围过宽：只表示 controller transport，不表示 GUI 原生宏或 baseline 通过。原始 JSON 保留，后续脚本改为更明确的 `PASS_CONTROLLER_TRANSPORT_ONLY` / `PASS_NATIVE_HEADLESS_ONLY`。

早期 controller 黑屏与较晚 QMP FreeCAD 界面来自不同时间，不能证明显示通道不一致。第二次又连续抓取两路画面，controller 请求耗时 14.421 秒、QMP 跟进 0.451 秒；二者显示相同 GNOME 桌面和中央 FreeCAD splash，主要差别为光标。启动时序可能解释早期现象，但完整根因未确定。GUI 宏的 DBus portal `NoReply` 与首轮 Wayland 警告是日志观察，不能据此断言唯一根因。

第二次 ledger 还保留一条 VM 停止后发出的只读 `macro-diagnostic-once`，连接失败记为 `uncertain`；未重发。它不是 CAD 变更，也不能作为宏执行失败原因的证据。

## 实际命令

```bash
HOMEBREW_NO_AUTO_UPDATE=1 brew install qemu
file /opt/homebrew/bin/qemu-system-x86_64 /opt/homebrew/bin/qemu-img
qemu-system-x86_64 --version
.venv/bin/python -m pytest -q tests/test_native_qemu_probe.py
.venv/bin/python -m pytest -q

ENABLE_PAID_RUNS=0 .venv/bin/python -u scripts/probe_native_qemu.py \
  --vm vendor/CADWORLD/vm_data/FreeCAD-Ubuntu.qcow2 \
  --expected-sha256 edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12 \
  --firmware results/mac_native_probe_20261019/official_uefi.rom \
  --firmware-sha256 2df617a6fd1bae41ec7c0e3bceca96c928a5a88d8dc198468d34733393ab2792 \
  --output results/mac_native_probe_20261019/boot_003 \
  --boot-seconds 600 --port 15002 --vnc-port 15903 \
  --native --native-mode cmd
```

第三次 exit=0；前两次 GUI 宏探针 exit=1。前两次实际 probe 源码已各自归档并与 result 中的 SHA 对齐，QEMU 完整 argv 见各次 `launch_command.json`，固件提取的实际命令见 `firmware_commands.json`。以上 output 已存在，复跑必须用新目录和未占用端口。

一次早期定向 pytest 命令包含不存在的 `tests/test_mac_vm_probe.py`，exit=4、未运行测试；随后改正，定向 5 项和完整 77 项通过。一次归档工具误用宿主 Python 缺 `requests`，改用项目 venv 完成归档；这两项均未派发 VM 变更。

## 归档、隔离与清理

[机器可读结论](evidence/native_qemu_20261019/summary.json)、[证据索引](evidence/native_qemu_20261019/INDEX.json)、[清理与 base 复核](evidence/native_qemu_20261019/cleanup.json) 收录本轮结果。各次目录包含 readiness JSONL、脱敏 execute JSONL、native 结果、必要截图和当次 probe 源码。完整本地原始记录位于 ignored `results/mac_native_probe_20261019/`。

公开 trace 的私有 X11 配置 payload 已脱敏并保留 SHA；原始 SQLite 不上传。GDM 修改仅发生在第二次私有 overlay，公开 VM 提权流程只供可信环境设置，不传给模型或 verifier。第三次 headless 无需该改动。

代码和文档的 `git diff --cached --check`（排除原始证据）通过。包含证据时，FreeCAD 原始 stdout 的进度控制字符触发 1 处 trailing-whitespace 提示；保留原始字节以便哈希追溯，没有把该全范围检查写作无警告。

三个 QEMU 进程均已退出，临时 QMP socket 已清理；保留 base 和隔离的 overlay 供失败追溯。没有隐藏评分输入、参考工程或模型 API 调用。

## 下一步 GO / NO-GO

**GO：无 KVM 路线的 runner 适配和无模型 GUI 文档同步检查。** 远程先按 [NO_KVM_RUN](../docs/NO_KVM_RUN.md) 检查现有 Docker provider 的 TCG 支持；Docker 不可用时再接原生 QEMU。当前探针尚未实现 `DesktopEnv.reset`、任务 setup、baseline 生命周期或 TypedWorker/GUI bridge 接入。还需修复完整 upstream 依赖与原始 CLI dry-run，然后才运行 [已授权的少量模型 smoke](../docs/NEXT_BASELINE_RUN.md)。

**NO-GO：宣称官方 baseline 已复现、生成 ACTC pairs、24-pair pilot 或 full-200。** `reports/stages.json` 保持不变。TCG 与参考硬件的结果分开，官方 GUI-only、CLI 与扩展 Hybrid 分开。endpoint、model ID、接口和凭证由执行模型实验的远程会话收集，本轮不请求密钥。
