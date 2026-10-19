# 本机 Linux 与 CADWorld VM 可行性

2026-10-19 实测：**Mac 可以在无 KVM 条件下启动官方 x86 VM，并完成 FreeCADCmd 参数化文件保存重开。** 最新证据、命令和失败见 [原生 QEMU 检查](MAC_NATIVE_QEMU_SMOKE.md)。本结论取代“尚未验证原生 ARM QEMU”的旧状态，baseline 尚未复现。

本机 Apple M5 Pro、ARM64、48 GiB RAM。使用 Homebrew ARM 原生 QEMU 11.1.2 的 TCG 模拟同一官方 x86 qcow2，2 vCPU、8 GiB guest RAM、user 网络；不依赖 Docker 或 KVM 启动该 guest。两次无 GDM 修改的 controller 启动约 120 秒。首次看到 FreeCAD 1.1.0 完整 GUI，第三次 FreeCADCmd 创建 Sketch→Pad、保存重开两次并修改长度成功。

前两次 GUI 宏均在 300 秒内无结果，不重试。第二次在独立 overlay 强制 GDM X11 并 reset，宏仍超时；该改动未证实必要。连续 controller/QMP 截图显示相同桌面，不能以不同时间的早期黑屏推断显示通道不一致。正式 GUI 操作、文档同步和 GUI bridge 仍需验证。

2026-10-16 的 Docker 路线使用 amd64 QEMU user translation 再加 TCG，900 秒没有 controller，保留于 [历史 Mac VM 报告](MAC_VM_SMOKE.md)。原生 ARM QEMU 避开了外层转译，当前已突破启动阻塞；没有证据证明历史每一项故障的唯一原因。

Linux 容器可以运行 FreeCAD，KVM 是 VM 加速条件。用户无法提供 KVM 时，先按 [无 KVM 路线](../docs/NO_KVM_RUN.md) 测试 Docker provider 的软件模拟；没有 Docker 权限则适配原生 QEMU。仍需检查内存、磁盘、TCG/JIT、桌面与端口条件。安装 VMware 或 ARM Linux 不会带来 x86 硬件加速，本轮无需安装。

全部本轮 QEMU 已退出，base SHA 启动前后相同，独立 Colima profile 已停止，原 profile 和默认 context 未变。TCG/X11 是探索环境差异，参考 gate 不直接放宽。下一步 GO 是 runner 生命周期适配与 GUI 同步检查；模型 baseline、真实 pair 和 pilot 仍为 NO-GO。
