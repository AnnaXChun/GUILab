# 基线复现

sketch 类 63 题已全部尝试：61 题可评估，10 题官方 strict=1，2 题执行不确定。完整分母下的可核验交付率为 10/63=15.87%，已评估子集通过率为 10/61=16.39%；未知质量不设 Q=0，整类严格通过率仍为 null。52 题保存原生文件，原生审计尚未完成。与 part 类一起，共 140 题已尝试、12 题官方评分通过；全量已进入 assembly 类，最终 200 题结果仍待收集。

当前 part 类全部 77 题已尝试：70 题可评估，官方 strict=1 为 2 题，7 题运行错误。可核验交付率为 2/77=2.60%，已评估子集通过率为 2/70=2.86%；含未知质量时整类严格通过率为 null。通过题为 part-013/039；原生保存、重开和参数响应另列。全量已进入 sketch 类，200 题最终率仍待完成，详见 [实验表格](CLI_EXPERIMENTS_20261022.md)。

2026-10-22 全量 200 题 CLI 已启动，固定 Qwen3.5-122B、原 pinned terminal prompt/图像输入、20 轮及单题 16384 输出 tokens，当前统计在独立 sweep 表格；该预算与官方默认 51200 分开标注。[模型候选两路成功](CLI_MODEL_CANDIDATE_SUCCESS_20261022.md)属于固定后续代码的干预小批，不增加官方 episode。

2026-10-22 [多步 CLI 构造小批](CLI_CAUSAL_PILOT_20261022.md)属于扩展局部干预协议。两题可信原生管线和控制通过，4 条模型响应均在执行前被接口拒绝，新增官方 baseline episode 为 0。官方 terminal CLI 与 GUI-only 的历史成绩保留；本批不更新其成功率，也不把控制成功计作模型任务成功。

最新[CLI 接口修复验证](CLI_API_GUIDED_PAIR_20261021.md)取得两个原生测量候选成功、一个有效 tie 配对，Q=1/1。它使用通用 API 说明和显式 JSON 围栏适配，属于扩展测量协议。官方 terminal CLI 历史成绩、原 prompt baseline 与 GUI-only 结果分别保留；本轮新增官方 episode 为 0。

最新[模型代码块小批](CLI_MODEL_PAIR_20261021.md)使用扩展接口和capture-before-request，不是官方terminal baseline完整episode。真实两候选在FreeCAD中失败，原始错误保留；旧官方CLI得分未修改。

后续 [模型轨迹代码重放](CLI_REPLAY_CREDIT_20261021.md)只复用已有Qwen代码，没有新增模型baseline episode。新建S0重放、人工绑定修正与官方CLI成绩分开；原历史文件未变，参数响应结果不能回写官方成功率。

2026-10-21 后续 [CLI 结构信用诊断](CLI_STRUCTURAL_CREDIT_20261021.md)已完成，属于无模型的 controlled synthetic，不是新增 baseline 跑题。三组 fixture 的修正版信用 `[1, 0, 1]` 只用于原生参数响应与配对机制验证，不能计入官方 CLI 成功率。GUI-only、已有 CLI 和该诊断继续分开报告。

2026-10-21 CLI 小批已完成，GUI 停止。sketch-063 官方 strict=1.0、原生编辑通过；measure-003 官方 strict=0.0、measurement 类型或结构错误。两题正常 finish，原 prompt/tools/parser 和离线评分保持 pinned 实现。详细任务、17 次请求成本、6 文件审计及 3 条训练候选见 [CLI_FOCUS_20261021](CLI_FOCUS_20261021.md)。不同模型、重复任务和预算的历史结果不合并成正式成功率；原论文 GUI-only 全量复现仍未完成。

最新6次[固定截图定位校准](GUI_GROUNDING_20261020.md)是独立诊断，未执行GUI或CADWorld episode。pixels组0/3、normalized1000组2/3；pixels原始返回事后按1000换算为3/3，仅支持单位假设，不改原定成绩。累计232次生成，baseline仍为11个attempt、9个有效评估episode、2个不同任务，GUI任务strict仍0且无成功文件。CLI122B单题官方1.0与原生审计PASS保留；论文GUI-only与扩展协议均未完成复现。159项项目测试通过，完整请求、响应与用量已归档。

下方保留此前各轮结果及当时累计数。

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
