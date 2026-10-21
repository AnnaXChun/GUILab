# CADWorld CLI 研究计划

本文件落实 2026-10-21 用户的新方向：停止 GUI，围绕 CADWorld CLI 做数据清洗、RL 和成功率改进。`SPEC.md` 保留原 ACTC 方案，涉及 GUI/API 路由的 RQ、P1–P3 gate 和 novelty 不再作为本方向的研究主张。旧 GUI 成绩和失败仍保留，不能据此声称 ACTC 已完成。

## 当前要解决的问题

FreeCAD CLI 能创建原生参数化工程。现有失败包括 API 名称错误、草图 attachment 错误、缺失有效 feature 以及未保存文件。先逐条核查轨迹与原生 artifact，再选择改进方法；不将所有失败概括成 CLI 的能力上限。

继续复用 pinned `CLI/run_cli.py`、`CLI/terminal_agent.py`、原 terminal tools 和离线官方评分。先保留原 prompt 的基线，新增 prompt、辅助 API 文档或训练后的模型均另列设置。两个任务可在同一 runner 进程顺序执行，任务间仍执行官方 reset，当前 TCG provider 会新建 VM overlay。每个 episode 的文件、完整 JSONL、token 和终止状态独立记录；未知执行结果不重发，隔离 VM。

## 数据清洗和奖励

`python -m cad_cf.cli_data` 从显式 run manifest 生成 `episodes.jsonl`、`quarantine.jsonl`、`sft.jsonl`、`rejected_training.jsonl` 和 `summary.json`。轨迹检查涵盖工具调用关联、缺失结果、时间顺序、token 对账、边界内容和重复记录。可恢复的脚本非零退出留在轨迹中，不能把模型自己的错误和修正洗掉。

官方评分、诊断仅在 episode 后用于报告，放在 `offline_evaluation`，不作为在线模型反馈或训练奖励。SFT 候选必须来自 train 分组、正常 finish、完整原生工具对话、单一模型 artifact，且原生重开/重算、参数编辑和公开目标检查通过。未支持的任务语义、图片运输或裁剪过的请求上下文不进入 SFT。保留排除原因及 SHA，避免将官方通过但原生 Invalid 的文件导入训练。

公开目标奖励目前只支持明确给出的直线、圆和圆环测量语义，其他任务返回 null。它只解析公开 instruction 并检查原生状态，不导入 evaluator 或黄金文件。圆环测量暂只验证原生面积属性，其他合法测量表示保留 unknown，不能改判为必然失败。这些检查是基础设施，研究贡献仍需实验。

## 分阶段推进

- CLI baseline：扩充开发任务，固定模型、调用上限与 wall time，逐题报告 strict、finish、保存率、原生有效率和成本。当前小样本用于调试，不能对标论文整体成功率。
- 数据：审计成功文件，保留失败轨迹，按任务家族和前置文件来源分组。所有已用于调试和选模型的任务归开发/训练侧，建立后续完全未使用的验证与测试集。清洗前后统计都报告。
- 提升对照：先比较原 prompt 与通用 FreeCAD API 使用说明，说明只取自公开 API，不包含任务答案。按相同任务、模型和预算做比较，保留全部尝试；不得只挑通过的题计算提升。
- 训练：先做少量 SFT，再比较等采样预算的 SFT、RL 和未训练模型。只用公开目标与原生质量奖励，严格成功率在独立测试集离线计算。训练框架后续选定，先不接 veRL。

训练的必要条件是可训练的模型权重、合适 GPU、稳定 reward 和足够的不同任务。当前托管 Qwen API 只承担推理采集，不代表已经获得训练权重。没有这些条件时继续采集、清洗和奖励测试，不启动大模型下载或训练。

## 下一轮执行

本轮配置 `configs/cli_focus_20261021.json` 只开放 CLI，任务选择见 `manifests/cli_focus_20261021.json`，最多 20 次生成、16000 输出 tokens。默认 `ENABLE_PAID_RUNS=0` 继续保留；已授权的批次启动时单次设为 1。每批使用新的 run ID 和账本，历史额度不恢复。

首个真实小批结果与 native audit 完成后，依据失败类型决定下一批：优先减少错误 API 调用和原生结构失效，随后扩充任务家族。真实 RL、训练效果及总体成功率目前不作预期数值。

本轮已完成：两题 1 通过、1 失败，6 文件审计后导出 3 条 SFT，见 `reports/CLI_FOCUS_20261021.md`。下一批围绕 attachment、native feature 和测量对象，用相同模型与预算比较原 prompt 和通用 API 使用说明。资料只取自公开 FreeCAD API，不能输入任务 evaluator 或参考答案。

后续训练采集可以单独验证 Linux 容器中的 FreeCADCmd，减少 TCG 冷启动成本；这条路径不依赖 KVM。先核对 FreeCAD 版本、对象行为、任务重置和原生文件检查，通过后再作为扩展执行协议单列。当前小批仍使用官方 VM，不把容器方案写成已验证环境。
