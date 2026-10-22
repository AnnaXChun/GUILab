# GUILab 交接

**2026-10-22 最新结果**：先读 [多步 CLI pilot](reports/CLI_CAUSAL_PILOT_20261022.md)、`reports/CLI_CAUSAL_STATUS.json` 和 [协议](docs/CLI_CAUSAL_CREDIT_PILOT.md)。新 runner 已实现；part-001/014 原生 S0、固定后续代码、保存重开和每题六探针通过，两对不相关 AuditNote 控制 Q=1/1、credit=0。4 次独立模型请求已完成，11268 输入/2491 输出 tokens，四条原响应均静态接口拒绝，天然候选执行为 0、有效自然 pair 为 0、credit=null。接口拒绝的代码没有实际运行，原生质量 unknown。

全部六台 VM 已停止，累计 /execute 10 次，9 complete/1 uncertain；272 项项目测试和 7 项上游 CLI 测试通过。完整模型/执行 JSONL、实际观察、拒绝、源码和预算审计见 `reports/evidence/cli_causal_pilot_20261022/INDEX.json`。旧八份账本不变；本批补采沿用原四次账本，剩余调用为 0。预检 004 通过一次独立有账本的手工 controller 准备完成，自动截图启动仍超时，不能报告为旧入口一键成功。

**接下来**：按 [通用 API 说明对照](docs/CLI_CAUSAL_API_COMPARISON.md)准备相同模型/任务/S0 的两组对照。先验证公开 Profile、Body 内 feature 创建、长度单位的说明，再冻结新实验预算与来源，不提供任务完整代码。当前多步原生管线 GO，天然结构信用、方法优势与训练 NO-GO；本轮交付不执行新采样。下方 2026-10-21 的 Torus 模型 tie 是独立历史，计数保留。

单个边界的局部差值与相同 Rresp 的终局 Best-of-2 应等价。多步可信续执行和不相关块零信用已通过，天然模型下游影响仍未观测；同奖励全轨迹 RL 与局部 credit 监督留待有足够局部标签后比较。所有自然 pair、tie、invalid 和 synthetic 控制分开记录。两任务及供应文件来源组归 development，不作 held-out；不恢复 GUI，不为 non-tie 重开账本。

**最新 CLI 模型候选已通过**：先读[接口修复结果](reports/CLI_API_GUIDED_PAIR_20261021.md)、[协议](docs/CLI_API_GUIDED_PAIR.md)和[当前状态](reports/CLI_MODEL_PAIR_STATUS.json)。通用 FreeCAD API 探针通过后，两次模型独立生成半径绑定；原响应的 JSON 围栏先被严格接口拒绝，随后显式封装适配提取原代码，恢复相同 S0 执行。A、B 均保存关闭重开并通过六个探针，Q=1/1、credit=0。原生 XML 验证为 Part::Torus 加 ExpressionEngine，模型代码字符串未编辑。

本轮 2 次模型请求、2430 输入/1147 输出 tokens、4 次 native 派发，uncertain=0；两 VM 停止，257 项项目测试和 7 项上游 CLI 测试通过，8 份旧模型账本 SHA 未变。完整模型/执行 JSONL 与失败、成功证据见 `reports/evidence/cli_api_guided_pair_20261021/INDEX.json`。此前超时、白名单拒绝和 API/表达式失败均保留；该系列累计 5 请求、9 派发，有效模型 pair 为一个 tie，原 GUI/API ACTC pair 和训练样本均为 0。

下一步冻结两个新 CLI 构造任务、任务划分与相同预算，每次新请求前捕获 S0，比较终局检查、参数干预检查与 Best-of-2。当前同 S0 模型块执行 GO，方法收益和训练 NO-GO。远程历史路径仅为 provenance，需自己的已核验 S0/runtime；不重开已结束账本，不恢复 GUI。下方模型失败段落为历史记录。

**捕获S0的模型候选已实际执行**：先读[本批报告](reports/CLI_MODEL_PAIR_20261021.md)、[协议](docs/CLI_MODEL_PAIR.md)、[状态](reports/CLI_MODEL_PAIR_STATUS.json)。S0在模型请求前保存重开，60秒首请求超时并保留2048未知预留；110秒新批返回两候选、2144输入/1283输出tokens。初始白名单拒绝B的只读hasProperty查询，复核放行后不改response，在停止捕获磁盘的新overlay恢复原S0并执行。A表达式ParserError，B当前PrimitivePy无hasProperty，均未保存artifact，pair invalid/credit=null。

本轮3次模型请求、5次native派发，原始请求/账本/拒绝/原生失败均保留，三VM停止，251项目tests/7上游CLI tests。没有自动transport重试、原模型代码修补或新增训练样本。旧7份模型账本SHA未变。下一步先冻结公开FreeCAD API/表达式说明的等预算对照再生成新代码，当前不重开本批；有效模型pair和方法优势仍NO-GO。

**2026-10-21 模型代码重放交接**：已把结构检查推进到真实 Qwen 轨迹代码，先读 [模型重放报告](reports/CLI_REPLAY_CREDIT_20261021.md)、[执行协议](docs/CLI_REPLAY_CREDIT.md)与 [机器状态](reports/CLI_REPLAY_STATUS.json)。第6/7轮代码在新建同S0静态圆环上重放，数值存储proxy为0/1，但缺半径绑定，响应Q均null。模型第7轮在原生圆环上的直接赋值初始正确、参数响应失败；人工追加公开半径公式后，保存重开及参数响应Q=1，credit=-1。原`Shape.Area`绑定失败及mock预设被真实结果推翻的记录保留。

本批8次无模型原生派发、6个文件、全部complete，两台VM已停止。231项目tests与7上游CLI tests通过。历史中间S0未保存，本批是model-sourced prospective replay，不能写成历史精确恢复；模型原文件SHA未变。人工修正候选、工程响应目标与原官方任务分开报告，新增官方episode/ACTC pair/训练样本均0。证据入口为`reports/evidence/cli_replay_credit_20261021/INDEX.json`。

下一步在新CLI任务执行候选前捕获S0，让模型提出替代代码块，冻结同intent/绑定/续执行及任务划分和预算，再做相同终局检查器、逐步验证、等预算Best-of-2与打乱信用对照。当前响应检查GO，方法增益和训练NO-GO；不重开旧账本，不直接启动RL。远程可先用`run_cli_replay_credit.py --dry-run`；真实重放无需key，但要自己的已核验VM配置。

**2026-10-21 最新验证**：用户指出普通 SFT/RL 缺少方法创新并要求继续验证，当前先看 [CLI 结构信用结果](reports/CLI_STRUCTURAL_CREDIT_20261021.md)、[执行协议](docs/CLI_STRUCTURAL_CREDIT.md)与 [机器状态](reports/CLI_STRUCTURAL_CREDIT_STATUS.json)。三个可信 fixture 已在真实 FreeCAD 完成，修正版 credit `[1, 0, 1]`；首轮包围盒误判 `[0, 0, 1]` 和全部失败保留。共 14 次单次派发，无模型调用、无不确定执行，两轮 VM 均停止，210 项项目测试与 7 项上游 CLI 测试通过。

这批只验证原生参数响应与固定续执行下的相对信用，不增加 CADWorld episode、原 ACTC pair 或训练样本。真实脚本与 `.FCStd` 类型树/状态/SHA 对应关系已独立审计。图只作记录；当前信用与同一终局检查器 Q 的差值一致，方法创新和训练仍 NO-GO。下一步冻结真实 CLI 构造块的同 intent/S0/续执行、独立任务分组和预算，再比较终局奖励、逐步验证、Best-of-2、打乱信用；不直接启动 RL。

远程先执行下方 mock 命令，真实诊断无需 API key，只需自己的已核验 native runtime 配置。每次 output 必须为新目录；历史两轮不覆盖，也不把其 fixture 导入 SFT。公开 trace 与两轮源码快照见 `reports/evidence/cli_structural_credit_20261021/INDEX.json`，原 FCStd/base64/controller 原响应不上传。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_structural_credit.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --dry-run --output results/new_structural_mock
```

**2026-10-21 当前交接**：用户停止 GUI，转向 CLI 的数据清洗、RL 和成功率改进。先读 [CLI 研究计划](docs/CLI_RESEARCH_PLAN.md)、[本轮 CLI 记录](reports/CLI_FOCUS_20261021.md)和 [CLI 数据清单](manifests/cli_dataset_20261021.json)。下方 2026-10-20 及更早段落保留为历史，不按旧 GUI 下一步执行。

本轮两题已结束：sketch-063 官方 1.0，measure-003 官方 0.0；均正常 finish，共 17 次生成、57833 输入 / 6517 输出 tokens，API 错误 0。6 个文件原生审计完成，4 个草图通过参数编辑，part-076 Invalid、圆环 editability UNAVAILABLE；所有原文件 SHA 保持。最终 11 个 CLI episode / 6 个任务导出 3 条 SFT，其他 8 条保留排除理由。数据公开副本见 `reports/evidence/cli_focus_20261021/cli_data_20261021/`，完整机器状态见 `reports/CLI_STATUS.json`。全部 VM 停止，当前批次结束，余下 3 次请求不追加。

新增 CLI 小批复用 pinned runner，一次 launch 选择至多两个任务，官方 reset 保留；TCG reset 仍会为下一题创建新的 VM overlay。配置只开放 CLI，最多 20 次生成、16000 输出 tokens。原 100 次账本已耗尽，23316 输出 tokens；不修改历史额度。任务、模型、实际消耗和审计结果以本轮报告及脱敏证据为准。

新增 `python -m cad_cf.cli_data --manifest manifests/cli_dataset_20261021.json --output results/<new-dataset>`，只做离线清洗，无模型调用。输出包括完整样本索引、quarantine、SFT 候选和排除原因。此前 9 个历史 episode 的审计前快照为 0 条 SFT；完成本轮及审计后更新为 11 个 episode、3 条 SFT。官方分数仅用于离线报告，不进入 SFT 奖励。远程可直接使用脱敏 JSONL；重跑 native audit 仍需原始 artifact 或自己生成的新文件，不能把公开 SHA 当作文件。

原生审计入口 `scripts/audit_cli_artifacts.py` 支持多次 `--artifact`，一次无模型 VM 检查多个文件，每个文件独立临时目录、一次派发、SHA 校验；不会修复模型文件。后续训练需有可训练权重、GPU、任务分组和稳定公开奖励，当前托管 API 只用于采集。暂不接 veRL，不启动 full-200。

更新：2026-10-20。仓库：[AnnaXChun/GUILab](https://github.com/AnnaXChun/GUILab)，根目录就是项目。先读本文件、[定位校准](reports/GUI_GROUNDING_20261020.md)与SPEC.md；GUI任务失败见[模型复测](reports/GUI_VALIDATION_20261020.md)，历史CLI成功见[此前续跑](reports/BASELINE_SUCCESS_SMOKE.md)，机器记录见handoff.json。历史失败不可被后续成功覆盖。

GUI控制闭环已通过：controls007在新官方base overlay中用12次单次派发操作创建Body/XY空Sketch、保存关闭重开，7071-byte文件字节不变，151项单测通过。已处理的具体问题为GNOME外部未响应弹窗、探针对话框移动后的旧坐标、30秒观察截止早于90秒阶段等待；不将这些统称为历史唯一根因。六次失败与一次PASS均已归档。

模型复测使用代码提交77d10d0和新VM，Qwen3.5-122B GUI sketch-061官方strict=0、no_output_file；25次生成、88918输入/2328输出tokens、无API错误。第15–25轮未命中Choose Orientation的OK按钮，不能把可信探针成功写成模型成功。GUI模型仍无文件，无原生文件可审计；CLI历史的官方与122B原生成功不变。

最新6次固定截图定位校准使用Qwen3.5-122B，原定pixels组0/3、normalized1000组2/3。官方pixels要求下的原始值事后按1000换算后为3/3，支持服务输出单位不匹配；这项事后检查未增加模型请求，也未执行点击，不能改判原定组或算GUI成功。详见[校准报告](reports/GUI_GROUNDING_20261020.md)与[原始证据](reports/evidence/gui_grounding_20261020/INDEX.json)。代码、预算和标注在首次请求前冻结于6caebeb。

累计232次生成、11个baseline attempt、9个有效评估episode、2个不同任务，已知输入806010/输出26186 tokens。新增校准单列为1个诊断run、6条预测；初次HTTP500未知usage与128-token占用保留，完整总量和美元总费null。全部本项目VM已停；本轮未启动VM。6次校准用量为14825输入/473输出tokens，剩余调用0，旧6本账本SHA不变。最新159项项目测试通过，此前4项官方Qwen测试通过。下一步在新截图上验证显式坐标配置，再限步复测GUI；正式worker/Qt bridge同步和same-S0双clone后移，见[验收计划](docs/NEXT_ACTC_VALIDATION.md)。真实pairs=0，P3/P4继续NO-GO。

下方详细段落保留2026-10-19的历史，不把其中201次、122 tests或“先做控件诊断”等旧状态当作当前待办。

## 已验证的结果

最新`qwen3.5-122b-a10b` CLI的`success_cli_qwen122_001`在sketch-061官方strict=1.0，8次生成/terminal、1869输出tokens，termination=turn_limit。原文件2924 bytes，SHA为`ebc2e5cbcee52bc49f0b081d67d5d3979a6e10f7205795d6945771403f47d673`；独立无模型VM原生审计PASS，重算/重开、类型树和一次性内存参数编辑通过，模型文件未改。它是原生Sketch，未完全约束，不声称agent主动finish。

Qwen3.6 CLI在`freecad-sketch-061`获得官方strict=1.0，14次生成、13次terminal、5823输出tokens；模型自行保存并重开。原CLI prompt、tools、parser、评分器与diagnostics均复用pinned源码，没有提供答案脚本或人工修复。

独立原生审计发现原文件的Sketch.State包含Invalid，Document.xml记录attachment错误。因此官方成功保留，工程质量判为FAIL，不进入有效训练数据。审计器曾有stdout未捕获、movePoint不可用、漏Invalid三次问题；保留原记录，以audit_review.json纠正旧PASS，不改模型文件。

GUI25进入绘图和保存阶段但未存盘，strict=0；预热GUI100在50次真实生成后仍停在欢迎页，主动阻断，随后WAIT均为原adapter fallback。该次strict=null，保留raw score=0，不能作为完整100步测试。撤掉预热的恢复run在第6轮因混合单位history触发越界拒绝，6次/464输出tokens保留；v2将在线history统一为normalized单位，实际pixel执行和JSONL不变。新run沿用同一本账本的剩余44次。最终消耗与终态见本轮报告。

35B/v2的44轮GUI与122B/v2的35轮GUI都strict=0、无文件，卡在Select attachment平面选择；控件展开状态与事件循环仍需独立检查。累计10个attempt、8个有效评估episode、2个运行/诊断错误，涉及2个任务；含探针201次生成，已知输入702267/输出23385 tokens，价格和初次HTTP500 usage未知。所有模型与审计VM已停止，最新122 tests、上游CLI 7 tests和原CLI适配dry-run通过。该题用于调试与选模型，不能作独立held-out成绩。

Qwen3.5首批的2 GUI + 1 CLI均为strict=0，无文件；15次请求、已知输出1369与早期HTTP500未知usage完整保留在[首批历史](reports/BASELINE_RUNTIME_SMOKE.md)。不同模型、预算与坐标合同不合并统计成功率。真实ACTC pairs仍为0。

## 环境与启动

用户无法提供KVM，不再索取，不安装VMware。Mac ARM原生QEMU/TCG已接入官方qcow2、DesktopEnv和GUI/CLI runner。单实例空GUI的reset/observe/action/observe/close、可信GUI参数化保存重开已通过；它们不是模型任务。参考Linux/KVM gate、正式TypedWorker、GUI bridge和same-S0双VM恢复尚未验收。

```bash
git clone --recurse-submodules https://github.com/AnnaXChun/GUILab.git
cd GUILab
bash scripts/bootstrap.sh --baseline
ENABLE_PAID_RUNS=0 bash scripts/test.sh
git -C vendor/CADWORLD rev-parse HEAD
git -C vendor/CADWORLD status --porcelain --untracked-files=no
```

upstream固定`e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，tracked文件不得修改。16个baseline直接依赖来自pinned lock，原CLI dry-run与7个上游测试通过；未安装完整405包或下载模型权重。

VM、固件、.env和SQLite不随Git上传。已有官方qcow2为28,310,503,424 bytes，SHA256为`edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12`；远程必须核验自己的资产，不能直接使用本机路径。按`configs/native_tcg.example.json`填写路径与SHA，重新运行`probe_baseline_env.py`取得本机验收。具体步骤见[TCG指南](docs/RUN_TCG_BASELINE.md)。

无模型检查无需API key。后续新截图模型验证只收集缺项：`CADWORLD_API_BASE_URL`、`CADWORLD_API_KEY`和准确model ID；已使用过qwen3.6-35b-a3b和qwen3.5-122b-a10b，均thinking=false。服务别名不证明权重哈希。密钥通过secret、环境变量或ignored `.env`提供，不进Git、argv或报告，不假定GitHub secret自动进入远程环境。

## 授权和预算

用户已要求少量真实实验，并追加“继续跑，直到模型任务能够成功，查看官方sh是否可复用”。默认`ENABLE_PAID_RUNS=0`保留为无配置保护，已授权命令单次设为1，无需重复请求同一范围许可。已完成的批次不能在远程重开。

5本账本请求数为15、50、50、50、36，合计201。success账本先用42次，最后CLI122用剩余8次；gui100在50次后blocked，recovery为6+44，122B专用账本为图片1+GUI35。未知usage保留128-token reservation，总token和美元费用null，不报0。不得把未消耗的blocked额度当作新实验授权。

SDK重试为0，/execute非幂等变更单次派发；timeout或不确定写入停止并隔离clone。不得清空账本、删失败或修改上限恢复额度。不启动24-pair pilot、full-200、模型下载、训练或veRL。

## 下一步和有效性边界

GUI控件诊断和本轮6次定位校准已完成。当前服务配原样官方pixel adapter为NO-GO；下一项是在新截图和事前冻结目标上验证明确坐标单位，再做限步GUI单题。已有normalized1000为2/3，事后“官方prompt加归一化解释”为待验证候选，不加固定偏移、不反馈Qt坐标。后续预算与验收条件须预先定义，不重开已耗尽配置。官方sh复用原Python入口；GUI sh引用缺失test_rest.json且不透传参数，vLLM sh固定GPU3，CLI wave sh启动四个模型和50题，不能原样启动。

P1必须部署正式guest_gui_bridge，验收Qt主线程ack、TypedWorker保存关闭重开和当前GUI刷新。之后P2才验证同一公开intent、同一S0、两个独立VM/磁盘/workdir；不能用同一base SHA或同任务ID代替S0证明，不能A后undo再B。真实pair、差异重测和训练GO门槛见stages.json，单路成功不自动放行P1–P4。

agent/router/verifier仅接公开白名单字段与当前状态。官方expected/reference/evaluation只在episode后离线评分，不回流在线模型。原论文GUI-only、CLI、显式坐标适配GUI、CADWorld-Hybrid分别报告；不把verifier或局部修复当novelty。

## 证据与提交

本轮脱敏归档位于`reports/evidence/baseline_success_20261019/`，INDEX记录原始与公开副本SHA。完整JSONL保留，截图抽样，其余本地图像哈希列入清单；执行SQLite公开导出仅含payload SHA/state，避免以base64上传原生文件。FCStd、qcow2、固件、凭证、完整模型目录和MCP诊断不提交。

继续更新reports/{REPRO_STATUS,BASELINE_REPRO,PILOT,FAILURE_CASES,DEVIATIONS}.md、机器状态和实际命令。完成适当测试、secret检查后直接提交并推送已授权仓库。scripts/verify.py固定早期Mac失败预期，不能作为通用远程验收。
