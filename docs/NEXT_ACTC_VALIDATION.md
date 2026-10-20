# 下一阶段验收

截至2026-10-20，CLI单题官方与122B原生审计通过；GUI controls007也已完成Body/XY空Sketch、GUI保存关闭重开。随后25次GUI模型复测仍strict=0、无文件，后段点击落在Choose Orientation对话框外。最新见[控件验收](../reports/GUI_CONTROLS.md)与[模型复测](../reports/GUI_VALIDATION_20261020.md)。累计226次生成，151项单测通过，真实ACTC pairs=0。

实际截图与原始动作的两轮mock SDK复放已通过：当前1920×1080 PNG字节、normalized→pixel映射和history单位均符合预期，零网络、零生成。远程可先按GUI_VALIDATION的scripts/replay_gui_protocol.py命令重验归档。保留本轮模型定位失败，不用可信脚本替其完成；本地复放不验证服务端内部图像处理。下一步验证正式TypedWorker/Qt bridge同步与隔离。当前不新增模型请求，不训练router或接入veRL。

结果与成本见[单题报告](../reports/BASELINE_SUCCESS_SMOKE.md)，完整轨迹见[证据清单](../reports/evidence/baseline_success_20261019/INDEX.json)。该题反复用于调试与模型选择，不能作为独立held-out效果估计。

## GUI控件验收已通过

下方方法已在controls007完整执行，详情和失败记录见GUI_CONTROLS；不重复开启模型批次。原生GUI对象树关键字段与保存字节保持，不等于正式TypedWorker同步通过。

使用新overlay和现有官方镜像，不调用模型。保持与失败run相同的FreeCAD版本、窗口分辨率、工作台和无预热设置；只执行预先写定的GUI诊断序列，保留逐步截图、时间、活动窗口与Qt控件状态。

重点检查Select attachment面板是否展开、平面条目是否存在且可见、窗口焦点与模态弹窗、点击前后事件是否被处理。需要将“控件不存在或未展开”“输入未送达”“主线程无响应”“模型定位错误”分别取证，不能用模型reason代替诊断。

验收条件是：在新clone中通过GUI选择XY平面，创建空Sketch并退出编辑，保存后关闭重开；截图、文档对象摘要与文件状态一致。可信诊断若执行了建模，只证明基础设施，不计模型baseline成绩，也不提供给下一轮模型作为答案。失败则保留日志、明确停在哪一步，不增加模型轮数掩盖问题。

通过后已执行一次25次生成上限的GUI复测，官方strict=0，当前剩余调用为0。保留原像素协议与normalized1000 v2结果的区别；不能覆盖目录或重开已耗尽账本。本轮证据提示模型定位问题，不能靠继续加轮数替代协议核对。

## 再验收正式Typed API与同步

部署仓库现有`guest_gui_bridge`与正式TypedWorker，使用受限typed工具修改一个原生Sketch或PartDesign参数。可信固定宏通过、CLI有产物，都不能代替这项验收。

必须记录Qt主线程ack、GUI保存并关闭、API修改与recompute、保存并关闭、GUI重开后的对象摘要和新截图。比较磁盘文件与GUI内存中的目标属性；检查原生Name/TypeId、shape/solver/Invalid状态以及参数可编辑性。遇到`/execute`结果不确定就隔离clone，不重发同一变更。没有bridge ack或出现旧GUI状态，P1失败，不能进入pair。

## 最后验证same-S0双clone

先用固定候选、不调用模型完成恢复检查：冻结同一公开intent和自检契约，建立停机checkpoint，派生两份独立disk、VM和workdir。两路执行前都重算并比较canonical对象摘要、目标属性、工作台、选择状态和截图，记录checkpoint SHA。原始ZIP字节SHA或task ID相同不能单独证明same-S0。

改动A后检查B和source checkpoint均未变化，再分别执行GUI与Typed API候选。两路都经过save/close/reopen/verify，保存完整`pair.json`、JSONL、state diff、自检项及成本。故意注入一次S0不匹配或执行超时，确认得到invalid并拒绝训练导出。

P1和P2通过后，才在既定小样本范围内安排最多3个真实paired smoke。先取得≥3个合法pair并重测差异，再讨论24-valid-pair pilot的预算。目标不可验证时只给tie/invalid；标签只能来自公开契约，官方评分在episode结束后单独计算。

## GO与NO-GO

当前GO是GUI控制基础设施与离线分析，控件诊断已完成。CLI单题官方与122B原生验收通过；GUI模型任务成功、正式P1/P2、真实配对、论文成功率复现和P4训练均未通过。参考Linux/KVM gate保持原记录，用户不能提供KVM，不再索取；TCG探索环境以自己的真实证据推进，不能直接改gate为PASS。

每项完成后同步五份报告、`handoff.json`、`reports/stages.json`和本文件。默认`ENABLE_PAID_RUNS=0`保留；本轮生成已停止，已完成批次不再发请求。
