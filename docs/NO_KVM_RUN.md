# 无 KVM 的环境执行路线

2026-10-19 用户确认远程无法提供 KVM。后续不再把“获得 KVM”作为唯一下一步。先验证原生宿主 QEMU 的 TCG 软件模拟，保留同一官方 x86 qcow2；不需要安装 VMware，也不需要在容器中再次运行 amd64 QEMU user translation。

## 先确认能够运行的宿主进程

Linux 容器可以运行 FreeCAD，也可以在运行条件允许时运行用户态 QEMU。KVM 不是安装 FreeCAD 的条件。对于本项目，先保留官方 VM，比直接重建一套 FreeCAD 桌面更容易控制环境差异。

检查架构、内存、磁盘和本机 QEMU。使用与宿主架构匹配的 `qemu-system-x86_64`、`qemu-img` 可执行文件：ARM 主机使用 ARM 版工具模拟 x86 guest，x86 主机使用 x86 版工具。不能根据二进制文件名中的 x86 判断宿主可执行架构。

```bash
uname -m
free -h
df -h .
file "$(command -v qemu-system-x86_64)"
qemu-system-x86_64 --version
qemu-img --version
```

guest 默认 2 vCPU、8 GiB RAM，宿主需要额外余量；官方镜像约 28.3 GB，base virtual size 为 50 GiB，overlay 还会增长。受限容器若无法分配内存、执行 TCG/JIT 或绑定本地端口，仍须记录具体 blocker，不能仅因存在 Linux 就宣称可运行。此探针运行时不依赖 Docker daemon、NET_ADMIN 或 `/dev/kvm`。

## 资产与显式验证

沿用 pinned 官方下载源及已记录的完整 SHA256，不自动下载模型。新取得的 qcow2 必须独立计算 SHA，不能直接复制历史值当作实测。固件也要记录来源和 SHA；本机本轮从同一官方 Docker digest 提取固件，未执行提取容器。远程如使用系统提供的其他固件，应记录该环境差异，不冒充同一固件。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_native_qemu.py \
  --vm vendor/CADWORLD/vm_data/FreeCAD-Ubuntu.qcow2 \
  --expected-sha256 edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12 \
  --firmware /path/to/prepared/official_uefi.rom \
  --firmware-sha256 2df617a6fd1bae41ec7c0e3bceca96c928a5a88d8dc198468d34733393ab2792 \
  --output results/new_native_probe --boot-seconds 600 --native --native-mode cmd
```

output 必须是新目录。脚本为原始底盘创建独立 qcow2 overlay，在 loopback 暴露 controller/VNC；完成或失败后都停止自己创建的 QEMU 进程。不得把旧失败 clone 中不确定的宏再次执行。

## 截图服务响应还不够

本机原生 QEMU 已取得 controller HTTP 200、成功 `/execute` 和鼠标动作，并看到 FreeCAD 1.1.0 GUI。前两次 GUI 宏均在 300 秒内未返回结果，未重发，clone 已停止。早期黑屏和较晚 FreeCAD 画面不是同时采集，不能据此认定显示通道不一致；第二次连续抓取 controller 与 QMP 画面显示相同桌面，主要差别为光标。仍需单独验证 GUI 操作闭环与保存重开。

`--native-mode cmd` 通过同一 snap runtime 的 FreeCADCmd 执行固定可信脚本，避免启动第二个 GUI。它的 PASS 只表示 headless 原生文件检查，不代表 TypedWorker、GUI bridge、GUI/API 同步或 baseline 已通过。

`--prepare-x11` 是显式的私有环境适配：按 pinned VM bootstrap 的既有提权流程，将该 overlay 内的 GDM `WaylandEnable` 设为 false，sync 后只重置一次，再让固定宏使用 Qt XCB。它不修改原始 qcow2、upstream tracked 文件、任务或评分规则。使用该选项必须报告环境差异；第二次采用该设置后 GUI 宏仍超时，第三次 headless 无此设置即通过，不能把它当作已证实的必要修复。

提权输入只用于该 VM 的环境准备。公开执行 trace 对这条 payload 脱敏并保留 SHA；原始 SQLite 只留在 ignored results，不能上传。模型、candidate 和 verifier 都不接触该流程或凭据。

## 模型 baseline 的下一步

本轮结果见 `reports/MAC_NATIVE_QEMU_SMOKE.md`。环境探针不是官方 task episode，不能由此修改 `reports/stages.json` 为 PASS。

先检查远程容器是否可用 Docker daemon 及其网络能力。pinned `desktop_env/providers/docker/provider.py` 已支持 `CADWORLD_ENABLE_KVM=false`，若该路线可用，优先验证原有 provider 的 `reset → observe → action → close`；不能仅凭设置该变量认定容器权限和网络也已解决。

若远程不能运行 Docker provider，可参考本机原生 QEMU 探针，下一步把生命周期、controller 地址与 reset/close 通过本项目外部适配层接入 pinned GUI/CLI runner。当前 `run_baseline.sh` 仍使用 Docker/参考环境 preflight，不能直接把上述探针命令改名当作 baseline 已接通。适配必须保留原 prompt、parser、agent action 协议与离线评分；GUI-only、CLI 和 extended Hybrid 分开报告，并标注 TCG/X11 环境。

模型接口与首批预算继续按 `docs/NEXT_BASELINE_RUN.md`：缺失的 endpoint、model ID、接口及 secret 就绪后，执行已授权的小批；不启动 24-pair pilot、full-200、训练或 veRL。新环境不是扩大 API 预算的理由。

## Gate 如何处理

现有 `preflight.py` 和 `run_baseline.sh` 仍执行参考环境 gate，不能把缺 KVM 的退出码改成 PASS。远程如采用 TCG，应增加明确的探索环境配置与独立的无模型验收记录，再让受限模型 smoke 使用该已验收环境；参考环境结果仍为未复现。不要手改 `stages.json` 解除 gate，也不要只给 baseline 启动命令加一个环境变量就声称适配完成。

## runner 接入更新

原生 provider、DesktopEnv 生命周期、endpoint/key 和共享预算账本已接入本项目适配层。上文尚未接 runner 的描述保留为前次交接状态；当前执行以 [RUN_TCG_BASELINE](RUN_TCG_BASELINE.md) 和最新报告为准。GUI 宏已有真实保存重开成功，冷启动实例竞争另有专项复验。模型实验仍需要真实 endpoint、model 与 key，可信宏不计作 baseline。
