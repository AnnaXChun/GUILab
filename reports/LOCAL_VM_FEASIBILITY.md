# 本机 Linux 与 CADWorld VM 可行性

2026-10-16 已从只读核查推进到真实、无模型的 VM 软件模拟检查。完整结果、命令、截图与失败证据见 [Mac VM 验证](MAC_VM_SMOKE.md)；早期 `local_vm_preflight.json` 只表示实验前状态。

本机为 Apple M5 Pro、ARM64、48 GiB RAM。原 `scientific-harness` ARM Linux profile 保持运行，默认 Docker context 未改变。为本轮另建 `cadworld-probe`：8 vCPU、16 GiB RAM、128 GiB data disk；没有 `/dev/kvm`。

已实际执行官方 linux/amd64 容器中的 QEMU 9.1.0，并通过 TCG BIOS 指令检查。28.3 GB 官方 FreeCAD qcow2 已下载，完整 SHA256 与 HF 内容哈希一致。该官方磁盘已在 TCG 中进入 64 位内核态并显示 Ubuntu 启动动画，不能再把“Mac 只能做静态检查”当作硬件事实。

完整桌面与 controller 本轮未通过验收，900.001 秒后状态为 `BLOCKED_BY_ENV`。默认 `tini -s` 入口在 QEMU user translation 下失败；直接原入口后，容器内 iptables 初始化也失败。使用同一镜像现有的直接入口与 user 网络选项后，已启动 guest，但观察到等待磁盘 UUID 超时、`/boot/efi` 挂载依赖失败和 systemd 错误。没有执行 `/execute`、FreeCAD 保存重开或模型 baseline，不能把启动动画当作 reset/action 闭环。

Mac 的主要成本来自跨架构软件模拟与容器运行时兼容；再装一台普通 ARM Linux 不会提供 x86 KVM。本轮使用 amd64 容器的 QEMU user translation，再由其中的 TCG 执行 x86 guest，是两层软件执行。原生 ARM 版 QEMU 模拟 x86 是另一条可探索路径，本轮未验证，不能假定它已可用。

正式参考协议仍是 Linux x86_64 + KVM；本机结果不改变 P0–P3 gate，也不能用于 GUI/API 等硬件效率比较。下一步为远程可访问 KVM 的 x86_64 Linux 上验证同一资产的 `DesktopEnv.reset → observe → close`，再执行已授权的少量模型 baseline。远程仍须实测，不能保证只换主机就自动成功。
