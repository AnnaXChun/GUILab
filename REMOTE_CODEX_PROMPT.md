请接手GUILab，继续CADWorld ACTC的受限实验。

先读AGENTS.md、HANDOFF.md、reports/BASELINE_SUCCESS_SMOKE.md、reports/UPSTREAM_SH_REUSE.md、reports/REPRO_STATUS.md、handoff.json和SPEC.md。upstream固定e5d0ebab8bd28da6e98c68c61db05747d1647f7b，不重新调研论文或更换benchmark。

最新Qwen3.5-122B CLI sketch-061官方strict=1.0、8次生成/terminal、1869输出tokens，原生文件重开/重算/可编辑性审计PASS，agent以turn_limit结束。Qwen3.6 CLI也有官方1.0，但原文件Sketch.Invalid/attachment，工程审计FAIL。GUI v2两次有效复测仍无文件，官方0。全部失败与首批15次请求保留，不能用新账本重开历史批次。累计含探针201次生成、10个attempt、8个有效评估episode；价格和初次HTTP500 usage未知。

用户要求开源多模态Qwen3，本轮使用qwen3.6-35b-a3b与qwen3.5-122b-a10b，thinking=false。当前下一阶段不调用模型，不索取不需要的密钥；本机`.env`不随Git上传。未来GUI需要图片输入，CLI保持terminal-only。服务别名不是权重身份已核验，不下载模型。normalized1000适配改变坐标合同，须与原像素结果分开。

无预热recovery run第6轮因混合坐标单位history失败，6次请求和464输出tokens保留。协议v2统一在线历史action的normalized单位，实际pixel执行及JSONL保留；无网络两轮回归通过。后续history run使用同一本账本剩余44次，不把失败6次清零。

用户无法提供KVM，不再索取，不安装VMware。原生QEMU/TCG、官方VM、单实例空GUI的DesktopEnv闭环和可信GUI参数化保存重开已有本机证据；远程必须重新核验资产SHA和环境。参考KVM gate、正式TypedWorker/GUI bridge和same-S0双VM未验收，不能手改stages.json绕过。

用户已授权少量真实baseline并要求继续跑至模型任务成功；现在CLI单题官方与原生审计已通过，本轮生成停止。默认ENABLE_PAID_RUNS=0保留。先读最终预算快照，保留旧账本、失败、未知usage占用与累计成本，不重置或扩大已完成批次。24-pair pilot、full-200、自动下载大模型、训练、veRL均未授权。

官方sh核对已完成：GUI sh引用的test_rest.json在pinned commit缺失且不透传参数；vLLM sh固定GPU3；CLI wave sh启动四个模型与50题。复用原Python runner、prompt/tools/parser/evaluator，按报告做单题与VM生命周期最小适配，不原样启动整批脚本。

按docs/NEXT_ACTC_VALIDATION.md继续：先做无模型GUI平面面板/事件循环诊断，再验收P1正式worker和Qt主线程保存重开同步，之后P2验证同intent/same-S0/clone隔离。前置通过后才考虑最多3个真实paired smoke。真实ACTC pairs仍为0，P3/P4 NO-GO。sketch-061已用于调试/选模型，不作独立held-out结果。在线agent/router/verifier不读expected/reference/evaluation，官方评分仅在episode后使用。官方GUI-only、CLI、显式适配GUI与Hybrid分开报告，不从单题推断论文成功率。

保留全部成功与失败、完整JSONL和成本，更新五份报告、交接和机器状态。/execute不自动重试，不确定写入隔离VM；费用未知用null。凭证、完整模型目录、二进制资产、编码后的FCStd与MCP缓存不上传。测试和secret检查通过后提交并推送AnnaXChun/GUILab，报告确切命令、任务、结果、阻塞和GO/NO-GO。
