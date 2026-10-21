# CLI 接口修复验证

用户要求解决模型测量代码的执行失败。本轮冻结 `configs/cli_model_pair_api_guided_20261021.json`，最多两次独立生成、4096 输出 tokens、三次原生派发、1200 秒运行窗口。模型沿用 `qwen3.5-122b-a10b`，temperature=0.7、thinking=false、单请求 110 秒、SDK 重试为 0。新账本承接这次小批授权，旧超时、失败和额度保持原样。

## 同 S0 与接口说明

使用已停止的 `cli_model_pair_service_native_20261021_001` 磁盘作为只读 backing，新建 overlay。准备阶段核对原 seed 字节与 canonical state，然后在独立临时文档中验证通用 API。语法探针使用 Box，测试 PropertiesList 查询、pi、^、长度与面积单位、保存重开和原生参数响应。探针失败时不发送模型请求。

模型说明只提供这些通用接口知识，并用 `Width * Height / (1 mm^2)` 举例。说明不含圆环公式、任务答案或探针结果。两次请求使用相同 messages，第二次不接收首候选和检查反馈；模型原文保存后不改写。候选在两个独立 FreeCAD 进程、文档和工作目录中各执行一次，继续执行仅 `doc.recompute()`。六个探针包含零扰动、两个半径各 ±20% 以及 Guard 负控制；全部从保存的 artifact 副本开始，不重放模型代码。

## 结果归类

这是开发任务上的 API 说明修复验证。历史无说明候选用于定位问题；本轮结果不能估计说明带来的因果增益。严格等预算对照需要另行冻结新采样分组。有效的 Q=1/1 配对属于 tie，保留完整记录，训练 eligibility 为 false。方法收益和训练效果需要独立任务验证。

运行命令使用新的输出目录，默认付费开关为 0，仅有界实测命令单次设置 1。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_model_pair.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_guided_cli_model_pair.py \
  --dry-run --output results/cli_model_pair_api_guided_mock_20261021_001
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_guided_cli_model_pair.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_model_pair_api_guided_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_guided_cli_model_pair.py \
  --run results/cli_model_pair_api_guided_native_20261021_001
```
