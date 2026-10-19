# Mac 官方 VM 软件模拟验证

2026-10-16，用户要求“开始验证”后执行。用途是验证本机能否加载官方 VM、取得真实截图与执行响应；不是模型实验，不计 CADWorld 成绩。

> 后续更新：2026-10-19 原生 ARM QEMU 已启动同一官方 VM 并通过 FreeCADCmd 原生文件检查，见 [最新报告](MAC_NATIVE_QEMU_SMOKE.md)。以下保留 2026-10-16 Docker 路线的历史失败，不代表所有无 KVM 路线均不可行。

## 当前结论

**本机这条 Docker/TCG 路径本轮为 NO-GO，`BLOCKED_BY_ENV`。官方模型 baseline 尚未跑通。** 第三次启动等待 900.001 秒，未取得 `/screenshot`；另一次只读 `/platform` 也超时。因此 `/execute` 派发为 0、FreeCAD 原生保存重开为 `NOT_RUN`、模型任务及真实 pair 均为 0。

已通过独立 ARM Linux、官方 amd64 容器的 QEMU 执行、TCG BIOS 指令执行、官方 qcow2 完整 SHA256 校验。第三次启动已进入 64 位内核态并显示 Ubuntu 启动动画，随后出现等待磁盘 UUID 超时、`/boot/efi` 挂载依赖失败、`systemd-binfmt.service` 失败及 Plymouth backtrace。没有确认这些 guest 故障的完整根因，不能仅据此断言所有 Mac 软件模拟路径都不可用。

小型版本化证据见 [`evidence/mac_vm_20261016/`](evidence/mac_vm_20261016/)，机器可读结论见 [`summary.json`](evidence/mac_vm_20261016/summary.json)。完整原始数据留在本机 `results/mac_probe_20261016/`。本轮最终代码对应的项目单测为 **72 passed in 6.78s**；可信 native 宏仅通过语法编译，没有执行。

## 环境与资产

| 项目 | 实测值 |
| --- | --- |
| 宿主 | Apple M5 Pro，macOS，ARM64，48 GiB RAM |
| 新建隔离环境 | Colima `cadworld-probe`，aarch64，8 vCPU，16 GiB RAM，128 GiB data disk |
| 原 Docker context | `colima-scientific-harness`；未切换默认 context |
| x86 KVM | 不存在；全程 `KVM=N` |
| 官方容器 | `happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9`，linux/amd64 |
| QEMU | Debian 9.1.0，通过 binfmt 的 QEMU user translation 执行，再以 TCG 模拟 x86 guest |
| 官方 VM | `https://huggingface.co/Zihan1004/CADWorld/resolve/main/vm_data/FreeCAD-Ubuntu.qcow2?download=true` |
| 下载文件大小 | 28,310,503,424 bytes |
| 实际完整 SHA256 | `edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12`，与 HF `x-linked-etag` 一致 |
| 镜像结构 | qcow2，50 GiB virtual size，`dirty-flag=false`、`corrupt=false`；这些 header 字段不等于完整文件系统验收 |
| VM 启动参数 | 2 vCPU，8 GiB RAM，`CPU_MODEL=qemu64`，TCG，底盘只读挂载 `/System.qcow2`，每个容器独立 `/boot.qcow2` 写入层 |

下载先使用 pinned 官方下载脚本，约 450 秒只取得 2.2 GB，主动停止并保留前缀。随后同源 aria2 8 连接、16 连接续传；全部字节完成后，用宿主 Python hashlib 做完整校验，耗时 13.922 秒。aria2 自身较慢的校验在独立校验通过后停止，故 aria2 的 exit 7 是主动中断，不能用作最终资产判定；最终判定见 `asset_verified.json`。不公开临时签名 CDN URL。

## 实际启动与失败

| 尝试 | 结果与证据 |
| --- | --- |
| `boot_001`，默认 entrypoint | 立即失败：`tini -s` 报 `PR_SET_CHILD_SUBREAPER is unavailable`；未进入 guest 启动 |
| `boot_002`，直接执行原 `/run/entry.sh` | QEMU 运行；legacy iptables 初始化失败，nft 查询也返回不支持；自动 user fallback 仅转发 22/3389，不可能连接 5000。保存 UEFI 截图后主动停止，未耗尽 900 秒 |
| `boot_003`，直接入口及显式 user 网络 | `NETWORK=user`、`USER_PORTS=5000,9222,8080`；QEMU argv 已含 5000 转发。900.001 秒后 `/screenshot` 未就绪，`BLOCKED_BY_ENV`，探针停止容器 |

仅在独立 Colima guest 加载了 `ip_tables`、`iptable_nat`；模块存在后，amd64 容器里的 iptables 查询仍失败。没有修改原 profile，也未通过禁用研究 gate 冒充参考环境通过。user 网络配置直接来自同一镜像的 `/run/network.sh`，没有修改镜像文件或 upstream tracked 文件。

guest 故障截图为 [`boot_003/boot_final.png`](evidence/mac_vm_20261016/boot_003/boot_final.png)，可读到 `/dev/disk/by-uuid/7479-9B70` 的等待超时与 `/boot/efi` 依赖失败。CPU 寄存器采样只证明已进入 64 位内核上下文，不等于完整 Ubuntu 桌面或 FreeCAD 可用。

## 可复跑命令

新环境与显式资产准备已完成；不会由探针自动下载镜像或启动模型。复跑应先启动独立 profile，检查磁盘空间，手动准备官方容器和 qcow2，并使用新的 output、container name。

```bash
colima start --profile cadworld-probe --activate=false \
  --arch aarch64 --vm-type vz --cpu 8 --memory 16 --disk 128 \
  --runtime docker --ssh-config=false \
  --mount /Users/bytedance/Desktop/Own/CUA/cad-cf-hybrid:w

docker --context colima-cadworld-probe pull --platform linux/amd64 \
  happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9

# 本轮实际先执行的官方下载命令；后续续传参数见机器可读证据。
.venv/bin/python -u vendor/CADWORLD/scripts/python/download_vm_image.py \
  --retries 1 --timeout 45

ENABLE_PAID_RUNS=0 .venv/bin/python -u scripts/probe_mac_vm.py \
  --context colima-cadworld-probe \
  --vm vendor/CADWORLD/vm_data/FreeCAD-Ubuntu.qcow2 \
  --expected-sha256 edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12 \
  --output results/mac_probe_20261016/boot_003 \
  --name actc-mac-infra-probe-20261016-003 \
  --boot-seconds 900 --direct-entry --user-network --keep-on-success

.venv/bin/python -m pytest -q
```

首次创建 profile、安装 aria2、拉取 Docker 镜像、下载 VM 均是本轮实际发生的环境操作。完整原始日志留在 ignored `results/mac_probe_20261016/`。版本化证据只收录必要元数据、脱敏命令、失败日志和截图，不提交 qcow2、模型或密钥。

`--keep-on-success` 仅供紧接着进行无模型检查；成功后须显式 stop 本轮容器并停止本轮 profile。失败路径会停止它自己创建的容器；重名时拒绝启动或清理已有容器。本轮三个容器均已停止，后续清理只操作与 manifest 中 ID、label 一致的本轮资源；已移除三个本轮容器并停止独立 profile，保留官方 qcow2；原 context 与两个健康容器不变。清理证据见 [`cleanup.json`](evidence/mac_vm_20261016/cleanup.json)。

## 研究边界与下一步

本轮真实模型任务为 0、真实 counterfactual pairs 为 0、模型调用为 0；未读取官方隐藏规则、参考工程或评分产物。2 vCPU、TCG、直接入口和 user 网络均与参考配置不同，不能据此比较 GUI/API 的硬件效率。正式 P0–P3 gate 不变。

本轮未达到运行 `trusted_native_probe.FCMacro` 的前提，FreeCAD 版本、原生文件结构、GUI/API 状态同步均未取得真实证据。宏仅用于后续检查 Body/Sketch/Pad、修改 Length、保存重开和 GUI 显示；它生成的文件不属于 agent 任务产物，不能算 baseline success。

下一步 **GO：远程 x86_64 Linux/KVM 基础设施核验**，先对同一资产独立计算 SHA，再打通 pinned `DesktopEnv.reset → observe → close`。当前 **NO-GO：直接开始本机模型 baseline、paired intervention 或 pilot**。VM 与 endpoint 条件就绪后，按 `docs/NEXT_BASELINE_RUN.md` 已授权范围执行少量官方 GUI/CLI baseline，不重复申请同范围许可。
