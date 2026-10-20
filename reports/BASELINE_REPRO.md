# 基线复现

已按固定源码核对[GUI坐标协议](GUI_COORDINATE_AUDIT.md)：官方Qwen要求原图像素并原样执行，最近normalized1000 v2属于扩展协议。现有旧响应按两种解释都未命中按钮；离线对照通过不代表模型定位或任务成功。本轮0次真实调用，项目154项、官方Qwen 4项测试通过，优先继续GUI定位。

2026-10-20新增[GUI控件验收](GUI_CONTROLS.md)：`controls007`完成12次单次派发的GUI操作，Body/XY空Sketch、保存关闭重开通过。7071-byte探针文件不计模型产物。代码已冻结于`77d10d0`，151项单测通过；正式模型GUI复测使用新的官方原始base overlay，结果与该可信探针分开统计。

本轮[GUI单题复测](GUI_VALIDATION_20261020.md)已完成有效官方评估，strict=0、no_output_file；25次生成、88918输入/2328输出tokens，API错误0。模型从第15轮起反复未命中Choose Orientation的OK按钮，没有产物可做原生审计。累计226次生成、11个attempt、9个有效评估episode，全部VM已停；旧201次与旧失败不覆写。GUI控制能力通过，模型GUI任务仍未成功，真实pairs=0。

复用 [CADWorld](https://github.com/Zdong104/CADWORLD) 的 pinned commit `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，不修改上游tracked文件。Mac ARM原生QEMU/TCG已接入原GUI/CLI runner；最新结果、成本和命令见 [单题续跑](BASELINE_SUCCESS_SMOKE.md)，脚本核对见 [UPSTREAM_SH_REUSE](UPSTREAM_SH_REUSE.md)。限定单题结果不能声称复现论文full-200或17.5%。

Qwen3.6 CLI `success_cli_qwen36_001` 已获得官方strict=1.0，14次生成、13次terminal、5823输出tokens，保存原生Body/Sketch/LineSegment。独立审计发现原文件Sketch.Invalid和attachment错误，因此官方任务成功与工程质量通过分开。模型文件未修复，官方评分器未修改，不进入有效训练数据。

最新`success_cli_qwen122_001`使用`qwen3.5-122b-a10b`，8次生成/terminal、1869输出tokens，官方strict=1.0，模型保存的2924-byte文件通过独立原生重算、关闭重开、类型树恢复和参数编辑审计。agent以turn_limit结束，不能写作finish。35B/v2的44轮GUI和122B/v2的35轮GUI都strict=0、无文件，仍卡在平面选择。

累计10个attempt中8个有效评估、2个运行/诊断错误；涉及2个任务，含探针共201次生成，已知输入702267/输出23385 tokens，价格和初次HTTP500 usage未知。不是201题，也不能合并估计成功率。下一步见[下一阶段验收](../docs/NEXT_ACTC_VALIDATION.md)；当前模型请求停止，真实pairs=0。

GUI `success_gui_qwen36_001` 的25轮未保存；`success_gui_qwen36_100_001` 的空白预热ack成功，但50次真实模型点击后欢迎页仍不响应，主动阻断后原adapter以WAIT结束循环。该次按诊断中止记录，strict=null，保留upstream_raw_score=0；不能当完整100次模型决策的成绩。撤掉预热的独立复测单列。新增normalized1000适配改变坐标合同，不能和原像素prompt合并成同一设置的成功率。

原论文GUI-only、官方CLI、加入显式坐标适配的GUI、CADWorld-Hybrid分别报告。真实ACTC pairs仍为0；本轮两个baseline没有same-S0恢复证明，不能用任务ID相同冒充pair。

## 首批历史结果

以下为Qwen3.5首批，原始证据见 [BASELINE_RUNTIME_SMOKE](BASELINE_RUNTIME_SMOKE.md)。其15次调用、失败和预算不因后续用户授权而删除或重置。

## 协议与模型

| 协议 | 本批设置 | 与论文/扩展的关系 |
| --- | --- | --- |
| 官方 GUI-only 代码，TCG 探索环境 | sketch-061、part-076，各最多 3 turns / 每次 512 输出 tokens；保留原 `Use GUI,` instruction；不录视频，保存截图/轨迹 | 复用原 prompt、parser、action/evaluation/diagnostics；使用用户选择的 Qwen3.5，不是原论文同模型同硬件成绩 |
| 官方 CLI terminal-only 代码，TCG 探索环境 | sketch-061；同一 Qwen3.5；只用 terminal，不提供运行时桌面截图；本批最多剩 7 次生成/terminal calls | 原 CLI prompt/tools/parser 与 `/execute` closure；SDK 认证和一次派发由外层保护，单独报告 |
| CADWorld-Hybrid (extended protocol) | 9 个 synthetic case；真实 pair N=0 | 不计入官方 baseline 的任务或成功率，未运行真实扩展协议 |

模型为服务实际列出的 `qwen3.5-35b-a3b`，用户要求开源多模态 Qwen3。图片验证真实成功，返回 `FREECAD`，usage 可计量。GUI 复用 pinned Qwen3-6 adapter，thinking=false；CLI 使用原 `--send-chat-template-kwargs` 并关闭 thinking。服务返回别名不等于权重身份已验证。模型的输入和工具观察不同，不能假称 GUI/CLI observation budget 完全相同。

## 环境接入已验证的范围

原始 CLI 7 个单测重跑通过。CLI 原始 dry-run 在安装受限 baseline 依赖、延迟导入原 registry 后通过；旧缺 dotenv 的失败仍保留。16 个 baseline 直接版本来自 pinned lock，未执行全部 405 个官方包的完整 sync，也未下载模型或 OCR 权重。

真实 DesktopEnv 单实例空 GUI 的 reset/observe/action/observe/close 已通过。可信 GUI 宏可建立 Body/Sketch/Pad、参数修改并保存关闭重开两次；它没有模型任务 instruction，不能计为 baseline artifact 或成绩。正式 ACTC 的 TypedWorker、GUI 主线程桥与同 S0 双 VM 尚待验收。

所有模型请求都进入同一本整批账本，SDK 重试为 0。失败请求计次数；未知 usage 保留占用，不报成 0。GUI 的 `/execute` 和 CLI 原一次派发外层均持久化记录，不确定结果隔离停机。镜像缺失不会静默下载；每次独立 overlay，原 base SHA 单独核验。GUI 两题分开 launch，避免第二次冷启动占用前一 launch 的 600 秒模型 gate。

上游 GUI/CLI 在运行错误时可能写 fallback 0，离线 `cad_cf.baseline_results` 保留原分数，但对 error.json、API error 或 circuit 打开输出 strict=null + reason。有效评估的 strict=0 保留为真实任务未通过。没有原生文件就报告缺失，不补 fixture、reference 或可信探针文件；ZIP 完整性不等于 FreeCAD 可重开或参数化结构已验收。

逐次失败与分母、模型 token、保存状态和阶段 funnel 以本批归档为准。官方 expected/reference 只供 episode 后的原评分与 diagnostics，不输入 agent、router 或 self-verifier。真实 pair 继续为 0，P3/P4 为 NO-GO。

## 本批实测

| 协议 | 真实 episode / 不同任务 | strict | 保存的模型文件 | 失败原因 |
| --- | --- | --- | --- | --- |
| GUI-only / TCG / Qwen3.5 | 2 / 2 | 0、0 | 0 | 连续点击错误位置，欢迎页未关闭；`no_output_file` |
| CLI-only / TCG / Qwen3.5 | 1 / 1 | 0 | 0 | 7 次终端脚本返回已知 API 用法错误，turn_limit；`no_output_file` |
| CADWorld-Hybrid | 0 / 0 | null | 0 | 未运行真实 pair |

共有 3 个有效评估 episode、2 个不同任务；不是 3 个独立任务，不能把 CLI 7 个工具错误当成 7 个 episode。15 次生成上限已用完，已知输出 1369 tokens，另有初次 GPT 500 的未知 usage 和 128-token 保守占用。正式任务 artifact 为 0；可信圆柱文件只证明基础设施。

首批历史结论：运行链路跑通，但这3个模型episode都未成功。后续CLI单题官方与122B原生验收已通过，见本报告开头；首批结果不覆写。论文成绩尚未复现，当前不再发出生成请求。
