请接手GUILab，继续CADWorld ACTC的受限实验。

先读AGENTS.md、HANDOFF.md、reports/GUI_GROUNDING_20261020.md、reports/GUI_VALIDATION_20261020.md、reports/REPRO_STATUS.md、handoff.json和SPEC.md。upstream固定e5d0ebab8bd28da6e98c68c61db05747d1647f7b，不重新调研论文或更换benchmark。

截至2026-10-20，controls007通过GUI创建Body/XY空Sketch、保存关闭重开。最近122B GUI任务25次生成、2328输出tokens，官方strict=0、no_output_file，无API错误。随后6次固定截图定位校准已完成：pixels组0/3、normalized1000组2/3；pixels原始值事后按1000换算为3/3，仅作单位假设，未执行点击。代码和标注事前冻结于6caebeb，6次用量14825输入/473输出tokens，剩余0。累计232次生成、11个baseline attempt、9个有效评估episode、2个不同任务，另记本轮诊断run和6条预测。159项项目测试通过，所有VM已停。旧6本账本SHA不变，新旧账本都保留，不重开已完成批次；默认付费仍0。

历史Qwen3.5-122B CLI sketch-061官方strict=1.0、8次生成/terminal、1869输出tokens，原生审计PASS、turn_limit结束；Qwen3.6 CLI官方1.0但原文件Invalid、工程审计FAIL。全部旧失败保留。累计已知输入806010/输出26186 tokens，初次HTTP500 usage和价格未知，完整总量与美元费null。

用户要求开源多模态Qwen3，本轮使用qwen3.6-35b-a3b与qwen3.5-122b-a10b，thinking=false。当前下一阶段不调用模型，不索取不需要的密钥；本机`.env`不随Git上传。未来GUI需要图片输入，CLI保持terminal-only。服务别名不是权重身份已核验，不下载模型。normalized1000适配改变坐标合同，须与原像素结果分开。

无预热recovery run第6轮因混合坐标单位history失败，6次请求和464输出tokens保留。协议v2统一在线历史action的normalized单位，实际pixel执行及JSONL保留；无网络两轮回归通过。后续history run使用同一本账本剩余44次，不把失败6次清零。

用户无法提供KVM，不再索取，不安装VMware。原生QEMU/TCG、官方VM、单实例空GUI的DesktopEnv闭环和可信GUI参数化保存重开已有本机证据；远程必须重新核验资产SHA和环境。参考KVM gate、正式TypedWorker/GUI bridge和same-S0双VM未验收，不能手改stages.json绕过。

用户已授权少量真实baseline并要求继续跑至模型任务成功；现在CLI单题官方与原生审计已通过，本轮生成停止。默认ENABLE_PAID_RUNS=0保留。先读最终预算快照，保留旧账本、失败、未知usage占用与累计成本，不重置或扩大已完成批次。24-pair pilot、full-200、自动下载大模型、训练、veRL均未授权。

官方sh核对已完成：GUI sh引用的test_rest.json在pinned commit缺失且不透传参数；vLLM sh固定GPU3；CLI wave sh启动四个模型与50题。复用原Python runner、prompt/tools/parser/evaluator，按报告做单题与VM生命周期最小适配，不原样启动整批脚本。

按用户最新方向优先解决模型GUI坐标定位，先读reports/GUI_GROUNDING_20261020.md和docs/NEXT_ACTC_VALIDATION.md。官方Qwen要求原图像素、actions不缩放；本轮真实响应支持当前服务仍返回normalized1000位置，原样官方pixel adapter接该服务为NO-GO。显式归一化仍有边界误差；下一项在新截图与事前冻结目标上验证坐标配置，再安排限步GUI单题。保留官方prompt、仅按1000解释输出是待验证候选，必须单列协议和预算，不能用同图事后3/3宣称已修复。不能猜单位、加固定偏移或给模型Qt控件坐标。本轮6次和此前25次均已用完，不重开旧配置或账本。

模型定位解决后，再验收正式worker/Qt bridge保存重开同步和same-S0/clone隔离。不要用可信文件补模型产物。前置通过后才考虑最多3个真实paired smoke。真实ACTC pairs仍为0，P3/P4 NO-GO。sketch-061已用于调试/选模型，不作独立held-out结果。在线agent/router/verifier不读expected/reference/evaluation，官方评分仅在episode后使用。官方GUI-only、CLI、显式适配GUI与Hybrid分开报告，不从单题推断论文成功率。

保留全部成功与失败、完整JSONL和成本，更新五份报告、交接和机器状态。/execute不自动重试，不确定写入隔离VM；费用未知用null。凭证、完整模型目录、二进制资产、编码后的FCStd与MCP缓存不上传。测试和secret检查通过后提交并推送AnnaXChun/GUILab，报告确切命令、任务、结果、阻塞和GO/NO-GO。
