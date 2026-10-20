# GUILab 执行约定

始终使用简体中文。回答分为“直接执行”和“深度交互（如有）”。从原始目标判断下一步，优先完成必要验证，保持实现简单。

## 接手入口

先读 `docs/NEXT_BASELINE_RUN.md`、`HANDOFF.md` 和 `SPEC.md`，再读 `reports/REPRO_STATUS.md`、`reports/BASELINE_REPRO.md`、`reports/DEVIATIONS.md`。`REMOTE_CODEX_PROMPT.md` 可直接作为远程会话的首条任务消息。

仓库根目录就是原 `cad-cf-hybrid` 项目，不需要再套一层同名目录。`vendor/CADWORLD` 是 Git submodule，固定 commit 为 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。按 pinned 源码做最小适配，不重新调研论文或更换 benchmark。

## 当前事实

最新事实以`reports/GUI_COORDINATE_AUDIT.md`、`reports/GUI_CONTROLS.md`、`reports/GUI_VALIDATION_20261020.md`、`reports/BASELINE_REPRO.md`和`handoff.json`为准。Qwen3.5-122B CLI sketch-061官方1.0、原生审计PASS；Qwen3.6 CLI官方1.0但原文件Invalid。GUI controls007完成Body/XY空Sketch、GUI保存关闭重开，PASS_GUI_CONTROL_CYCLE。随后122B GUI复测25次生成、2328输出tokens、官方strict=0、无文件，无API错误；后段点击落在Choose Orientation对话框外。官方Qwen要求原图像素、无缩放；最近normalized1000 v2为本项目额外协议。两路离线SDK对照通过不等于模型定位正确；可用scripts/replay_gui_protocol.py --protocol compare重验。累计226次生成，最新154项项目测试与4项官方Qwen测试通过，全部本项目VM停止，真实pairs=0。当前优先解决模型GUI坐标定位，正式TypedWorker/GUI bridge同步和same-S0后移；不新增本轮推理或重开已用尽账本。参考Linux/KVM gate保持原记录，远程须验证自己的环境。

## 实验与预算

按 P0 → P1 → P2 → P3 推进真实实验。P0/P1 未通过时，后续静态开发和 mock 可以继续，真实实验不能越级。`reports/stages.json` 只能依据新证据更新，禁止直接修改 PASS 绕过 gate。

默认 `ENABLE_PAID_RUNS=0`、`MAX_LIVE_TASKS=2`、`MAX_PAIRS=3`、`MAX_MODEL_CALLS_PER_TASK=12`、`MAX_WALL_SECONDS_PER_TASK=600`、`MAX_RETRIES=0`。2026-10-16 用户后续已明确要求远程 Codex 收集 endpoint/key 并进行少量真实 baseline smoke，授权范围与首批保守预算以 `docs/NEXT_BASELINE_RUN.md` 为准。默认 0 是无配置保护；参数、环境和预算就绪后，远程应为该批次设置 1 并执行，不重复请求同一范围的形式许可。用户随后要求“开始验证”，授权本机使用独立 Colima profile 做限时、无模型的官方 VM 软件模拟检查；早期结果见 `reports/MAC_VM_SMOKE.md`，后续原生 QEMU 结果见 `reports/MAC_NATIVE_QEMU_SMOKE.md`，不得计作模型 baseline 或放宽正式 gate。仍不授权 24-pair pilot、full-200、自动下载大模型、模型训练或 veRL。镜像下载必须显式记录命令、来源、磁盘需求与实际 SHA，不得借 runner 默认行为静默下载。

2026-10-19 用户进一步要求当前会话解决 GUI 宏超时并真正开始 baseline，当前 Mac 执行已获同一首批小样本授权；参数就绪后按 `docs/RUN_TCG_BASELINE.md` 执行，不再将旧的执行位置限制当作 blocker。优先 upstream CLI dry-run 与无模型 VM reset/observe 检查，再做极少量已授权模型 smoke。2026-10-19 用户确认无法提供 KVM，后续按 `docs/NO_KVM_RUN.md` 推进 TCG，不再索取 KVM 或默认安装 VMware。Linux 容器可以运行 FreeCAD，KVM 只影响 VM 硬件加速。缺资源、镜像、可用 controller 或模型服务时记录具体 `BLOCKED_BY_ENV` / `BLOCKED_BY_CREDENTIALS` / `NOT_RUN_BUDGET`。参考 preflight 不改成无条件通过；TCG 的探索验收需独立记录。

用户指定开源多模态 Qwen3 系列，本批选 `qwen3.5-35b-a3b`，图片接口验证通过。GUI/CLI 使用同一模型并加 `--qwen-no-thinking`。此前 GPT 图片请求 HTTP 500 的次数和未知 usage 继续占用原账本；用户更正模型后才记录 correction 恢复，不能删除失败或重建账本重置预算。按实际剩余额度收紧 CLI，本批总上限仍为 15 次生成、16000 输出 tokens。

后续用户明确要求“继续跑，直到模型任务能够成功，查看官方sh是否可复用”，授权单题续跑。采用显式campaign，保留所有旧账本。success账本上限50，先42次，最后122B CLI用剩余8次；gui100实际50后blocked，后50个WAIT不是模型请求；recovery为6+44，122B专用账本为图片1+GUI35。加首批15，合计201次生成。现已停止新增推理，完成原生审计与交接，不重开已完成批次，不覆盖run ID。

GUI 新增的 `normalized1000` 是显式协议适配，必须单列，不能声称整段 prompt 完全未变。预热 ack 只能证明宏完成，不能证明欢迎页可操作；卡住原因尚未唯一确定。官方 sh 的 `test_rest.json` 在 pinned commit 缺失；vLLM sh 会启动 GPU 服务，CLI wave sh 会启动四个模型与50题，不能原样启动。复用原 Python 入口，详见 `reports/UPSTREAM_SH_REUSE.md`。

2026-10-20用户要求继续解决GUI。新增无模型控件检查：保留001–006失败，007完整通过。新适配为启动前后单实例核验、最大化、私有overlay可选GNOME alive timeout（本轮5000→600000ms），以及仅用于可信探针的布局/exposure与90秒观察屏障。模型不接收Qt摘要、控件坐标或探针文件。本轮新25次账本已用满，配置`configs/gui_validation_20261020.json`不能与新ledger配合无限重开；新旧账本都保留。代码先冻结于77d10d0再运行模型，运行后核对37个源码文件并明确标记posthoc snapshot。

无预热的recovery run在第6次请求因混合单位history失败，464输出tokens保留；模型照抄了前轮pixel执行值。坐标协议v2仅将在线history的action统一为normalized单位，原返回response和完整JSONL仍记录pixel执行与mapping。真实pinned agent两轮无网络回归已验证。`success_gui_qwen36_history_001`使用同一本recovery账本，自动收紧至剩余44次；不能改用新账本恢复50次。

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
