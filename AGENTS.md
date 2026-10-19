# GUILab 执行约定

始终使用简体中文。回答分为“直接执行”和“深度交互（如有）”。从原始目标判断下一步，优先完成必要验证，保持实现简单。

## 接手入口

先读 `docs/NEXT_BASELINE_RUN.md`、`HANDOFF.md` 和 `SPEC.md`，再读 `reports/REPRO_STATUS.md`、`reports/BASELINE_REPRO.md`、`reports/DEVIATIONS.md`。`REMOTE_CODEX_PROMPT.md` 可直接作为远程会话的首条任务消息。

仓库根目录就是原 `cad-cf-hybrid` 项目，不需要再套一层同名目录。`vendor/CADWORLD` 是 Git submodule，固定 commit 为 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。按 pinned 源码做最小适配，不重新调研论文或更换 benchmark。

## 当前事实

历史本机记录为 70 个项目测试、7 个 upstream CLI 单测通过，9 个 synthetic case；新增探针后的测试结果以 reports/MAC_NATIVE_QEMU_SMOKE.md 为准。真实 CADWorld 任务、真实 pairs、模型网络请求均为 0。官方 GUI baseline 未执行；官方 CLI 原始 dry-run 曾因缺 `dotenv` 失败。远程必须重新验证，不能把这些历史记录当作远程主机验收。

## 实验与预算

按 P0 → P1 → P2 → P3 推进真实实验。P0/P1 未通过时，后续静态开发和 mock 可以继续，真实实验不能越级。`reports/stages.json` 只能依据新证据更新，禁止直接修改 PASS 绕过 gate。

默认 `ENABLE_PAID_RUNS=0`、`MAX_LIVE_TASKS=2`、`MAX_PAIRS=3`、`MAX_MODEL_CALLS_PER_TASK=12`、`MAX_WALL_SECONDS_PER_TASK=600`、`MAX_RETRIES=0`。2026-10-16 用户后续已明确要求远程 Codex 收集 endpoint/key 并进行少量真实 baseline smoke，授权范围与首批保守预算以 `docs/NEXT_BASELINE_RUN.md` 为准。默认 0 是无配置保护；参数、环境和预算就绪后，远程应为该批次设置 1 并执行，不重复请求同一范围的形式许可。用户随后要求“开始验证”，授权本机使用独立 Colima profile 做限时、无模型的官方 VM 软件模拟检查；早期结果见 `reports/MAC_VM_SMOKE.md`，后续原生 QEMU 结果见 `reports/MAC_NATIVE_QEMU_SMOKE.md`，不得计作模型 baseline 或放宽正式 gate。仍不授权 24-pair pilot、full-200、自动下载大模型、模型训练或 veRL。镜像下载必须显式记录命令、来源、磁盘需求与实际 SHA，不得借 runner 默认行为静默下载。

优先原始 upstream CLI dry-run 与无模型 VM reset/observe 检查，再做极少量已授权模型 smoke。2026-10-19 用户确认无法提供 KVM，后续按 `docs/NO_KVM_RUN.md` 推进 TCG，不再索取 KVM 或默认安装 VMware。Linux 容器可以运行 FreeCAD，KVM 只影响 VM 硬件加速。缺资源、镜像、可用 controller 或模型服务时记录具体 `BLOCKED_BY_ENV` / `BLOCKED_BY_CREDENTIALS` / `NOT_RUN_BUDGET`。参考 preflight 不改成无条件通过；TCG 的探索验收需独立记录。

## 研究有效性

- 同一公开语义 intent、同一可重算 S0、两个独立 VM/磁盘/工作目录；不同 S0 或不可靠恢复必须 invalid。
- GUI/API 在显式 save/close/reopen boundary 同步，并刷新截图、核对当前文档状态。
- 只向 agent 提供白名单公开字段及当前工程状态；不传 raw task config。
- 在线 candidate、router、verifier 不读取官方 expected rules、golden `.FCStd` 或 `evaluation.json`。官方评分只在 episode 结束后离线使用。
- `/execute` 的非幂等变更不自动重试；timeout/5xx 的不确定写入需隔离 clone。
- 原生 `.FCStd` 和参数化历史必须实测；mock 不能作为原生保存成功证据。
- synthetic、invalid、tie、未知质量与 held-out 数据不进入 train preference 导出。
- G0 原论文 GUI-only、官方 terminal CLI、G1–G7 extended hybrid 分开报告；不以小样本冒充 full-200，不把 verifier 或局部修复当 novelty。

## 代码、产物与 Git

只改本项目代码，不修改 submodule 的 tracked 评分规则、参考模型或隐藏答案。差异记入 `reports/DEVIATIONS.md`。保留失败尝试、完整 JSONL 和成本；unknown 用 null + reason。

`results/` 默认不进 Git。上传摘要、manifest、必要脱敏 trace 和失败证据即可；`.env`、Cookie、Token、私钥、模型权重、qcow2 和大型原生文件不提交。`reports/evidence/mock_smoke/` 是已版本化的 synthetic 归档，内部绝对路径是历史 provenance，不能在远程当作可用路径执行。

运行适当单测与 smoke 后提交代码。`scripts/verify.py` 固定了早期 Mac 的失败预期，未经适配不能作为远程 Linux 的通用验收脚本。交接中标注的 runtime 风险必须先验证，不宣称已一键跑通。
