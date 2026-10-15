# 后续实验接口

[研究假设] ACTC 的证据目标是 held-out 工具 utility 与 route regret，混合接口、verifier 和局部修复不作为 novelty。

P3 真实验收前不启动训练。先验证至少 3 个隔离、可重测的真实 smoke pairs；经额外授权再尝试获取 24 valid pairs。invalid、unpaired、执行失败全部保留，所有成本同时统计。若没有非 tie 真实差异，或规则路由已等效，P4 为 NO-GO。

当前分组固定 seed=20261015，按公开任务 family 和明确给定的 precondition 来源 SHA 并集分组。完整 part/sketch 共 140 题，train/val/test=92/25/23；32 个 edit 初筛候选分布为 19/7/6。这是完整 group 优先下的近似 60/20/20。edit pool 中 sketch 仅 1 题且位于 train，val/test 的 sketch-edit 覆盖为 0，不能报告该分层的泛化效果。候选 Name/TypeId 的真实可检验性仍待 introspection。

P4 输入 `instruction_effective + canonical summary + screenshot features + frozen intent`，输出 GUI/API 概率。只用 train 的真实 valid、已知质量、non-tie pairs 训练；val 选择 confidence threshold 并冻结权重/epsilon/cost normalization；test 一次性验证，不反向调整契约或选样。`router.execute_single` 确保推理只执行一个分支，`route_metrics` 计算准确率和 task-cluster bootstrap regret。训练器接入 frozen predictor 回调，v1 不自动下载 backbone。

对照使用同一 extended protocol：G1 GUI、G2 Typed API、G3 naive、G4 rule、G5 成本匹配常规 verifier（最多一次独立重试）、G6 frozen ACTC router。G7 Best-of-2 两路成本全部计入，标为额外计算上界。G0 原始 GUI-only 与官方 unrestricted terminal CLI 单列。非幂等的网络重试始终为 0；G5 的独立新尝试必须重新建 clone 和新的执行记录。

消融固定为 no-counterfactual、no-preservation、no-editability、等成本常规验证、random、API-only；different-S0 为 invalid-pair 负控制。主指标为官方 post-hoc Strict Success 和 valid_saved_artifact_rate，结构指标带适用覆盖率。成功率差用同任务配对差和足够样本下的 McNemar；CI 按 task bootstrap，不能把同任务多 pair 当独立样本。

P5 仅在 P4 held-out regret 改善、等预算 strict 不下降且参数结构无退化后评估。先 frozen backbone + router；明确离线 off-policy credit、on-policy task reward 与额外 pair 生成成本。没有统计支持就停止大规模实验。本轮 veRL 与 RL 均 NOT_IMPLEMENTED / NOT_RUN_BUDGET。
