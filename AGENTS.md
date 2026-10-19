# GUILab 执行约定

始终使用简体中文。回答分为“直接执行”和“深度交互（如有）”。从原始目标判断下一步，优先完成必要验证，保持实现简单。

## 接手入口

先读 `docs/NEXT_BASELINE_RUN.md`、`HANDOFF.md` 和 `SPEC.md`，再读 `reports/REPRO_STATUS.md`、`reports/BASELINE_REPRO.md`、`reports/DEVIATIONS.md`。`REMOTE_CODEX_PROMPT.md` 可直接作为远程会话的首条任务消息。

仓库根目录就是原 `cad-cf-hybrid` 项目，不需要再套一层同名目录。`vendor/CADWORLD` 是 Git submodule，固定 commit 为 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。按 pinned 源码做最小适配，不重新调研论文或更换 benchmark。

## 当前事实

最新事实以 `reports/BASELINE_RUNTIME_SMOKE.md`、`reports/BASELINE_REPRO.md` 和 `handoff.json` 为准，历史无模型报告不能覆盖后续真实请求。原生 QEMU/TCG 已接入 pinned runner；单实例空 GUI 的 `DesktopEnv.reset → observe → action → observe → close` 已通过，可信 GUI 参数化保存重开已通过。原始 CLI dry-run 的旧 `dotenv` 失败保留，本轮安装受限依赖并延迟导入原始 registry 后已通过，7 项上游 CLI 单测也已重跑。正式 TypedWorker、ACTC 配对与参考 Linux/KVM 环境仍未验收。远程须验证本环境，不把本机记录直接当作远程验收。

## 实验与预算

按 P0 → P1 → P2 → P3 推进真实实验。P0/P1 未通过时，后续静态开发和 mock 可以继续，真实实验不能越级。`reports/stages.json` 只能依据新证据更新，禁止直接修改 PASS 绕过 gate。

默认 `ENABLE_PAID_RUNS=0`、`MAX_LIVE_TASKS=2`、`MAX_PAIRS=3`、`MAX_MODEL_CALLS_PER_TASK=12`、`MAX_WALL_SECONDS_PER_TASK=600`、`MAX_RETRIES=0`。2026-10-16 用户后续已明确要求远程 Codex 收集 endpoint/key 并进行少量真实 baseline smoke，授权范围与首批保守预算以 `docs/NEXT_BASELINE_RUN.md` 为准。默认 0 是无配置保护；参数、环境和预算就绪后，远程应为该批次设置 1 并执行，不重复请求同一范围的形式许可。用户随后要求“开始验证”，授权本机使用独立 Colima profile 做限时、无模型的官方 VM 软件模拟检查；早期结果见 `reports/MAC_VM_SMOKE.md`，后续原生 QEMU 结果见 `reports/MAC_NATIVE_QEMU_SMOKE.md`，不得计作模型 baseline 或放宽正式 gate。仍不授权 24-pair pilot、full-200、自动下载大模型、模型训练或 veRL。镜像下载必须显式记录命令、来源、磁盘需求与实际 SHA，不得借 runner 默认行为静默下载。

2026-10-19 用户进一步要求当前会话解决 GUI 宏超时并真正开始 baseline，当前 Mac 执行已获同一首批小样本授权；参数就绪后按 `docs/RUN_TCG_BASELINE.md` 执行，不再将旧的执行位置限制当作 blocker。优先 upstream CLI dry-run 与无模型 VM reset/observe 检查，再做极少量已授权模型 smoke。2026-10-19 用户确认无法提供 KVM，后续按 `docs/NO_KVM_RUN.md` 推进 TCG，不再索取 KVM 或默认安装 VMware。Linux 容器可以运行 FreeCAD，KVM 只影响 VM 硬件加速。缺资源、镜像、可用 controller 或模型服务时记录具体 `BLOCKED_BY_ENV` / `BLOCKED_BY_CREDENTIALS` / `NOT_RUN_BUDGET`。参考 preflight 不改成无条件通过；TCG 的探索验收需独立记录。

用户指定开源多模态 Qwen3 系列，本批选 `qwen3.5-35b-a3b`，图片接口验证通过。GUI/CLI 使用同一模型并加 `--qwen-no-thinking`。此前 GPT 图片请求 HTTP 500 的次数和未知 usage 继续占用原账本；用户更正模型后才记录 correction 恢复，不能删除失败或重建账本重置预算。按实际剩余额度收紧 CLI，本批总上限仍为 15 次生成、16000 输出 tokens。

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
