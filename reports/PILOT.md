# Pilot 结果

[本项目新增] 本报告由保存的 pair trace 离线生成。

真实 pair 数 N=0；有效真实 pair 数 N=0。
synthetic 单测样本 N=9，仅用于工程验证。标签分布 `{'tie': 3, 'api': 1, 'invalid': 3, 'gui': 2}`。

真实 GUI/API 任务均未运行。Strict Success、有效 pair 比例、标签覆盖率和 task bootstrap 95% CI 均为 null，分母 N=0。

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
当前无真实 episode，part/sketch、creation/edit、failure_class 与 stage funnel 均无可统计样本。

[研究假设] 真实标签能否改善路由，需要先验证原生文件恢复、双路径执行与差异重测；当前没有效果估计。
