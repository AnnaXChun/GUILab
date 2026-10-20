# GUI 坐标协议核对

后续更新：本文末尾建议的6次真实定位校准已执行，见[GUI定位校准](GUI_GROUNDING_20261020.md)。原定pixels组0/3、normalized1000组2/3；pixels原始响应事后按1000换算为3/3，提供了此前缺少的单位不一致证据。本页保留校准前的源码核对与当时判断；下文“尚未执行”仅指当时状态，当前累计232次生成。

2026-10-20，按用户要求检查固定版本的官方实现。结论：**官方 Qwen adapter 使用原图像素坐标，没有 normalized1000 换算；最近一轮模型实验使用的是本项目额外定义的 normalized1000 v2 协议。** 本地乘法符合这个额外协议，但协议是否适合当前 Qwen3.5 服务尚未实测分离，不能把此前复放通过当成模型定位正确。

本轮只读取 pinned 源码、复放已归档截图与响应、运行单测。新增真实模型请求、VM 启动、CADWorld episode 和 ACTC pair 均为 0；累计生成仍为 226 次。

## 官方怎样处理坐标

固定 commit 为 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，tracked 源码未改。官方按模型分别适配，没有统一猜测单位的规则。

| 路径 | 输入与执行约定 | 固定源码 |
| --- | --- | --- |
| Qwen3.6 | prompt 要求原始截图的像素坐标；`adapt_actions` 直接返回 actions | [adapter.py](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/baseline/Qwen3-6/adapter.py#L13)，[原始测试](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/baseline/Qwen3-6/test_adapter.py#L63) |
| Holo3.1 | 将模型的 0..1000 坐标按截图宽、高分别换算为像素 | [coordinate_adapter.py](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/baseline/Holo3-1/coordinate_adapter.py#L89) |
| OpenCUA72B | 按其 smart_resize 规则推算模型坐标空间，再映回原图 | [adapter.py](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/baseline/OpenCUA-72B/adapter.py#L66) |

Qwen 的公共链路还做了以下处理。

- [`_prompt`](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/scripts/python/api_agent.py#L391)从 PNG 读取尺寸，在文本中写入 `Screenshot resolution: 1920x1080`，再拼接 Qwen 的像素坐标要求。
- [`_openai_chat_content`](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/scripts/python/api_agent.py#L633)将原 PNG 编码为 data URL；这条客户端路径没有 resize 或 crop。
- [`predict`](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/scripts/python/api_agent.py#L168)完成解析与 sanitize，再调用 provider 的 `adapt_actions`。Qwen 的实现不缩放。
- [`execute_python_command`](https://github.com/Zdong104/CADWORLD/blob/e5d0ebab8bd28da6e98c68c61db05747d1647f7b/desktop_env/controllers/python.py#L136)发送 PyAutoGUI 代码。这一方法也没有坐标缩放。本项目继续保留单次派发保护，不使用上游自动重试。

官方 Qwen3.6 README 明确说明保留 original screenshot pixels。当前服务别名为 Qwen3.5，复用官方 Qwen3.6 adapter 是已记录的版本适配，不能据此断言服务端采用相同的图像预处理。OpenCUA 的 smart_resize 也不能直接套在该服务上。

## 失败点复核

输入为真实第 24 步截图，SHA256 为 `bcfb20058d2fcb44c72f5bd6f3c40fdc442264c81651ebad50773ee7fe6159bd`。第 25 步返回的代码为 `pyautogui.click(x=258, y=561)`。

| 解释方式 | 本地执行像素 | 含义 |
| --- | --- | --- |
| 原实验 normalized1000 v2 | `(495,606)` | `round(258×1920/1000)`、`round(561×1080/1000)`，与真实执行一致 |
| 官方 Qwen 原图像素 | `(258,561)` | 相同响应不经缩放；这是离线协议对照，不是官方 prompt 下的新预测 |
| 截图中的 OK 中心 | 约 `(937,659)` | 人工只看截图定位，未传给模型；对应 normalized 约 `(488,610)` |

两种解释下，相同旧响应都没有命中 OK。第 20 步曾输出 normalized `(489,561)`，执行为 `(939,606)`，横向已接近按钮，纵向仍差约 53 像素。已有证据不能支持一个统一缩放系数可修复所有动作，也不能区分模型定位、服务端图像处理或提示协议的影响。

截图：[第 24 步](evidence/gui_validation_20261020/official_gui/gui_validation_qwen122_20261020_001/freecad-sketch-061/step_24_20261020@130728292029.png)。完整响应及执行见同目录 `traj.jsonl`。上述人工位置只用于离线解释，不是工程 verifier、任务答案或候选动作。

## 本轮实际验证

扩展 `scripts/replay_gui_protocol.py`，增加 `upstream-pixels` 和 `compare` 模式。比较使用同一真实截图和同一旧响应，各经过 pinned agent、真实 SDK 的 MockTransport、parser、adapter 与两轮 history。请求只到内存中的 mock transport，未连接模型服务。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/replay_gui_protocol.py \
  --protocol compare \
  --episode reports/evidence/gui_validation_20261020/official_gui/gui_validation_qwen122_20261020_001/freecad-sketch-061 \
  --output results/gui_coordinate_audit_20261020_001/comparison.json
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q tests/test_gui_protocol_replay.py tests/test_qwen_coordinates.py
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q vendor/CADWORLD/baseline/Qwen3-6/test_adapter.py
```

实际结果：协议对照 PASS，4 次 mock SDK completion，0 次网络与真实生成；两路发送的 PNG 字节及 1920×1080 尺寸相同。坐标专项 16 passed，项目全量 154 passed，官方 Qwen adapter 原测试 4 passed。公开对照见[comparison.json](evidence/gui_coordinate_audit_20261020/comparison.json)。重复执行须使用新 output，原证据不覆盖。

新增 SDK 测试同时覆盖小于 1000 的像素 `(937,659)` 和大于 1000 的像素 `(1615,799)`，均保持原值，并检查原图字节、尺寸提示和下一轮 history。不能靠“数值小于 1000”自动识别归一化单位。

代码检索使用已有项目的本地MCP CLI，主索引fast刷新成功；detect_changes返回修改清单，changed symbol为0，脚本与文档有目录排除，已直接核对实际源码与git diff。MCP可用、索引刷新和测试通过分别记录，不把索引结果作为正确性证明。

## 下一步

当前优先级恢复为模型 GUI 定位，正式 TypedWorker 同步后移。`cad_cf.baseline` 的默认值本来就是 `pixels`，没有需要撤销的默认行为；后续复现官方 Qwen 路径应显式使用 `--qwen-coordinates pixels`。normalized1000 保留为单独的实验协议，历史结果和账本不变。

下一轮先做固定截图的少量定位校准，再决定是否重跑完整任务：同一模型、同一张原图、相同可见目标，在官方像素和额外 normalized1000 两种要求下分别单轮预测，不提供目标坐标或 Qt 信息。建议 3 个目标各 2 种协议，总上限 6 次生成、每次 256 输出 tokens、SDK 重试 0。坐标命中只在响应完成后依据截图人工标注检查，保留全部失败和 usage。该设计尚未执行，不能用耗尽账本或旧 25 次配置重新启动。

两种协议任一种仍系统性偏移时，先核对服务端是否 resize、crop 或改变坐标参照；客户端原图字节相同不能证明服务端输入张量相同。校准通过再安排单题 GUI baseline，任务成绩继续与定位诊断分开。当前 GO 为离线协议核对；模型 GUI 成功与 ACTC 真实配对仍为 NO-GO。

交付复核已对新增中文执行机械扫描，半角标点、机械编号标题、元话语和对比句式命中均为0；20个候选提交文件的密钥模式命中0，新报告本地链接缺失0，4个JSON解析通过。已复读坐标、测试计数和实验归属，保留模型定位与服务端处理尚未分离的结论；代码和URL按技能规则豁免。
