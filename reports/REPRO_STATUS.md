# 复现状态

2026-10-22 [多步 CLI pilot](CLI_CAUSAL_PILOT_20261022.md)已完成。part-001/014 的原生 S0、固定 Pad/Pocket 续执行、保存重开和每题六探针通过，两对不相关块控制 credit=0。4 次模型请求/11268 输入/2491 输出 tokens，原响应全部静态接口拒绝；天然候选执行和有效自然 pair 为 0，质量 unknown。累计 10 次 native 派发为 9 complete/1 uncertain，六台 VM 停止，272 项项目测试/7 项上游 CLI 测试通过。原生管线 GO，天然结构信用、方法收益和训练 NO-GO，下一步见[API 说明对照](../docs/CLI_CAUSAL_API_COMPARISON.md)。本批不增加官方 baseline episode；此前 Torus 的一个 tie 单独保留。

最新[CLI 接口修复](CLI_API_GUIDED_PAIR_20261021.md)已通过：两条新模型原文在同 S0 上各执行一次，保存重开和六个参数/控制探针 Q=1/1，credit=0。原 JSON 围栏拒绝保留，显式适配只去封装。当前有效模型 pair 为一个 tie；本轮新增 2 模型请求、4 native 派发，257 项项目测试/7 项上游 CLI 测试通过，VM 均停止。官方 baseline 历史结果保持，方法收益与训练仍 NO-GO。下方模型 pair=0 是该修复前的历史记录。

最新[捕获S0模型小批](CLI_MODEL_PAIR_20261021.md)已实测：模型前保存S0，首超时保留，服务适配返回两代码；恢复原S0执行后分别ParserError/AttributeError，无artifact，credit=null。累计3模型请求/5native派发、251项目tests/7上游CLI tests，全部VM停止。pipeline失败审计通过，模型pair与方法优势NO-GO；不新增官方episode或训练样本。

最新 [模型代码重放](CLI_REPLAY_CREDIT_20261021.md)完成8次无模型派发和6文件审计，真实模型直接赋值初始正确但参数响应失败，人工半径公式保存重开后Q=1。历史S0未捕获，静态圆环缺参数绑定时响应null，Shape.Area表达式失败保留。231项目tests/7上游CLI tests通过，两台VM停止；未增加官方episode或训练样本，方法优势仍NO-GO。

2026-10-21 新增 [CLI 结构信用验证](CLI_STRUCTURAL_CREDIT_20261021.md)：三组真实 FreeCAD 受控对照完成，修正后的 credit 为 `[1, 0, 1]`，14 次无模型派发全部 complete、两轮 VM 已停止，210 项项目测试与 7 项上游 CLI 测试通过。首轮圆环包围盒检查器失败及原始 `[0, 0, 1]` 保留。当前参数响应检查 GO；方法优势与训练 NO-GO。该诊断不增加官方 baseline episode、原 ACTC pair 或 SFT 样本，具体状态见 `CLI_STRUCTURAL_CREDIT_STATUS.json`。

2026-10-21 当前主线转为 CLI 数据清洗、RL 和成功率改进，GUI 停止。最新事实见 [CLI_FOCUS_20261021](CLI_FOCUS_20261021.md)及 [CLI 研究计划](../docs/CLI_RESEARCH_PLAN.md)。本轮 sketch-063 官方 1.0 且原生编辑 PASS，measure-003 官方 0.0、参数编辑未验证；两题正常 finish、共 17 次生成。6 个文件审计完成，11 个 CLI episode 清洗后导出 3 条 SFT，183 项本地单测与 7 项 upstream CLI 测试通过，全部 VM 停止。采集和清洗 GO，真实训练 NO-GO，详见 CLI_STATUS.json。下方 GUI/ACTC 状态保留为历史，不作为 CLI 训练前置，也不改判为通过。

2026-10-20最新[定位校准](GUI_GROUNDING_20261020.md)已完成6次真实请求：预定pixels组0/3、normalized1000组2/3；pixels返回值事后按1000换算为3/3，仅作单位假设。当前服务返回值与官方像素要求不一致已有实测支持，尚未验证实际点击或跨截图定位。本轮14825输入/473输出tokens、无API错误，0次VM启动、0个新增episode，旧6本账本不变。累计232次生成，159项项目测试通过；GUI baseline仍未成功，真实pairs=0。下一步在新截图验证显式单位，再做限步GUI复测，原样官方pixel adapter接当前服务为NO-GO。

以下坐标审计、25次GUI任务和2026-10-19累计数为各轮历史记录。

最新坐标核对见[GUI坐标协议](GUI_COORDINATE_AUDIT.md)：官方Qwen保留原图像素，本项目normalized1000是额外协议。两路离线SDK对照通过，最新项目154项、官方Qwen 4项测试通过；新增真实生成与VM启动均为0。下一步优先模型GUI定位校准，正式TypedWorker与same-S0验收后移；真实pair仍为0。

2026-10-20 GUI专项：无模型控件验收`controls007`已通过，实际由GUI创建Body与XY空Sketch、保存关闭重开，关键对象树与文件字节保持；151项单测通过。随后Qwen3.5-122B GUI单题复测用满25次生成，官方strict=0、无文件，无API错误；后段点击落在Choose Orientation对话框外。详见[控件验收](GUI_CONTROLS.md)与[模型复测](GUI_VALIDATION_20261020.md)。累计226次生成，全部本项目VM停止，真实pairs=0。下方为2026-10-19的历史累计结果。

2026-10-19最终更新：Qwen3.5-122B CLI在sketch-061获得官方strict=1.0，保存的模型文件通过独立原生审计；8次生成、1869输出tokens、turn_limit结束。Qwen3.6 CLI也有官方1.0，但原文件Invalid，工程审计FAIL。GUI仍未成功，真实pairs=0。全部成功、失败和成本见[单题续跑](BASELINE_SUCCESS_SMOKE.md)，下一方向见[下一阶段验收](../docs/NEXT_ACTC_VALIDATION.md)。以下状态分别指代码、基础设施、官方任务得分或原生工程质量，不互相替代。

| 检查项 | 状态 | 证据与限制 |
| --- | --- | --- |
| pinned upstream | PASS | `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，tracked 文件未改 |
| 本项目 + baseline 受限依赖 | PASS | baseline group 的 16 个直接版本取自 pinned lock；没有下载模型权重 |
| upstream 全量依赖 | NOT_RUN | 405 包未全部安装；不能把受限依赖运行通过写成完整 sync |
| upstream CLI unittest | PASS | 本轮重新执行 7 tests |
| 原始 CLI dry-run + 延迟导入适配 | PASS | 原始 `CLI/run_cli.py --dry-run`，保留旧 dotenv 失败；未替换 metric/getter 函数 |
| 本项目单测 | PASS | 122 passed；坐标合同、续跑预算、原生Invalid审计、外部中止归类与脱敏归档回归 |
| synthetic campaign | PASS | 9 case，6 valid mock、3 invalid；不能计真实任务或 pair |
| 官方 VM/controller，TCG | PASS | 同一官方 qcow2，ARM 原生 QEMU 11.1.2，2 vCPU / 8 GiB，无 KVM |
| FreeCAD GUI 可信原生建模 | PASS_NATIVE_INFRASTRUCTURE_ONLY | FreeCAD 1.1.0；Body/Sketch/Pad、参数修改、保存关闭重开两次，形体有效；不是模型产物 |
| 官方 DesktopEnv 空 GUI 闭环 | PASS_BASELINE_INFRASTRUCTURE | 003 单实例、空文档、reset/observe/action/observe/close；001 双实例和 002 JSON 失败保留 |
| 模型服务 | PASS_IMAGE_PROBE | Qwen3.5与Qwen3.6图片验证成功，usage可计量；服务价格与权重身份未核验 |
| Qwen3.6官方CLI单题 | PASS_OFFICIAL_SCORE | sketch-061，14次生成、13次terminal、5823输出tokens，strict=1.0；不是论文全量复现 |
| Qwen3.6 CLI模型原生工程质量 | FAIL | 原文件含Sketch.Invalid与attachment错误；官方分数保留，训练导出排除 |
| Qwen3.5-122B CLI单题与原生质量 | PASS_NATIVE_ARTIFACT_AUDIT | 官方1.0；原生Sketch、重算/重开、一次性内存参数编辑通过，原文件SHA不变；非完全约束，非finish |
| GUI v2两次有效复测 | FAIL | 35B 44轮、122B 35轮，均strict=0、无文件；平面面板/事件循环尚待无模型诊断 |
| 参考 Linux x86_64/KVM 环境 | BLOCKED_BY_ENV | 用户不能提供 KVM；本机 TCG 独立记录，参考 gate 未改成 PASS |
| 正式 NativeBackend/TypedWorker/GUI bridge | BLOCKED_BY_ENV | 固定可信宏通过不等于正式模块已部署验收 |
| same-S0 双 VM 与真实 ACTC pairs | NOT_RUN | N=0；不能以单路 baseline、mock 或同 VM undo 代替 |
| GUI25及后续单题续跑 | SEE_BASELINE_SUCCESS_SMOKE | 用户追加授权，显式配置和独立历史账本；不是重开首批 |
| 24-pair pilot、full-200 | NOT_RUN_BUDGET | 未启动 |
| 凭证缺失时的移机状态 | BLOCKED_BY_CREDENTIALS | 本机服务已可用；新主机没有凭证时才使用该状态，不把它写成本机当前阻塞 |
| P4 训练 / P5 veRL | NOT_IMPLEMENTED | 接口和后续方案已交付，本轮不启动 |

[本项目新增] native QEMU provider、GUI bootstrap、endpoint/SDK guard、共享整批账本、一次派发隔离、坐标合同v2和离线审计/归档已实现。GUI agent、CLI agent、任务config、官方评分与diagnostics复用pinned实现；坐标适配差异单列。最新完整source snapshot、JSONL、失败截图与脱敏日志见`evidence/baseline_success_20261019/INDEX.json`，首批历史归档保留。

默认付费为 0；本机同一小批已有用户授权，实际命令单次设为 1。此前 GPT 图片请求 HTTP 500 继续计入额度；用户改选 Qwen3 后记录 correction 才恢复同一本账本。未知 usage 保留 128-token 占用，不能用零成本或新账本覆盖。

P1/P2 静态开发和 9 个 mock case 不代表真实阶段验收。P3 的 ≥3 个合法真实 smoke pairs、差异重测和 24 valid pairs 均未完成，P4 为 NO-GO。SPEC 的阶段门槛继续约束真实实验；TCG 的环境差异和模型差异见 `DEVIATIONS.md`。

下一步先做无模型GUI控件与事件循环诊断，再验收正式worker和GUI保存重开同步，最后验证same-S0双clone。参考环境gate未通过；TCG探索验收独立记录，不再索取KVM。不把单题成功外推为论文17.5%或full-200成绩。

历史首批最终为3个episode、2个不同任务，strict均0，无文件；15次请求，已知输入28304/输出1369，早期500的usage未知、128-token占用保留。该历史终态不能覆盖后续官方CLI成功。当前完整成本、VM清理、原生审计、测试计数与GO/NO-GO以最新续跑报告及其机器可读归档为准。参考KVM gate、正式P1/P2、真实pair N=0和P4 NO-GO均未改变。

累计10个attempt、8个有效评估episode、2个运行/诊断错误，涉及2个不同任务；包含探针在内共201次生成，已知输入702267/输出23385 tokens，美元费用null。已停止新增推理，全部模型与审计VM退出。sketch-061已用于调试与选模型，不是独立held-out结果。
