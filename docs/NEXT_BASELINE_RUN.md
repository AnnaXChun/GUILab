# 下一步：真实 baseline smoke

2026-10-20最新：GUI控制探针完整保存关闭重开通过；新25次GUI模型复测官方strict=0、无文件，模型未命中方向对话框的OK按钮。累计226次生成，最新154项单测通过，全部VM停止。官方Qwen要求原图像素，额外normalized1000协议已单列核对；当前优先做模型坐标定位校准，见[坐标核对](../reports/GUI_COORDINATE_AUDIT.md)和[NEXT_ACTC_VALIDATION](NEXT_ACTC_VALIDATION.md)。下方201次和首批15次均为历史，不得据此再次开启同一批次。

最新状态：CLI单题已通过官方评分和122B原生审计；GUI仍无成功文件，真实pairs=0。累计含探针201次生成，本轮不再新增推理。下一步按[阶段验收](NEXT_ACTC_VALIDATION.md)做无模型GUI诊断、正式worker同步和same-S0双clone。全部结果与预算见[单题续跑](../reports/BASELINE_SUCCESS_SMOKE.md)、[sh复用](../reports/UPSTREAM_SH_REUSE.md)和handoff.json。下方是**已经执行的首批历史计划**，不得重开或忽略后续证据。

2026-10-16 用户更新要求：下一步应在远程 Codex 中收集 base URL、API key 与模型信息，真正运行少量实验，先跑通 baseline。用户随后要求本机“开始验证”；本机只做独立、限时、无模型的 VM 软件模拟检查，结果见 `../reports/MAC_VM_SMOKE.md`。本文件继续定义远程的模型 baseline 小批实验。2026-10-19 用户确认无法提供 KVM，后续先按 [无 KVM 路线](NO_KVM_RUN.md) 验证 TCG；本机最新证据见 [原生 QEMU 检查](../reports/MAC_NATIVE_QEMU_SMOKE.md)。

## 当前执行位置与参数

2026-10-19 用户要求当前会话解决 GUI 宏并开始 baseline，当前 Mac 也可执行同一首批。已实现入口与实际命令见 [RUN_TCG_BASELINE](RUN_TCG_BASELINE.md)。先检查现有配置和 secret，再收集缺失项：

> 接下来运行已授权的少量真实 CADWorld baseline smoke。请提供 BASE_URL、准确的 MODEL_ID、接口类型，并将 API key 通过当前远程环境可用的 secret 或环境变量注入方式提供，告诉我变量名。GUI baseline 需要模型支持图片输入；CLI 需要 Chat Completions 工具调用或上游支持的 JSON action 模式。你提供参数、环境就绪后，我会在下述小批预算内直接执行并报告结果。

推荐 secret 名为 `CADWORLD_API_KEY`；endpoint 与 model 可用 `CADWORLD_API_BASE_URL`、`CADWORLD_MODEL_NAME`。不要假定 GitHub Actions repository secret 会自动出现在其他执行环境。若远程平台没有 secret 注入入口，可以使用不受 Git 跟踪的本地配置方式，不能把密钥写进受跟踪配置、命令日志或提交。

参数收集和容器权限、Docker、原生宿主 QEMU、内存、镜像及 upstream 依赖检查可以并行推进。KVM 已确认不可提供，不再反复索取。先检查 pinned Docker provider 的 `CADWORLD_ENABLE_KVM=false` 路线；若 Docker 不可用，使用原生 QEMU/TCG 并完成 runner 生命周期适配。Linux 容器可以运行 FreeCAD；是否具备桌面、依赖和所需资源需要实测。具体步骤见 `NO_KVM_RUN.md`。

## 付费调用如何启用

`ENABLE_PAID_RUNS=0` 是无人配置时的默认值，不是禁止真实实验的研究要求。用户已经明确要求少量真实 baseline smoke；同一范围内收集到参数、预算可执行且环境通过后，远程 Codex 应为本次进程设置 `ENABLE_PAID_RUNS=1` 并运行，无需重复请求形式上的启用许可。不要继续以“仓库默认关闭”为由停在 mock。

仓库和示例配置仍保留默认 0，避免无配置调用。不要把代码改成无条件启用 API。模型凭证、VM 镜像、实际服务可达性都是运行条件，不能通过修改 stages.json 为 PASS 来代替。

首批保守上限如下。预算按整批累计，各个入口的限制不能相互绕过。

| 项目 | 首批上限 |
| --- | --- |
| 不同 CADWorld 任务 | 2：`freecad-sketch-061`、`freecad-part-076` |
| 模型 endpoint 验证 | 1 次小型生成请求，最多 128 输出 tokens；确认模型、接口、图片输入和 usage，不能算 CADWorld 成绩 |
| 官方 GUI 连接 smoke | 两题各最多 3 个 decision turns，生成调用合计最多 6 次，每次输出上限 512 tokens |
| 官方 CLI smoke | 先只运行 sketch-061，最多 8 turns、8 次 terminal calls、8 次生成调用、12000 completion tokens |
| 整批生成调用 | 最多 15 次，包含 endpoint 验证；失败的已发出请求也占调用预算 |
| 整批输出 tokens | 最多 16000；输入 tokens 和 provider 返回的 thinking/计费信息另行记录，不把输出上限当作完整账单上限 |
| 每题累计模型调用 | 不超过原默认 12；sketch 的 GUI 3 + CLI 8 = 11，part 的 GUI为 3 |
| 时间 | 每次模型请求最多 110 秒；每个 baseline launch 的模型 gate 为 600 秒，共享给该 launch 内各题；保留进程级强制超时 |
| 自动 API / 非幂等执行重试 | 0；401/403/5xx/timeout 后记录错误并停止相应请求链，不反复试 key 或重发变更 |

这些是对“少量实验”的保守执行上限，不授权 25-step 两题追加、24-pair pilot、full-200、大模型下载、训练或 veRL。先在该范围内给出真实闭环证据和问题。需要加长 episode 或增加预算时，先报告已花费和预计追加量，再讨论扩展。

若提供的 endpoint 无法返回可计量 usage，应报告缺失并停止继续计费请求。无法提前给出美元成本时，报告请求/token 上限和缺失的价格信息，不虚构费用。`/models` 之类只读健康检查单独记录；失败后不要进行无限探测。

## endpoint 与执行入口

本轮已为 `cad_cf.baseline` 增加 base URL、model ID、provider、所选 key 环境变量和 ignored dotenv 接入，CLI 默认 EMPTY key 由可信 SDK 适配注入。HTTP mock 已验证 Authorization 和 token clamp，key 值不进 argv 或 launch manifest。GUI/CLI 原始 runner、prompt、parser、metric/getter 实现不变。

endpoint 验证、GUI 和 CLI 共用 SQLite batch ledger，不能通过分别启动进程重置 15 次 / 16000 输出 tokens 上限。未完成或失败的请求关闭 circuit。SDK 零重试，GUI 动作持久化单次派发，未知写入不重发。模型 wall gate 从首次请求计 600 秒，OS/GUI 启动另设有限 deadline；整个 runner 最多 1800 秒，超时终止本轮进程组。计时适配、视频禁用、TCG 和 lazy registry 单独报告。

当前优先接 OpenAI Chat Completions 兼容接口。CLI 保留 upstream `/models` healthcheck 与默认 native tools；服务不支持时记录兼容性阻塞，不假称列出模型，也不启动模型服务。其他接口按 pinned provider 的实际路径核对。

真实调用前使用 `probe_baseline_env.py` 生成 TCG 验收，证明空 GUI、单个 FreeCAD 实例和官方 DesktopEnv 的 reset/action/close。历史仅有 screenshot HTTP 200 或两个 GUI 的原始 PASS 不能启用计费。TCG 模型结果与参考硬件协议分开。

## 实际运行顺序

1. 完成 pinned submodule 和原始 CLI unittest / dry-run。修正环境依赖，不把旧 `scripts/verify.py` 期待的 Mac 失败退出码当成远程通过条件。
2. 显式准备官方 VM，记录来源与 SHA；按无 KVM 路线完成无模型的 reset/observe/action/close 检查。TCG 作为探索环境单列，当前参考 gate 不直接放宽；需要在适配层增加该协议的独立验收，不能手改 stage PASS。镜像与主机不可用时先解决环境，不能把 endpoint 文本响应当作 baseline 跑通。
3. 收集 endpoint 参数，使用已实现接口，在整批预算内执行一次模型验证。GUI 使用图片，CLI 使用上游支持的 action 协议；兼容性失败就保留错误并修复，不切换到其他 benchmark。
4. 启用本次进程的付费调用，在两道 creation 题上跑官方 GUI 3-turn smoke。核对真实轨迹、截图、动作、评分与产物收集，区分 strict=0 和 run_error。
5. VM 与模型接口健康时，在同一服务/实际 model ID 上运行官方 CLI 的 sketch-061 小批。CLI 不提供运行时桌面截图，作为单独基线记录，不与 GUI 假称完全相同 observation budget。
6. 汇总首批结果。只有基线真实闭环通过，才考虑后续原生 GUI/API 同步和 paired intervention。不要为了先出 ACTC 标签跳过 baseline。

## 这批怎样算有结果

- 实际运行的任务 ID、协议、模型、命令和时间必须能追溯。
- GUI 有 `traj.jsonl`、`result.txt`、`evaluation.json`、截图/运行日志；CLI 有其原始轨迹、结果、artifact 与诊断。缺失项明确列出。
- 所有真实 `.FCStd` 来自 agent 运行，并核查保存、可打开与原生结构。没有文件就报告缺失，不以 fixture 或 reference 文件补齐。
- 任务 strict=0 可以是一次有效测量；runner、模型或 VM 错误必须单独归类。流程跑通、文件有效、任务得分和论文全量成绩是不同结论。
- 不论通过或失败，都保留样本与实际成本，更新 `reports/BASELINE_REPRO.md`、`REPRO_STATUS.md`、`FAILURE_CASES.md`、`DEVIATIONS.md` 和必要机器可读记录。`stages.json` 依据证据更新。
- 若第一批只是连接 smoke，报告“已完成 N 个真实 episode，strict 分别为……，还有哪些阻塞”；不写“已复现论文 17.5%”。

## 给远程 Codex 的执行要求

先索取缺失参数并检查环境，接着做最小接口适配并完成已授权的小批真实 baseline。拿到可执行条件后持续完成闭环，不以再次重述计划结束。只有需要新参数、实际环境不可用或超出这批预算时才报告具体阻塞。

模型实验可由当前已获授权的本机会话或接手的远程 Codex 执行，共用同一首批预算，不各自开第二批。可信 VM/GUI 检查不消耗模型调用额度，也不计入 baseline 任务数。
