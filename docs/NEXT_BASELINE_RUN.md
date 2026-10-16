# 下一步：真实 baseline smoke

2026-10-16 用户更新要求：下一步应在远程 Codex 中收集 base URL、API key 与模型信息，真正运行少量实验，先跑通 baseline。用户随后要求本机“开始验证”；本机只做独立、限时、无模型的 VM 软件模拟检查，结果见 `../reports/MAC_VM_SMOKE.md`。本文件继续定义远程的模型 baseline 小批实验。

## 远程接手后的第一件事

远程 Codex 先检查现有配置和 secret，再向用户一次性收集缺失项：

> 接下来运行已授权的少量真实 CADWorld baseline smoke。请提供 BASE_URL、准确的 MODEL_ID、接口类型，并将 API key 通过当前远程环境可用的 secret 或环境变量注入方式提供，告诉我变量名。GUI baseline 需要模型支持图片输入；CLI 需要 Chat Completions 工具调用或上游支持的 JSON action 模式。你提供参数、环境就绪后，我会在下述小批预算内直接执行并报告结果。

推荐 secret 名为 `CADWORLD_API_KEY`；endpoint 与 model 可用 `CADWORLD_API_BASE_URL`、`CADWORLD_MODEL_NAME`。不要假定 GitHub Actions repository secret 会自动出现在其他执行环境。若远程平台没有 secret 注入入口，可以使用不受 Git 跟踪的本地配置方式，不能把密钥写进受跟踪配置、命令日志或提交。

参数收集和 Linux/KVM、Docker、QEMU、镜像、完整 upstream 依赖检查可以并行推进。没有 `/dev/kvm` 时给出明确解除条件和所需主机能力；不能靠再装一个普通容器就声称解决。具体环境命令在 `HANDOFF.md`。

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

## 先把自定义 endpoint 接入，再运行

**当前仓库的外层 baseline 启动器没有完成通用 endpoint 参数接入，需要远程 Codex 先做以下最小适配。当前文档中的变量名是接入约定，不代表现有脚本已经支持这些参数。**

1. `cad_cf/baseline.py` 的 GUI provider 仍写死为 Gemini，CLI base URL 仍为本地 `127.0.0.1:8001/v1`。为 provider、base URL、model ID 和 key 的环境变量名增加可配置入口，dry-run 显示实际计划；不把 key 值放入 argv、输出或 manifest。
2. pinned GUI runner 已有 `--api_provider`、`--api_base_url`、`--model_name`。其中 `openai-compatible` 走 Chat Completions，并从 `CADWORLD_OPENAI_COMPATIBLE_API_KEY` / `CADWORLD_LOCAL_API_KEY` 读取 key；`openai` provider 的请求路径与其不同，不能只凭 endpoint 名称猜接口。按用户提供的接口类型映射，复用上游 prompt、parser 与 runner。
3. pinned CLI 已有 `--base-url`、`--model`、`--api-key-name` 和 `--env-file`。但默认 client 的 key 是 `EMPTY`，`--api-key-name` 读的是指定 dotenv 文件，不能假定仅设置 `OPENAI_API_KEY` 或 `CADWORLD_API_KEY` 就会生效。用本项目适配层正确注入所选 secret，或使用不受跟踪的凭证文件；不修改上游评分器。
4. CLI 的原始 `healthcheck()` 会调用 `/models`。如果服务确实不支持该路由，明确记录兼容性差异；可在可信适配层使用用户提供的准确 model ID 和受限生成验证，不能伪称已列出模型，也不能为探测服务自动启动或下载模型。
5. 保留 `upstream_launch.py` 的零重试、usage trace、总时长和 token gate。它目前按 launch 共享预算，远程需要为 endpoint 验证、GUI 与 CLI 建立整批账本，确保 15 次 / 16000 输出 tokens 不因切换进程而重置。不要自动启用第二批。
6. 用 HTTP mock 验证 endpoint、Authorization 注入、缺 key 拒绝、key 不出日志以及预算拒绝；通过后再发出用户 endpoint 的那一次真实验证请求。不会接触上游隐藏规则，也不需要引入新 benchmark。

接口适配完成后给出实际可复制的命令，保存 provider/model、base URL 的必要非敏感信息、预算和 config/code SHA。不要在交接里直接写一条现有脚本并不支持的命令，声称它已经可运行。

## 实际运行顺序

1. 完成 pinned submodule 和原始 CLI unittest / dry-run。修正环境依赖，不把旧 `scripts/verify.py` 期待的 Mac 失败退出码当成远程通过条件。
2. 显式准备官方 VM，记录来源与 SHA；完成无模型的 reset/observe/close 检查。镜像与主机不可用时先解决环境，不能把 endpoint 文本响应当作 baseline 跑通。
3. 收集 endpoint 参数并完成上述自定义接口适配，在整批预算内执行一次模型验证。GUI 使用图片，CLI 使用上游支持的 action 协议；兼容性失败就保留错误并修复，不切换到其他 benchmark。
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

这些模型实验由接手仓库的远程 Codex 执行。本机 VM 基础设施检查不消耗本文件的模型调用预算，也不计入 baseline 任务数。
