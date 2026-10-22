# 跑通候选，再测全量 CLI

2026-10-22 用户明确要求跑通模型候选、测试全部 CLI 任务通过率并汇总实验表。该请求授权本轮全量 200 题评测，覆盖此前“小批、不启动 full-200”的范围限制。默认 `ENABLE_PAID_RUNS=0` 保留，实际已授权的新批次显式设为 1；旧账本和原响应保持不变。

先在独立文档中原生核验 Pad 创建、Profile 和单位说明，再用 `configs/cli_causal_pad_api_guided_20261022.json` 采样两题各两个独立候选，共最多四次新请求。候选仍只用公开任务和 S0，代码不修改、各执行一次；固定后续代码与每题六个参数探针沿用已核验版本。这个小批检验执行可行性，历史拒绝不能充当等预算原说明对照。原计划的八次 API 说明对照另保留，当前不借此声称提示的因果收益。

全量使用 pinned `evaluation_examples/test_all.json` 的 200 题、11 类任务及原 `CLI/run_cli.py`/`TerminalModelAgent`，保留原 prompt、图像输入和离线官方 evaluator。模型固定为 Qwen3.5-122B。推荐预算为每题最多 20 轮、每次 2048 输出 tokens、单题 16384 输出 tokens、1200 秒；全量上限 4000 请求和 3276800 输出 tokens。该设置与官方 CLI 的默认 51200 输出 tokens 分开标注。价格未配置时费用为 null，实际用量由账本和完整 JSONL 报告。

`scripts/run_cli_full_sweep.py` 默认两路并行，每题一个独立 overlay、工作目录、端口、账本与 run ID，仍保留官方 reset。每题失败与未完成任务保留。resume 仅启动原本 PENDING 的题，已启动但失联的题标为 ORPHANED_NO_REPLAY；有旧任务进程仍存活时拒绝重复启动。模型错误或 unknown usage 打开 circuit 后停止新增题，原生非幂等派发不自动重试。

汇总由 `cad_cf.cli_full_results` 离线产生 JSON、逐题 JSONL/CSV 和 `EXPERIMENT_TABLE.md`。严格通过定义为官方 score=1；部分分数保留，运行错误时上游写出的 raw score=0 单列，strict 为 unknown。全量 200 题都有可评估结果才给全量通过率；期间报告覆盖率、已评估子集通过率、错误与待完成数量。原生文件保存、重开和参数响应独立报告，不能用 ZIP 完整性冒充原生有效。

此前开发过的 sketch-061/063、measure-003、part-001/014/076 标记为已见任务；这轮全量基线不宣称 held-out 泛化。模型候选的两题属于 development，synthetic 控制、原生模型 pair 和官方 episode 分开计数。当前不训练、不下载模型权重、不接 veRL。

全量命令由候选原生成功后执行，独立新 output：

```bash
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_cli_full_sweep.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --model qwen3.5-122b-a10b --workers 2 --turns 20 --output-tokens 16384 \
  --output results/cli_full_sweep_native_20261022_001
```
