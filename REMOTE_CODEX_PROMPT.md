请接手 GUILab 仓库中的 CADWorld ACTC 复现工程，直接推进执行。

先读根目录 AGENTS.md、HANDOFF.md、SPEC.md，再按 HANDOFF 的顺序检查报告与 pinned upstream。上游固定为 e5d0ebab8bd28da6e98c68c61db05747d1647f7b，不重新调研论文或替换 benchmark。

当前真实 baseline 尚未跑通：只有历史 70 个项目单测、7 个 upstream CLI 单测和 9 个 synthetic case，真实任务与 pairs 为 0。首先确认当前远程环境是否具有 Linux x86_64、可访问 /dev/kvm、Docker daemon、QEMU、足够磁盘和外网。远程 Codex 普通容器不保证有这些能力；没有就如实记录 blocker，不能伪造 VM 成绩。

按 P0 → P1 → P2 → P3 进行，当前重点是 P0：初始化 submodule、核对 SHA、安装合适依赖、让原始 CLI unittest 和 dry-run 通过；再在镜像与环境就绪时完成无模型 VM 检查。明确记录官方 GUI-only、官方 CLI、extended hybrid 的协议与不同可见信息。

ENABLE_PAID_RUNS 默认保持 0。本条交接消息没有追加模型额度，不授权 full-200、24-pair pilot、自动下载大模型、训练或 veRL。先完成无付费工作；需要真实模型时说明实际 provider/model、可用凭证状态和具体任务/调用/token/wall 上限，再依据会话中的授权启用。不得输出或提交密钥。下载官方 VM 必须显式操作并记录实际 SHA。

HANDOFF.md 已列出应优先排查的代码风险，特别是 scripts/verify.py 的 Mac 固定预期、qcow2 backing file 的容器可见性、guest GUI bridge 的部署启动、headless FreeCAD 的保存重开，以及 pair artifact 到官方 post-hoc 评分路径的接入。逐项用真实环境验证后再更新阶段 gate，不能仅把 JSON 改为 PASS。

最终更新 reports/{REPRO_STATUS,BASELINE_REPRO,PILOT,FAILURE_CASES,DEVIATIONS}.md、机器可读阶段状态及必要脱敏证据，提交代码并报告实际命令、任务 ID、产物、成本、失败/阻塞和 GO/NO-GO。保留所有失败样本，mock 不计入研究结论。
