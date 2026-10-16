# 本地 Linux 可行性

2026-10-16，只读核查，未安装新 VM、修改现有 Colima profile、拉取容器镜像或下载官方 qcow2。

本机为 Apple M5 Pro、macOS 26.5.1、ARM64、48 GiB 内存。已经有一台运行中的 Colima Linux VM：Ubuntu 24.04.4 LTS、aarch64、4 vCPU、12 GiB 内存、80 GiB 虚拟磁盘。guest 内实测 `/dev/kvm` 不存在。

需要补充先前的环境判断：pinned upstream 并非完全禁止无 KVM 运行。`desktop_env/providers/docker/provider.py:172,274` 和 `DOCKER_GUIDELINE.md` 明确支持 `CADWORLD_ENABLE_KVM=false`，会设置 `KVM=N`。因此本地软件模拟可以作为待验证的功能 smoke 路径，不能直接断言 VM 完全无法启动。

本次 registry metadata 核查显示，上游使用的 `happysixd/osworld-docker:latest` 为 linux/amd64，观察到的 digest 是 `sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9`。这里只读取 manifest，没有拉取镜像。

Mac 上再创建 ARM Linux，仍无法给官方 x86_64 guest 提供同架构 KVM 加速。Lima 2.2.0 的配置说明支持 M3 及以上芯片的 ARM 嵌套虚拟化，但它不提供跨架构 x86 KVM。容器 amd64 兼容和 FreeCAD 系统 VM 的软件模拟均需另外实测；当前没有启动耗时、交互延迟或成功结果。

结论：Linux 本身已经可用，无需为“有 Linux”重复安装。若继续本地路线，应使用独立 CADWorld profile 做明确标注的软件模拟试验，先验证容器兼容，再显式准备官方镜像，最后做限时、无模型的 VM 连接测试。现有其他项目的 profile 不应被改作 CADWorld 环境。

SPEC 的 Linux x86_64 + KVM 参考协议仍为 NO-GO；软件模拟结果须单列环境差异与时间成本，不用于等硬件效率比较。正式 baseline 推荐可访问 `/dev/kvm` 的 x86_64 Linux 主机。真实任务与 paid model calls 仍为 0。
