# 失败案例

synthetic 行是明确注入的单测场景。真实样本 N=0，与 mock 分开统计。

| 样本 | 观察结果 | Trace |
| --- | --- | --- |
| case_01_gui_target_miss | GUI 未满足公开目标；target_progress=0，标签 api | `results/verification/case_01_gui_target_miss/trajectory.jsonl` |
| case_02_different_s0 | InvalidPair: different_S0: canonical state differs | `results/verification/case_02_different_s0/trajectory.jsonl` |
| case_03_stale_screenshot | InvalidPair: different_S0: screenshot differs | `results/verification/case_03_stale_screenshot/trajectory.jsonl` |
| case_04_execution_timeout | ExecutionUncertain: injected /execute timeout: no replay | `results/verification/case_04_execution_timeout/trajectory.jsonl` |
| case_05_api_preservation | API 改动非目标对象；preservation=0，标签 gui | `results/verification/case_05_api_preservation/trajectory.jsonl` |
| case_06_unknown_target | unknown public target; no directional supervision | `results/verification/case_06_unknown_target/trajectory.jsonl` |
| case_07_unknown_validity | quality evidence unavailable | `results/verification/case_07_unknown_validity/trajectory.jsonl` |
| case_08_invalid_native | API 原生重算失败；validity=0，保留失败证据 | `results/verification/case_08_invalid_native/trajectory.jsonl` |
