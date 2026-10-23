# 下游 Pocket 的局部信用小批

本轮在已完成的 200 题 CLI 基线之后，验证一个新的分叉边界：模型从已保存的 Pad 工程构造 Pocket，包括新草图的放置与依赖。已有 Pad 小批只有一个有效 tie，无法观察结构区分。本轮最多采两条独立原文，不为得到非 tie 追加采样。

公开任务仍为 development 的 `freecad-part-014`。原任务要求圆形 Pad、同心半径 4 mm、深度 6 mm Pocket；本研究明确增加“后续修改 Pad.Length 时 Pocket 保持位于外端”的工程子目标。这是 CLI 扩展协议，成绩与官方 terminal baseline 分开。可信 Pad 前缀由程序构建，不能把它当作模型完成的多步 episode，也不能用它证明全轨迹信用收益。

先在旧已停止磁盘的新 overlay 中恢复供应轮廓 S0，创建可信 Pad，保存关闭重开为 prospective S1。模型请求前冻结 S1 字节/native SHA、公开 intent、固定 recompute 后续代码、六个探针，以及源码和预算。原生观察只包含当前对象、参数、约束和关系；模型不接收准备阶段的可信 Pocket 代码、探针结果、检查器或官方规则。独立 XY 工程先核验 Pocket.Profile、BaseFeature、长度单位和 Placement 表达式，再用任务工程验证固定六探针。两条 AuditNote synthetic 控制应 Q=1/1、credit=0。

模型在同一 messages 下各采一次，不互看候选或反馈。构造块可选择新草图的数值放置、表达式或范围允许的 attachment；原文仅去除 JSON 封装，不改代码。现有 Pad、供应草图及其约束和放置受保护。候选每条只执行一次；后续只 recompute、保存关闭重开。六探针从 artifact 独立副本修改参数并 recompute，不重放候选或后续代码。

自然候选在两个独立 VM overlay、进程、工作目录和文档副本执行。两台 VM 均从同一已停止、SHA 固定的 S1 磁盘启动；每路执行前核对 S1 字节与 native SHA。分别保存原生文件、JSONL、一次派发账本和停止记录。源码范围检查与 VM 克隆隔离分别记录，不宣称已实现更强的 guest 用户权限 sandbox。

预算为 `configs/cli_pocket_credit_20261023.json`：两次模型请求，每次最多 2048 输出 tokens，总 4096，temperature=0.7，thinking=false，SDK retry=0，request timeout=110秒。准备最多三次原生派发（准备一次、两控制）；候选最多两次，各最多180秒，每份文件六探针。正常停止的准备快照可供本批首次采样使用，消费过的模型批次和派发目录不可恢复；不确定执行隔离并停止，不重发。默认付费开关0，已授权的本轮 sample 命令设1。

离线复用相同两条响应和观测，报告 first-sample、初始几何 Best-of-2、响应终局 Best-of-2、局部 credit 与交换 A/B 信用。所有方法拥有同一份两次生成、两路执行及探针预算；这些离线算分没有新增独立实验。tie 一律选 A，交换标签也不改变 tie。单边界局部 credit 与相同响应奖励的终局选择必须等价。旧 helper 的 shuffled 表示强制反选、在 tie 时选 B；本轮明确使用交换标签，历史文件保持。

接口拒绝、执行失败、未知、tie 分开保存。接口拒绝和无可靠 artifact 的分支质量为 null，不能记0；synthetic、development、tie 不导入训练。本轮只能判断下游工程信用能否产生有信息的自然 pair。方法增益、全轨迹奖励对照、训练效果和 held-out 成功率均为 null。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_pocket_credit.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_pocket_credit.py \
  --mode dry-run --output results/new_pocket_dry_run
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_pocket_credit.py \
  --mode prepare --source results/cli_causal_inspect_native_20261022_004 \
  --runtime-config results/cli_focus_runtime_20261021.json --output results/new_pocket_prepare
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_cli_pocket_credit.py \
  --mode sample --source results/new_pocket_prepare \
  --runtime-config results/cli_focus_runtime_20261021.json --output results/new_pocket_sample
```

历史本机路径用于 provenance。远程缺原生资产时先做 dry-run；不能凭 SHA 或公开摘要重建 S1。没有 VM/文件记录 `BLOCKED_BY_ENV`，没有模型配置记录 `BLOCKED_BY_CREDENTIALS`。首次运行结束后更新结果与交接，不重复启动以上实际消费过的目录。
