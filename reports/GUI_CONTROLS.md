# GUI 控件验收

2026-10-20，按用户“继续解决GUI的问题”执行。最终controls007为`PASS_GUI_CONTROL_CYCLE`：12次GUI动作均单次派发，完成空文档、Body、XY空Sketch、退出编辑、保存、关闭、重开。关键对象树字段一致，7071-byte原文件重开后字节不变，SHA256为`d04da8e1d5c8e95101c3fb636d0e28de5c7d4093e97aad28e43c59a6024524b1`。

所有控件探针均不调用模型，不计作 CADWorld episode、模型产物或 ACTC pair。七次探针VM均已停止。机器摘要见[summary.json](evidence/gui_controls_20261020/gui_controls_20261020_summary/summary.json)，完整JSONL、状态与截图见[证据清单](evidence/gui_controls_20261020/INDEX.json)，可直接查看[GUI重开截图](evidence/gui_controls_20261020/gui_controls_native_20261020_007/reopen.png)。模型任务复测单独记录。

## 已观察的问题

`gui_controls_native_20261020_004/new_document.png`显示 GNOME 的“FreeCAD is not responding”对话框覆盖窗口。此时只读 Qt 观察器仍能响应，心跳最终增至196，但单次 New Body 点击后文档仍为空，90秒状态等待失败。Qt 的 activeModalWidget 为 null，不能据此认定桌面没有外部弹窗。该轮不重发点击，自动停止 VM。

后续005的启动响应确认原 `org.gnome.mutter check-alive-timeout`为`uint32 5000`。新增显式`gui_alive_timeout_ms=600000`，只修改新建 overlay 中用户会话的桌面判定时间，并读回核对；默认 null 保留原设置。应用操作仍受90秒状态等待、600秒启动和1800秒探针总时限约束。不能把延长桌面判定时间写作应用不可能卡住，也不能据此断言历史模型失败只有一个根因。

## 无模型尝试

| 运行 | 实际结果 | 边界 |
| --- | --- | --- |
| controls001 | controller就绪、Cocoa窗口长期黑屏、宏无ack；发现空autostart实例与受控实例并存，验证argv后清理空实例，随后人工中止 | 不是600秒宏超时；Cocoa根因未证实 |
| controls002 | GUI与Qt观察器成功；首次HTTP截图20秒超时，原型driver停机 | 保留响应和最终欢迎页截图 |
| controls003 | 以002已停机overlay派生诊断clone；完成XY平面选择并进入Sketch编辑；原型先后遇NULL Shape检查故障和过早观察后的重复Body | 暖盘诊断，不作为benchmark初态；重复Body文件保留，不算模型产物 |
| controls003干净文档 | GUI创建一个Body和一个空Sketch，官方HTTP截图可见Sketch编辑；尚未保存重开时driver到1800秒停机 | 停机后一次收尾连接拒绝，记uncertain，未重发 |
| controls004 | 官方原始base的新overlay；新建文档后外部未响应弹窗，New Body状态等待超时 | 原始失败与单次派发记录保留 |
| controls005 | 新overlay，显式600秒GNOME判定时间；Body/XY Sketch、退出编辑、GUI保存与关闭成功；重开时输入框移动，旧坐标未命中文件名栏，状态等待失败 | GUI保存的文件保留，未重发；整轮FAIL，不能报完整重开成功 |
| controls006 | 新overlay，布局屏障下完成Body与XY选择；confirm_xy后Qt观察器30秒未返回，停机画面仍显示Recompute | 观察超时，不冒称90秒完整阶段失败或死锁；不重发 |
| controls007 | 新overlay，90秒观察等待与布局屏障下完成全部12次GUI动作，保存关闭重开通过 | PASS_GUI_CONTROL_CYCLE；关键对象树与文件字节保持，0模型调用、0 pair |

## 验收方法

固定只读宏检查当前PID、Qt心跳、控件几何、文档对象树和Invalid/Error；不通过 FreeCAD API 创建、编辑或保存CAD。CAD操作全部由PyAutoGUI完成：关闭欢迎页、新建文档、Body、XY空Sketch、退出编辑、保存、关闭、重开。每次GUI动作只派发一次，之后仅轮询状态；重复文档、Body或Sketch立即失败。

GUI启动先核验并清理已排队的空自动实例，再等待宏ack，最后再次核验单实例。ack PID必须与启动PID相同。窗口最大化后记录几何，避免Done按钮被裁出屏幕。截图仍来自官方HTTP接口，没有替换为QMP输入，也没有向模型提供控件坐标。

controls005的`state_0027.json`记录文件名栏y=675，`state_0029.json`及后续为y=715，实际点击仍为旧中心(968,688)，最终栏内文本为空。新屏障要求相邻布局稳定、模态窗口已active/exposed，并在官方截图后重新观察；若布局变化，只重复只读观察与截图，不重放GUI动作。回归测试模拟截图期间对话框移动，验证返回新坐标且动作只执行一次。该屏障属于可信探针，没有加入模型baseline，也没有将Qt控件信息提供给模型。

controls006暴露了观察器内部30秒截止早于90秒阶段等待的问题。新观察器将同一个只读请求的等待统一到90秒，并受1800秒总时限约束；没有重新派发CAD动作。40秒迟到ack的离线测试验证只提交一次观察请求。该改动不能把006改判成功。

## 已执行命令

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_gui_controls.py \
  --config results/gui_controls_20261020_004/runtime_config.json \
  --output results/gui_controls_native_20261020_004
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_gui_controls.py \
  --config results/gui_controls_20261020_005/runtime_config.json \
  --output results/gui_controls_native_20261020_005
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_gui_controls.py \
  --config results/gui_controls_20261020_006/runtime_config.json \
  --output results/gui_controls_native_20261020_006
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_gui_controls.py \
  --config results/gui_controls_20261020_007/runtime_config.json \
  --output results/gui_controls_native_20261020_007
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
```

最新全量单测151 passed，日志为`results/gui_controls_20261020_007/project_tests.log`。实现已冻结于`77d10d070757fcaebe6f7aca0783fe89849dd75d`；源码SHA与该提交一致，提交创建在探针完成后、模型复测启动前。MCP本地fast索引与detect_changes已执行；脚本、运行产物和Markdown不在该索引的源码覆盖范围，直接按精确文件核对。

模型复测计划的dry-run通过：sketch-061、Qwen3.5-122B、normalized1000 v2、最多25次生成/16000输出tokens、动作后等待5秒。正式TypedWorker/GUI bridge同步、same-S0双clone和真实pair均未验收。可信探针使用0.7秒鼠标停留；模型baseline未加入这个控制序列或Qt坐标反馈，不能仅据探针PASS断言原模型操作已成功。

模型复测终态见[GUI单题复测](GUI_VALIDATION_20261020.md)。[交付检查](evidence/gui_delivery_20261020/INDEX.json)保留151项单测日志、公开归档离线复放和终端摘要；625个实验归档文件哈希通过、本地链接缺失0。已显式复读数字、归属和结论，并对新增中文行机械扫描：半角标点、机械编号标题、元话语、对比句式命中均0，代码与URL按技能规则豁免。
