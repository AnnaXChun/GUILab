# 下一阶段验收

截至2026-10-20，CLI单题官方与122B原生审计通过；GUI controls007也已完成Body/XY空Sketch、GUI保存关闭重开。随后25次GUI模型复测仍strict=0、无文件。最新6次[定位校准](../reports/GUI_GROUNDING_20261020.md)已完成：pixels组0/3、normalized1000组2/3；pixels原始值事后按1000换算为3/3，仅作单位假设。累计232次生成，159项项目测试通过，真实ACTC pairs=0。

官方Qwen使用原图像素、不缩放；normalized1000是本项目的协议扩展，源码核对见[坐标协议](../reports/GUI_COORDINATE_AUDIT.md)。本轮真实响应支持当前服务与官方像素约定不一致，但仍有边界误差，尚未验证跨截图定位或实际点击。当前优先解决模型GUI定位，正式TypedWorker同步与隔离后移；6次上限已用尽，不重开配置或旧账本，不训练router或接入veRL。

结果与成本见[单题报告](../reports/BASELINE_SUCCESS_SMOKE.md)，完整轨迹见[证据清单](../reports/evidence/baseline_success_20261019/INDEX.json)。该题反复用于调试与模型选择，不能作为独立held-out效果估计。

## 先解决模型坐标定位

使用`scripts/replay_gui_protocol.py --protocol compare`可离线对照同一旧响应在官方pixels和normalized1000 v2下的执行结果。已确认`(258,561)`分别执行为原值或`(495,606)`，都未命中截图约`(937,659)`的OK按钮；不能直接宣布删掉乘法即可修复，也不能从本地PNG一致推断服务端没有resize。

上述同图3目标、两协议的6次校准现已执行。代码、预算和离线标注在首次请求前冻结于6caebeb，14825输入/473输出tokens，无API错误。显式normalized组的Cancel点比按钮上边界高2像素，另两个点靠近边界；事后换算不更改原定0/3，也不作为第三组真实实验。

下一项先准备不同于本轮的截图，冻结目标、标注和协议，再定义少量模型调用预算。保留官方prompt但将输出按normalized1000解释，是本轮事后发现的待验证候选；若实现，必须单独命名、预先冻结，并让在线history保持同一单位。已有显式normalized1000方案也需在新截图验证。不得依照坐标数值自动猜单位、添加固定偏移或向模型反馈Qt坐标。

当前服务配原样官方pixel adapter为NO-GO；默认pixels保留，防止静默改变官方协议。新截图定位通过后再安排限步GUI单题，验收实际点击、建模与模型自行保存的原生FCStd。官方GUI-only与坐标适配GUI分开报告。正式worker与same-S0仍须独立验收，本轮校准不放行后续gate。

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
