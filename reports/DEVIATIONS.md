# 差异与适配

2026-10-23 新增全量 CLI 离线分析：逐题原始官方分数、执行不确定、启动失败与原生文件审计分别记录。审计按原路径和 SHA 绑定，拒绝其他批次文件、变更后的文件及重复审计；原生重开、对象状态、通用编辑探针采用独立计数。该后处理不修改正在运行的模型 prompt、账本或官方评分规则。

全量已保存的装配文件中有约 1.8 MB 文件，原审计的 base64 命令参数会超过 Linux 单参数长度限制。新审计复用 pinned `desktop_env/server/main.py` 的 `/setup/upload`，一次 multipart 上传后检查 SHA，再以独占标记执行原生 worker。上传及执行不确定均保留并停止审计，不重发。三项上传单测通过；真实传输与全量原生审计等待当前两路 CLI 批次停止后执行。

完整回归中的旧公共输入 dry-run 测试原先读取项目里的全部模型账本，会与正在运行的全量批次冲突。该单测改用独立冻结账本，保留生产账本保护；修正后 292 项项目测试、7 项 upstream CLI 测试通过。MCP 索引正常，两个历史有限大数 JSON 的局部解析告警保留，索引可用不代替测试或真实原生验收。

零 API 的 [Link schema 探针](evidence/cli_link_schema_20261022/INDEX.json) 使用自定义公开名称 `ReferenceSketch`，验证 pinned getter 将普通 Link 解析为字符串、无子元素的 LinkSub 解析为字典；与同一字符串条件比较的结果为 true/false。它只证明通用 schema 区别，没有读取任务规则、没有将某题失败归因于此，也没有规范化链接或改分。首次独立加载 metric 缺少相对包上下文的 ImportError 保留；在独立命名空间补齐包上下文后探针成功。

上游 `getters/freecad.py::parse_part_fcstd` 从 XML 属性推算支持的 primitive/scale 形状，并不通过 FreeCAD 内核读取 BRep。Pad/Pocket 等不在 primitive 推算分支，文档摘要中的 `total_volume=0` 不能当作原生 `Shape.Volume=0`。原评分保持，真实重开和参数响应另做原生核验；该解析边界属于结果解释，不放宽评分或修改模型输入。

上游 `CLI/run_cli.py::describe_result` 在 geometry.ok=True 时使用“几何正确”，没有检查 n_checks 是否为零。本项目只修正离线分析口径：零项标为 UNCHECKED，原始失败标签、分数和任务轨迹保留，不改官方 evaluator。活动进程继续使用原报告函数，结束后由 `summarize_cli_full_sweep.py` 离线刷新完整表格。

全量汇总的结果路径补齐 pinned runner 的 `CLI/results/actc/<run_id>/<task_id>` 层级。活动调度进程沿用旧读取代码，仅增加指向原结果的本地只读 symlink 兼容；没有修改轨迹、官方分数或已启动任务。离线表格改为从同一 JSON 快照渲染，区分仍待完成与全部尝试后含未知评分；运行错误保留完整分母。

全量的 runtime/evidence SHA 在 config 中冻结，runtime Python 模块另与 `025cab6` 核对。源码核对是在批次启动后记录，标为 posthoc；这与候选批次的请求前源码记录分别报告。当前除离线汇总外的 runtime 模块均与参考提交一致，未改正在执行的模型 prompt 或 controller guard。

本轮通用 Pad API 先经原生验证；Quantity 字面量构造最小放行，四条历史拒绝理由保持。可信分支 worker 从 110→180 秒、HTTP 等待 200 秒，默认桥接上限仍 120 秒；旧失败不重发。模型原文不改，固定 C 与 S0 保持。[成功小批](CLI_MODEL_CANDIDATE_SUCCESS_20261022.md)与全量原 terminal CLI 分开；全量采用单题 16384 输出 tokens、20 轮，单次上限沿用 8192，不冒充官方默认 51200 预算复现。

## 多步原生执行的最小适配

2026-10-22 专用 Sketch/Body/Pad/Pocket runner 已实现，结果见 [多步 pilot](CLI_CAUSAL_PILOT_20261022.md)。Compound 质心读取改为实际 solid，Body 显式 touch/recompute；Pocket 的中心按供应圆心补约束，保存前后 DoF 均为 0，重开检查保留。预检 004 暂停本项目截图等待父进程，在同 VM 通过独立一次 ledger 派发准备，恢复后由原父进程超时清理；此流程单列，未冒充自动入口成功。

后续 CLI 明确使用 controller-only 就绪，GET /platform 须返回 Linux；GUI 默认仍要求 PNG。准备 worker 去掉重复 verifier 历史并在发送前限制单参数长度，原 Errno 7 uncertain 派发隔离保留，没有重发。runner 将候选接口拒绝限制在单题，补采器沿用原提示/S0/控制证明和同四次账本完成剩余请求；服务错误/unknown usage 仍停止采样。4 条原模型代码未编辑或放行，静态拒绝不设几何 Q=0。恢复的预检 worker 源码为 posthoc recovery，并按实际派发的 manifest 校验 SHA；注入的原生文件编码不上传。

## 多步 CLI 局部信用设计

2026-10-22 将实验从 Torus 测量转为供应 Sketch 上的 Pad 与 Pad→Pocket。固定后续执行首轮由可信代码实现，其来源和 SHA 在候选生成前冻结；它解释固定上下文的相对作用，真实 agent 续执行需另行验证。part-001 的下游测量审计是工程扩展，part-014 的 Pocket 来自公开任务。图暂不参与分数；局部 credit 与同响应终局 Best-of-2 等价作为检查项，后续价值由同奖励归因/训练对照检验。设计入口见 [多步小批](../docs/CLI_CAUSAL_CREDIT_PILOT.md)，实际完成状态与成本见本批报告，原设计配置不回写。

## CLI 通用接口说明与响应封装

新增通用 FreeCAD API 说明，先在独立 Box 文档实测 PropertiesList、pi、^、单位、保存重开与参数响应，通过后才发新模型请求。说明不含圆环公式。两响应有 JSON 围栏，保留原严格 JSON 拒绝后启用显式 single_json_fence，只去单个完整围栏，代码字符串不改；以新 overlay 恢复原 seed 执行既有响应，无新增模型请求。两候选 Q=1/1、credit=0，原生 XML 与六探针审计通过。该设置是扩展测量协议，原 baseline prompt 和历史成绩保留；历史失败与新成功不能当作等预算因果对照。服务请求 thinking=false 仍返回 reasoning_content/962 reasoning tokens，按完整 completion 用量保留。详情见 [CLI 接口修复](CLI_API_GUIDED_PAIR_20261021.md)。

## 捕获S0的模型代码块

新增模型前保存重开S0、同prompt两独立采样与durable模型限额，扩展接口仅允许数值测量属性。首60秒超时保留，110秒新批限2请求，累计实际3请求，SDK重试0。B的hasProperty只读查询原白名单遗漏，保留原拒绝后只放行固定测量查询；实际API仍不存在，失败不改代码。停止捕获overlay作为只读backing，新overlay恢复原seed/native state后执行原responses，无新增模型请求。原非幂等候选只执行一次、失败无artifact、credit=null，旧账本未改，原baseline协议不替换。

## 模型代码块重放

新增`cad_cf.cli_replay`与可信worker，复用实际Qwen轨迹第4/6/7轮的连续AST源码；适配只移除shell、import、文档open/new和save/close外层，保留原片段与SHA。历史S0未捕获，新建同S0的prospective replay单列。首轮Shape.Area表达式不刷新，原数据保留；修正版仅改为公开半径公式，保持续执行与容差。探针只重算FreeCAD，不重放模型代码。人工候选、数值proxy与工程响应目标均标明来源/范围，不作为官方episode或训练数据。通用runner只新增worker/evaluator注入点，原默认fixture协议保留。

## CLI 结构信用诊断

2026-10-21 用户要求验证 CLI 方法方向，新增三个可信程序 fixture，不调用模型、训练或官方评分器。它们是 controlled synthetic，训练 eligibility 为 false，原 ACTC gate 不改判。每分支独立 FreeCAD 进程、文档和 artifact 目录，共用 VM；第二轮显式设定独立 cwd，未冒充双 VM 或强 OS sandbox。

首轮固定 Q 的原始结果 `[0, 0, 1]` 保留。真实圆环 `Shape.BoundBox` 是保守值，修正版使用实际 VM 的 `optimalBoundingBox(False, False)`，保留旧值与 API 说明，Q 公式和容差未改。两轮执行前后源码 SHA 和实际派发 payload 核验通过；第一轮源码快照单独保留，第二轮结果 `[1, 0, 1]` 单列。FreeCAD remote 源码读取遇到 404/403，适配依据为原生 API 实测。依赖图目前仅记录影响范围，信用与同一终局 Q 差值相同；方法优势、独立算法对照和 RL 效果均待测量。

## CLI 方向切换

最终归档的 106 份 JSON 通过严格解析与 SHA 核验。MCP 对两份审计记录的 App::Plane 面积 `8e+100` 给出局部解析告警；它是有限的合法 JSON 数值，本轮没有观察到 NaN。审计器新增 `normalize_native_numbers` 和严格 JSON 编码，未来非有限数值写为 null 并记录字段路径与原因。本轮未触发数值转换，原始响应、诊断字节、模型文件和评分均不变；新增两项通用序列化回归，无新 API 或 VM 执行。

2026-10-21 用户明确停止 GUI，转为 CLI 数据清洗、RL 和成功率改进。原 SPEC 作为历史保留，新执行协议见 [CLI_RESEARCH_PLAN](../docs/CLI_RESEARCH_PLAN.md)。GUI/API 反事实路由不再作为本方向目标，旧 gate 不改判为 PASS。

`cad_cf.baseline` 新增显式 `--tasks-file`，单次 CLI launch 限制为至多两个任务；`cad_cf.campaign` 允许只配置 CLI，缺失 GUI route 时拒绝启动 GUI。多题共享请求与输出账本，每题保留原 runner 的限步和 reset。复用的是 runner 进程，TCG reset 仍会重启新 VM overlay；不是同 VM 连续跨任务，也不是 same-S0 pair。官方 prompt/tools/parser 和评分规则不修改。

`cad_cf.cli_data` 是本项目新增的离线清洗入口，官方分数只进 `offline_evaluation`。公开目标检查仅支持三类明确语义，其他返回 null。原生批量审计扩展了圆半径和圆环参数编辑探针，并记录全局几何位置与原生面积属性；仅在独立临时副本中编辑，原 artifact SHA 保持不变。训练接口不接 veRL，也未启动 RL。

## 固定截图定位校准

2026-10-20新增`cad_cf/gui_grounding.py`、冻结配置/离线标注、shell入口及5项测试，复用pinned agent和现有预算保护。用户授权的6次真实请求已完成，159项全量测试通过。该轮只收集同图同目标的单轮预测，不接桌面controller；标注不进入模型请求，未读官方评分规则，upstream tracked源码未改。完整细节见[定位校准](GUI_GROUNDING_20261020.md)。

代码、预算与标注在首次请求前提交为6caebeb。pixels使用官方prompt/adapter，normalized1000使用已有扩展后缀；原定命中0/3与2/3。看到结果后新增的“pixels原始值按1000解释”为3/3，单列事后假设，不重写analysis或冒充第三实验组。本轮14825输入/473输出tokens，旧6本账本SHA不变，累计232次生成；无VM、无点击、无新增episode或ACTC pair，默认付费和阶段gate不变。

## 官方坐标协议核对

2026-10-20按用户要求复核pinned `baseline/Qwen3-6/adapter.py`：官方要求original screenshot pixels，`adapt_actions`原样返回。`normalized1000 v2`是本项目明确改变prompt和执行坐标的扩展，不是官方Qwen默认处理；不能把Holo的1000分母或OpenCUA的smart_resize自动套到Qwen服务。运行入口默认本来就是pixels，本轮未改默认或模型执行逻辑。

仅扩展离线`scripts/replay_gui_protocol.py`增加官方pixel与原扩展协议的相同响应对照，添加真实SDK/原图/history的回归测试。项目154项、官方Qwen 4项测试通过，新增网络、生成、VM启动均为0。结论、原始链接和命令见[坐标核对](GUI_COORDINATE_AUDIT.md)。下一步按用户方向优先模型GUI定位校准，正式TypedWorker同步后移；未新增实验额度，未改变任何gate。

## 2026-10-20 GUI专项

本轮新增固定、无模型的`cad_cf/gui_control_probe.py`，只读Qt宏观察状态，建模与保存全部使用PyAutoGUI。它的控件坐标来自Qt，仅用于可信基础设施探针，不提供给模型；不能作为GUI baseline、在线修复器或ACTC候选。完整经过见[GUI控件验收](GUI_CONTROLS.md)。

| 来源或实际差异 | 最小适配 | 结论边界 |
| --- | --- | --- |
| 冷启动时已排队的FreeCAD自动实例可能在关闭autostart后才出现 | `gui_startup.prepare_gui`在等待宏前和ack后分别核验单实例，启动PID与ack PID必须一致 | 只结束验证过的空启动实例；不能用宏ack替代GUI操作验收 |
| 非最大化窗口可能将欢迎页Done裁出屏幕 | 启动时最大化、raise/activate并记录几何，未最大化拒绝ready | 控件可见性需实际截图与操作再验收 |
| controls004截图显示GNOME外部未响应弹窗，Qt activeModalWidget仍为null、心跳仍在前进 | 新可选`gui_alive_timeout_ms`，默认null；本轮新overlay显式600000ms，设置前记录原值5000ms与schema，设置后读回核验 | 这是TCG桌面超时适配；保留应用执行deadline，不改评分规则，不声称历史唯一根因 |
| pinned `scripts/python/run_cadworld.py`已有`--sleep_after_execution`，默认0.3秒 | campaign可选`settle_seconds`，仅接受0..10有限数值，通过同一原参数透传；本轮GUI复测计划为5秒 | 原始默认保留；等待时间变化单列，不直接用于等硬件时延比较 |
| FreeCAD空Body/Sketch的Shape为NULL | 只读观察器先isNull，再决定是否isValid；NULL有效性写null | 不把观察器异常或空Shape当作模型工程错误 |
| controls005对话框显示后还会改变位置，截图前读到的坐标已过期 | 可信探针新增布局稳定、模态active/exposed及截图后重读屏障，只重复观察，不重复GUI动作 | 只用于探针，不给模型Qt信息，不更改模型baseline的动作逻辑；失败原样保留 |
| controls006的内部只读观察截止30秒，早于阶段的90秒等待，进入Sketch时被提前截断 | 统一到90秒且服从1800秒总时限；同一个观察请求只提交一次，等待迟到ack | 007完整通过；006保持FAIL，不把观察超时直接判为CAD死锁 |

本轮模型复测为25次/16000输出tokens上限，实际25次、2328输出tokens、官方strict=0。它使用normalized1000 v2、5秒settle与600000ms GNOME alive timeout，不能与历史设置合并归因或计算成功率。可信探针的Qt信息和鼠标停留未加入模型。实现先提交为`77d10d0`再启动模型；运行后核对并归档37个cad_cf文件，明确标作posthoc snapshot，不声称在本轮首次请求前自动采集。全部数据与原生审计未运行原因见[本轮复测](GUI_VALIDATION_20261020.md)。

新增`scripts/replay_gui_protocol.py`用于已完成轨迹的零网络mock SDK复放，未参与模型运行；真实截图和公开归档两路均PASS。另修正`scripts/final_summary.py`读取最新handoff与命令清单，移除早期写死的“0真实任务、缺VM/凭证、应补KVM”等陈旧摘要，不改变实验执行与评分。

下方为之前各轮的历史差异，不能把其中的“未接入”“无凭证”等旧状态当成本轮最新阻塞。

| 来源与确切路径 | 实际差异 | 影响与本项目适配 |
| --- | --- | --- |
| `vendor/CADWORLD/desktop_env/providers/docker/provider.py:362` | `save_state` 抛出 `NotImplementedError`；revert 只停止 emulator | 不调用它伪造快照。`snapshot.create_overlay` 要求停机 source disk + SHA；两路独立 disk/VM/endpoint，原生状态与截图再比对 |
| `vendor/CADWORLD/desktop_env/controllers/python.py:136` | GUI `execute_python_command` 内有重试循环 | 配对 GUI/API 共用一次性 `TerminalBridge`，持久化 dispatch ledger。HTTP timeout/5xx 判 outcome uncertain，隔离并销毁 clone，绝不重发 |
| `vendor/CADWORLD/CLI/run_cli.py:420` | CLI 内联 `/execute` closure 不能直接导入复用；snap runtime 有环境预设 | 本项目仅封装同一 endpoint/payload，保留 timeout 和无 shell 暴露。固定 worker 复用 snap 的 PATH/PYTHONPATH/LD_LIBRARY_PATH 设置；不修改 HOME |
| `vendor/CADWORLD/scripts/python/run_cadworld.py:93` | `--download_vm` 默认 true | 启动命令增加 `--no-download_vm`；下载保持显式操作 |
| `vendor/CADWORLD/CLI/prompts.py:39` | normalize 支持三种精确前缀且会 strip/lstrip | 本项目逐字复用同样的前缀规则。raw 保留，effective 单独记录，官方 GUI 使用 raw |
| `vendor/CADWORLD/desktop_env/evaluators/diagnostics.py:717` | diagnostics 读取 evaluator.expected | 仅 `posthoc.py` 离线可信入口引用官方收集/诊断函数；verifier、candidate、router 不导入它，模型不接触 raw task config |
| `vendor/CADWORLD/pyproject.toml` / `uv.lock` | full sync 405 包含大型推理/视觉运行时 | 本机 Mac 先用轻量本项目 venv 跑 upstream CLI 单测；full sync 只预览，原始 CLI dry-run 失败如实保留。Linux 上由 bootstrap --full-upstream 执行完整依赖 |
| SPEC P0–P3 Stop/Go 与初期静态交付 | 初期本机缺少KVM、VM及凭证；后续TCG/VM/模型服务已实测 | 参考环境gate仍未通过；正式P1–P3尚未验收，不以synthetic或单路CLI成功满足≥3 real pairs |
| native fork 工作文件 | 任务公开路径常为 `/home/user/Unnamed.FCStd`，并行 worker 需要每任务私有目录 | NativeBackend 在 guest `/home/user/current` 操作 checkpoint/artifact；正式 post-hoc 前由可信适配层发布已保存文件到任务输出路径。官方 baseline 原路径不变；该发布尚未真实验证 |
| GUI 进程同步 | 上游未提供可复用的同步 FreeCAD GUI IPC | 新增 guest-only loopback/Qt 主线程桥。仅 summary、commit/close、reopen；启动宏是受控 checkpoint 准备步骤。没有桥或无 ack 时拒绝配对；GUI bridge 尚未实际部署验收 |
| same-S0 | 精确截图哈希容易受光标/动画/通知影响 | 初版宁可拒绝 pair，要求稳定 workbench/camera/selection/文档集与截图。未用近似截图相等放宽证据 |
| 任务分组 | 原 test_easy/test_small/test_60 重叠，且 precondition 工程可能重复 | 仅公开操作 family + 明确提供的 precondition 文件 SHA 做并集分组，兼顾领域与 edit 初筛池，尽量接近 60/20/20，seed=20261015。完整任务实际 92/25/23，edit 初筛候选 19/7/6；分组完整性优先于精确比例 |
| 原生执行失败的归类 | 已知无效形体与网络结果不确定需要分开 | 文件可重开且终态已知时保留低质量候选；timeout/5xx 或无法恢复终态时判 invalid_pair。全部记录失败分支成本，未知动作数用 null，不当作零成本 |
| verifier unknown | SPEC 允许不适用项重归一化，但未指定 unknown 的乐观处理 | 仅不适用项重归一化；任何适用质量项 unknown 则不产生方向标签。当前目标 grammar 保守，未覆盖项显式 unknown；只在 val 上扩展/冻结规则 |
| `CLI/terminal_agent.py:236` 与 `scripts/python/api_agent.py:732` | SDK client 没有显式禁用默认重试 | 外部 `upstream_launch` 仅覆写 SDK constructor/request 预算，OpenAI max_retries=0、Gemini attempts=1；错误后不再调用 provider，usage 独立 JSONL。未改 prompt、parser 或评分器；原始命令与受限执行命令分开记录，guard 仅 mock transport 验证 |
| P3 24 valid pairs | 默认限 3 live pairs，且没有额外授权 | 24-pair pilot 不启动，NOT_RUN_BUDGET。9 个 mock campaign case 不计入 3 个合法真实 smoke pair 或 24 valid pair 目标 |
| 运行时模型生成 | 本轮凭证/环境不可用 | deterministic candidate stub + reviewed live-plan 接口；没有伪造模型 proposal、tokens、provider 时间或任务成绩。P4 predictor 接口提供，训练 NOT_IMPLEMENTED |

所有上述变化均位于本项目。上游 evaluator、规则、参考 artifact 与 tracked 文件未改动，也未读取 golden `.FCStd` 来生成答案。选样只 hash `fixtures/precondition/` 下明确作为任务输入的文件，未打开这些文件解析几何。正式 native worker 路径目前只静态验证；最新可信 headless 探针单列于下文，不替代 worker/GUI 同步验收。

## 2026-10-16 Mac 环境验证

用户后续要求“开始验证”，因此在原“Mac 静态开发”边界之外增加独立、限时、无模型的软件模拟检查。它不是正式 baseline，不改变 `preflight.py` 和 `reports/stages.json` 的 Linux x86_64/KVM gate。

| 来源与确切路径 | 实测差异 | 最小适配与影响 |
| --- | --- | --- |
| `desktop_env/providers/docker/provider.py:start_emulator` | 本机为 ARM64，只有 amd64 binfmt；外层 preflight 会拒绝参考环境以外的启动 | 新增 `scripts/probe_mac_vm.py`，以显式 Docker CLI 检查同一官方容器/VM 的基础设施，不声称执行过 `DesktopEnv.reset` 或 baseline runner |
| 官方容器 Config.Entrypoint | `/usr/bin/tini -s /run/entry.sh` 在 QEMU user translation 下立即报 subreaper 不支持 | 保留默认入口失败；显式 `--direct-entry` 直接执行未修改的 `/run/entry.sh`。仅验证短期独立容器，不替换正式 Linux 入口 |
| 官方容器 `/run/network.sh` | legacy iptables 查询失败；模块加载后仍失败，nft 查询也不支持。自动 user fallback 未转发 5000 | 显式 `--user-network` 使用镜像既有 `NETWORK=user`、`USER_PORTS=5000,9222,8080`；不改评分或 guest 工程 |
| 官方容器及 provider 的资源参数 | 参考约 8 vCPU/8 GiB/KVM；本轮为 2 vCPU/8 GiB/TCG | 记录真实时延与超时，不用于等硬件效率比较或 stage PASS |
| pinned `scripts/python/download_vm_image.py` | 单连接传输过慢 | 同一官方 URL 续传，保留失败/切换记录；完整 Python SHA256 与 HF 内容哈希一致后才改为正式 qcow2 文件名。没有替换镜像或重选 benchmark |

逐次命令、结果、截图和清理证据以 `MAC_VM_SMOKE.md` 及其版本化证据为准。没有模型生成、官方评分或真实 pair，不把可信基础设施探针用于 preference 数据。

## 2026-10-19 无 KVM 原生 QEMU

用户确认无法提供 KVM。Linux 容器能够运行 FreeCAD；KVM 用于 VM 加速，不能把缺 KVM 直接等同于所有执行不可行。本轮结果和证据见 [原生 QEMU 报告](MAC_NATIVE_QEMU_SMOKE.md)。

| 来源 | 适配与边界 | 实测 |
| --- | --- | --- |
| pinned `desktop_env/providers/docker/provider.py:173,284` | upstream 已支持 `CADWORLD_ENABLE_KVM=false`，其 Docker/网络权限仍需检查；不是新算法 | 远程优先验证这一原有入口；本机探针直接运行 ARM 原生 QEMU，尚未接该 provider |
| 同一官方容器的 QEMU/固件参数 | 新增 `scripts/probe_native_qemu.py`，独立 overlay、TCG、user forwarding、QMP 与限时清理；不改 upstream tracked 文件 | 3 次 controller 成功，约 120 秒可启动；原始 base SHA 前后相同 |
| pinned `scripts/bootstrap_vm_server.sh` 的公开提权流程 | 可选 `--prepare-x11` 仅在私有 overlay 设置 GDM，再 reset 一次；原始 ledger 不上传，导出脱敏该 payload | 第二次 GUI 宏仍超时；第三次 headless 不用此选项，未将它宣称为必要修复 |
| `CLI/run_cli.py:420` snap runtime | 固定 `trusted_headless_probe.py` + `--native-mode cmd`，复用 PATH/PYTHONPATH/LD_LIBRARY_PATH，去除显示变量；不改 HOME、无 agent shell | FreeCADCmd 1.1.0 实测 Body/Sketch/Pad、参数修改与保存重开；不是正式 TypedWorker 验收 |
| GUI 宏结果未知 | 前两次宏仅启动一次；第三次使用新 clone 和固定 headless 脚本，输出路径嵌入部署内容，避免依赖 GUI 环境变量转发 | GUI 宏根因仍未知；headless PASS 单列，不作为 GUI 同步证据 |
| 环境协议与阶段 gate | 当前 baseline 入口仍要求参考环境，原生 QEMU 不具备完整 runner 生命周期；新增文档定义无 KVM 后续适配 | 不手改 stage PASS；GUI-only、CLI、Hybrid 和 TCG 环境分开报告，真实模型任务/pair 仍为 0 |

## 2026-10-19 GUI 修复与真实小批接入

本节是后续状态，覆盖上文“尚未接入 baseline runner”“本轮没有凭证”“GUI 仅 headless 成功”等历史限制。逐次证据见 [BASELINE_RUNTIME_SMOKE](BASELINE_RUNTIME_SMOKE.md)，保留原失败记录。

| pinned 来源或研究边界 | 本轮最小适配 | 影响与验证 |
| --- | --- | --- |
| `desktop_env/desktop_env.py` 的 factory、reset/start/close | 外部注入 `NativeQemuProvider`，独立 overlay、资产 SHA、loopback controller、QMP 与限时清理；内部保留 docker 名称以兼容初始化分支，manifest 明示 native QEMU/TCG | 没有伪造 RAM snapshot；reset 丢弃旧盘并重启。空 GUI 的官方 DesktopEnv reset/action/close 已实测通过；参考硬件 gate 不改 |
| `desktop_env/evaluators/{metrics,getters}/__init__.py` | 从原导出表延迟加载原函数，不 eager 导入无关 Office/OCR 依赖 | 无 metric/getter 实现或期望规则替换；同一原函数身份经单测确认，CLI 原始脚本 dry-run 通过；未声称完整上游 sync |
| snap FreeCAD GUI 启动 | 直接运行同一 snap ELF，沿用其 Python/库环境；固定宏输出路径，保留 HOME；私有 overlay 禁用 autostart，ack 后核验单实例 | 可信 GUI 保存重开和参数修改通过；旧超时唯一根因未确定。001 双实例验收被新 gate 拒绝，002 序列化失败保留，003 完整通过 |
| `desktop_env/controllers/python.py`、CLI 的一次 `/execute` closure | GUI 改走持久化 TerminalBridge；CLI 在原 closure 外记录同一 HTTP payload 的一次派发；不确定结果停机隔离，环境 setup 外层尝试次数为 1 | 不自动重试非幂等变更；CLI prompt/tools/parser、GUI 原始 parser 保留，实际派发 JSONL 可追溯 |
| `CLI/run_cli.py` 默认 EMPTY key 和 GUI 兼容服务配置 | 本项目从所选环境变量或 ignored dotenv 接 endpoint/model/key，可信 SDK constructor 注入认证；不把 key 放入 argv | HTTP mock 已验证实际 Authorization 和 token clamp；真实服务参数只留 ignored results，公开副本脱敏 |
| SDK 默认重试与按 launch 预算 | SDK 零重试，共享 SQLite 整批账本；错误请求保留未知 token 预留，进程崩溃留下未决派发时拒绝继续；模型 wall 从首次请求开始，OS/GUI 启动另限时 | 批次总 15 次 / 16000 输出不重置；runner 整进程 1800 秒，超时杀本轮进程组。费用未知不用 0；原始错误类、usage 和 ledger 状态保留 |
| `baseline/Qwen3-6/adapter.py` 与 CLI thinking flags | 用户指定开源多模态 Qwen3；服务列出 `qwen3.5-35b-a3b`。GUI 复用原 Qwen3-6 adapter，think_level=none；CLI 发 chat_template_kwargs，thinking=false；图片 probe 同配置 | Qwen3.5 图片接口实测成功；这是复用 adapter 的版本适配，不改原 prompt/parser 实现。服务别名不证明后端权重身份；有限 smoke 与论文模型/推理设置分开 |
| 早期 GPT endpoint HTTP 500 | 用户改选 Qwen 后显式记录配置 correction，再恢复同一账本；未重发 GPT 请求 | 失败 1 次、usage unknown 与 128-token 预留仍占用；额外 Qwen probe 1 次，CLI 按整批剩余 calls 收紧，不能开启第二本账本 |
| GUI 录制与 600 秒模型时限 | 关闭视频，保留 screenshot/traj/runtime/evaluation；两题独立 launch，避免第二次冷启动耗尽同一 launch 的模型时窗 | TCG 效率不与参考环境比较；不是 GUI 25-turn 或 full-200 成绩 |
| `run_single_example`/CLI 错误时的上游 0 分 fallback | 仅在离线 `baseline_results` 汇总时读取 error/usage/circuit，保留 upstream_raw_score；运行故障的 strict=null + reason | 不改上游 result 或评分器。真实未通过可为 strict=0；没有 artifact 不用可信探针/fixture 补齐，ZIP 结构不冒充原生重开验证 |

正式 ACTC 的 TypedWorker、GUI 主线程桥、same-S0 和双 VM 隔离仍未因这些基础设施 PASS 而验收。真实 pair 数继续为 0；24-pair pilot、full-200、训练与 veRL 未启动。

`CLI/run_cli.py:100–102` 对 results-dir 有 CLI_ROOT 边界限制。第一次 live CLI 参数解析被拒绝（0 次模型生成、0 次 VM 启动）；`cad_cf.baseline` 改为先在 upstream `CLI/results/actc/<run_id>` 保存，进程结束后原样复制到本项目 `results/official_cli/<run_id>`。没有用 symlink 绕过检查，没有改上游安全边界；另拒绝已存在的 CLI run ID，防止上游默认 resume 混入历史结果。新路径经实际原 CLI dry-run 与边界回归检查通过，失败 `_001` 不覆盖，继续使用 `_002`。

## 单题续跑与官方sh适配

用户后续授权继续跑至模型任务成功。新增显式campaign配置；首批15次账本不变，续跑50次上限批实际42次，另有GUI诊断与恢复预算，全部保留。原账本constructor上限不符时未释放SQLite锁的问题已修复。共享reserve拒绝会打开当前APIGate并写budget_rejected，避免被原adapter的WAIT fallback误报成完整模型测量。

pinned `baseline/Qwen3-6/experiment_qwen3_6.sh` 的100步、trajectory10、sleep0.3和think none已核对。它引用的`test_rest.json`在该commit缺失，且不透传`"$@"`；vLLM sh固定NVIDIA GPU3、CLI wave sh同时启动四个模型与50题。本机复用同一Python入口与现有服务，改用单题清单、TCG生命周期和受限预算，未执行GPU服务脚本或整批任务。模型由服务Qwen3.5改为对应的Qwen3.6别名，模型、预算同时变化，不能归因单一改动。

原Qwen adapter要求像素，服务在公开空GUI截图探针上仍输出0..1000位置。新增显式normalized1000合同及AST转换，仅缩放绝对鼠标x/y，保留相对位移、scroll数量和键盘操作；原始与实际像素动作均记录。这一prompt后缀差异单列，不能称原GUI协议完全未变；不提供按钮位置或建模步骤。

可选空视图预热创建无对象临时文档、渲染后关闭，核对空文档集。GUI100的宏ack成功但欢迎页仍不响应，50次请求后停止计费，原循环余下为WAIT。不能据此确认唯一根因，也不能将raw score=0当成有效完整100步结果；离线collector据external_stop.json输出strict=null。恢复运行在新VM显式关闭预热，最多50次，两次实际生成合计不超过100。

CLI官方strict=1.0与工程审计FAIL并列保留。独立审计器先后出现stdout缺失、movePoint不可用、漏Invalid状态三类问题；原记录不覆写，修正分类器并保留review。所有参数编辑只在独立VM内的内存副本，原文件SHA不变。工程自检未读取expected/reference，也没有给在线模型反馈评分或审计结果。

撤掉预热的`success_gui_qwen36_recovery_001`在6次生成后因坐标合同违例结束：前轮normalized `(805,283)`执行为pixel `(1546,306)`；第6轮模型直接输出后者，转换器拒绝执行。pinned `predict → _remember_turn → _trajectory_prompt_context`会同时把原始model_action与实际pixel executed_action放入下一轮prompt，形成混合单位历史。该工程缺陷已在协议v2修正：在线history的两类action统一以normalized单位表示，返回response和实际JSONL保留原始值、pixel执行值及显式coordinate_mapping元数据。未猜单位、未双重缩放或放宽越界检查。使用真实pinned agent的无网络两轮测试验证下一轮prompt不再含pixel action，执行返回值仍为正确pixel，退出后恢复所有monkeypatch。

后续`success_gui_qwen36_history_001`复用同一recovery账本，6次请求不清零，自动将新run上限收紧至剩余44次；环境仍为全新overlay、无预热。这个历史字段呈现差异与v1结果分别报告，不改pinned tracked源码或任务答案。

## 最终续跑与原生验收

35B/v2的44轮和122B/v2的35轮GUI都未保存，官方strict=0。更大服务模型未解决本轮平面选择；平面列表的展开状态、输入送达、Qt事件循环尚未单独诊断，不将失败唯一归因于模型或TCG。最终代码又补齐scroll位置参数缩放与重复坐标拒绝；各模型run的source_snapshot保存首次请求前的实际实现，不能把之后的小修追溯算进此前实验。

122B CLI使用success账本原50次上限中的剩余8次，官方strict=1.0、1869输出tokens，termination=turn_limit。独立无模型VM审计其原文件，重算、重开、类型树和可编辑性通过，原文件SHA不变；没有修复模型产物。其原生Sketch没有Body、未完全约束，均不据此否定原生参数化结构。Qwen3.6原文件的Invalid仍为FAIL，不能由122B成功覆盖。

运行时基于ea2a4b1父提交且工作区有改动，每个run首次模型请求前保存36个cad_cf源文件及SHA。后续交付提交含审计器和归档修正，不声称是模型当时运行的干净提交。完整JSONL保留，公开执行SQLite仅导出payload SHA与state，避免以base64上传FCStd；原始SQLite与二进制文件仍留本地。

累计含探针201次生成、10个attempt、8个有效评估episode；不同模型/预算/坐标协议与重复任务不合并估计成功率。sketch-061用于调试与模型选择，不充当未见held-out结果。下一阶段为无模型GUI诊断、正式worker同步和same-S0隔离验收，见`docs/NEXT_ACTC_VALIDATION.md`；真实pairs=0，参考gate与P3/P4未放行。
