# Pilot 结果

最新 [模型代码重放](CLI_REPLAY_CREDIT_20261021.md)：第6/7轮同静态圆环的响应Q均null、数值proxy 0/1；第7轮直接赋值/人工半径公式在同原生圆环的初始proxy均1，响应Q为0/1。首轮Shape.Area绑定失败Q=0保留。8次无模型派发、6文件审计通过；这是同一开发任务的新建S0重放，历史S0不可恢复，训练样本增加0，方法优势未测量。

2026-10-21 新增三个可信 CLI fixture 的真实 FreeCAD 诊断，见 [结构信用报告](CLI_STRUCTURAL_CREDIT_20261021.md)。首轮 `[0, 0, 1]` 揭示圆环保守包围盒误判，保留后用精确 API 复测得到 `[1, 0, 1]`。同一 seed 字节与原生状态、相同 intent/续执行、进程和工作目录隔离、单次候选执行、保存重开与完整 trace 均核验通过；共用 VM，强 OS 隔离未验收。三个语义 fixture 两轮执行不增加 benchmark episode 或训练样本；相同检查器终局奖励与图记录尚未体现方法增益，RL 效果未测量。

2026-10-21 用户停止 GUI，当前 pilot 改为 CLI 开发样本采集、原生审计和清洗，见 [CLI_FOCUS_20261021](CLI_FOCUS_20261021.md)。本轮不是 ACTC pair，也不构造 GUI/API credit。旧真实 pair N=0 保留；CLI 的公开奖励与后续 RL 效果分开报告。

本轮两题 1 通过、1 失败，17 次生成、6517 输出 tokens；6 个模型文件独立原生审计，最终 11 个 CLI episode 导出 3 条 SFT。全部任务位于开发/训练侧，无独立效果估计。真实训练未启动，采集/清洗 GO、训练 NO-GO。

最新[定位校准](GUI_GROUNDING_20261020.md)新增6条真实模型预测，累计232次生成。预定pixels组0/3、normalized1000组2/3；事后单位解释独立记录。该轮无VM、无点击、无S0配对、无credit或preference标签。真实pair与差异重测仍为0，P3/P4继续NO-GO；正式TypedWorker同步和same-S0后移，优先在新截图验证坐标配置。159项项目测试通过不改变pilot验收状态。

下方为此前各轮记录。

最新[坐标协议核对](GUI_COORDINATE_AUDIT.md)仅做离线SDK对照与测试，不产生模型样本或pair。当前优先解决模型GUI定位，正式TypedWorker同步与same-S0后移；真实pair与差异重测仍为0，P3/P4继续NO-GO。

2026-10-20的GUI控件探针已完成保存关闭重开，见[GUI控件验收](GUI_CONTROLS.md)。它未运行GUI/API候选配对，不新增preference、credit或有效pair；真实pair与差异重测仍为0。后续单路GUI模型复测也不作为pair或held-out效果估计。

该单路复测现已完成：25次生成、官方strict=0、无文件、无API错误，见[模型复测](GUI_VALIDATION_20261020.md)。累计226次生成；本轮没有同S0配对或方向标签，P3/P4仍为NO-GO。

[本项目新增] 本报告由保存的 pair trace 离线生成。

真实 pair 数 N=0；有效真实 pair 数 N=0。
synthetic 单测样本 N=9，仅用于工程验证。标签分布 `{'tie': 3, 'api': 1, 'invalid': 3, 'gui': 2}`。

2026-10-16 本机新增的是无模型 VM 软件模拟检查，见 `MAC_VM_SMOKE.md`，没有新增 episode、pair 或标签。本报告的统计样本和指标不变。

2026-10-19 无 KVM FreeCADCmd 环境探针成功，前两次 GUI 宏超时；全部属于可信基础设施检查，未新增 pair、标签或模型 episode，见 `MAC_NATIVE_QEMU_SMOKE.md`。

真实 GUI/API 配对尚未运行。配对 Strict Success、有效 pair 比例、标签覆盖率和 task bootstrap 95% CI 均为 null，真实 pair 分母 N=0。后续单路模型 baseline 见 `BASELINE_RUNTIME_SMOKE.md`，不能把它们计作 ACTC pair。

原论文 GUI-only、官方 CLI 与 CADWorld-Hybrid (extended protocol) 分开报告。GO/NO-GO 需要结合阶段验收与真实差异重测。

公开任务选择与分组见 `manifests/selection_audit.csv` 和 `manifests/splits.json`。
默认最多 2 题、3 个 live pairs；24-pair pilot 尚未授权，状态 NOT_RUN_BUDGET。

| 样本 | 类型 | 有效 | 标签 | 原因 |
| --- | --- | --- | --- | --- |
| case_00_none | synthetic | True | tie | public_contract_only |
| case_01_gui_target_miss | synthetic | True | api | public_contract_only |
| case_02_different_s0 | synthetic | False | invalid | InvalidPair: different_S0: canonical state differs |
| case_03_stale_screenshot | synthetic | False | invalid | InvalidPair: different_S0: screenshot differs |
| case_04_execution_timeout | synthetic | False | invalid | ExecutionUncertain: injected /execute timeout: no replay |
| case_05_api_preservation | synthetic | True | gui | public_contract_only |
| case_06_unknown_target | synthetic | True | tie | unknown public target; no directional supervision |
| case_07_unknown_validity | synthetic | True | tie | quality evidence unavailable |
| case_08_invalid_native | synthetic | True | gui | public_contract_only |

完整指标与适用覆盖率见同名 JSON：valid_saved_artifact_rate、native_feature_tree_validity、preservation、editability probe、pair_valid_rate、label_coverage、route accuracy/regret 和分项成本。
当前无真实 pair，配对的 part/sketch、creation/edit、failure_class 与 stage funnel 均无可统计样本；单路 baseline 另行报告。

[研究假设] 真实标签能否改善路由，需要先验证原生文件恢复、双路径执行与差异重测；当前没有效果估计。

2026-10-19 后续：真实单路 baseline 已评估 3 个 episode（2 GUI + 1 CLI，2 个不同任务），strict 均为 0，无模型输出文件；15 次生成已达到首批调用上限。它们不是反事实 pairs，不生成 preference/credit，不改变本报告的真实 pair N=0、CI=null 或 P3/P4 NO-GO。

2026-10-19最终续跑：Qwen3.6 CLI sketch-061官方1.0、原生审计FAIL；Qwen3.5-122B CLI官方1.0、原生审计PASS。GUI两次v2复测仍无文件。累计10个attempt、8个有效评估episode、2个运行/诊断错误，含探针共201次生成；详见`BASELINE_SUCCESS_SMOKE.md`，各运行不是same-S0配对。sketch-061已用于调试与模型选择，不能作独立held-out效果。真实ACTC pair、有效pair、GUI/API差异重测仍为0，不能从单路成功推导路由收益，P3/P4继续NO-GO。
