# 失败案例

最新模型候选的代码采用了通过实测的 PropertiesList 与 FreeCAD 表达式语法，但响应外层带 JSON 围栏，被原严格 JSON 解析器拒绝。原响应、JSONDecodeError 和账本保留；新增显式单围栏封装适配，只去围栏不改代码，恢复同 S0 执行后 A、B 均通过原生检查。额外文字、多个围栏或 Python 围栏仍拒绝。该失败归为响应封装不一致，详见[接口修复](CLI_API_GUIDED_PAIR_20261021.md)。

捕获S0模型小批新增：60秒API超时无usage，circuit阻断；110秒新批B的只读hasProperty被白名单遗漏拒绝，保留后最小放行；恢复原S0执行A表达式Base.ParserError，B当前PrimitivePy无hasProperty，未进入表达式调用。两原代码不修改、不假设B表达式也已解析失败，pair invalid而非Q=0/0。[详情](CLI_MODEL_PAIR_20261021.md)。

最新 [模型代码重放](CLI_REPLAY_CREDIT_20261021.md)保留四类问题：第6轮测量字符串未赋值，第7轮数值赋值在半径变化后陈旧，Shape.Area表达式保存后仍不刷新，以及单组runner完成条件写死。前两者来自真实模型片段；表达式为人工候选失败，runner由单测修正。静态圆环缺原生半径属性记unknown，历史中间S0缺失不冒充恢复。

2026-10-21 [结构信用诊断](CLI_STRUCTURAL_CREDIT_20261021.md)新增检查器失败：圆环 `Shape.BoundBox` 返回 ±7.5767454，解析值为 ±7，首轮原生参数对象也被误判 Q=0。保留源码与结果后，实测 `optimalBoundingBox(False, False)` 返回 ±7.0000001，原容差通过。修正版静态圆环/圆柱的假参数仍无法驱动几何，下游测量修改也不能消除上游故障，均保留为受控失败。单测另验证缺 runtime、缺 VM/固件资产返回 `BLOCKED_BY_ENV`，不派发、不造原生结果。

2026-10-21 当前优先分析 CLI，见 [CLI_FOCUS_20261021](CLI_FOCUS_20261021.md)。part-077 最新一次实际只有 8 轮，末轮为 `Sketcher.Horizontal` 不存在的 AttributeError，且未保存文件；此前“已跑 24 轮”的表述撤回。part-076 后续终端输出已出现原生对象无有效 shape，不能只用此前“几何正确、过程错误”的摘要解释全部重试。CLI 可以创建原生参数化对象，任务错误记录为 failure；只有真实环境或凭证问题才使用 BLOCKED_BY_ENV / BLOCKED_BY_CREDENTIALS。

新增独立审计确认 `cli_part076_2` 的 Sketch、Pad 有 Invalid，solver 失败，参数编辑 FAIL，原文件 SHA 未改。本轮 measure-003 保存了 Part::Feature，面积数值正确、文件可重开，但官方 measurement 类型或结构未通过，原生参数编辑 UNAVAILABLE。它不进入 SFT，公开目标因表示覆盖不足返回 null。历史 Qwen3.6 官方通过但原生 Invalid 的文件继续排除；8 条训练排除记录均保留，未补文件或修改原分数。

最新[定位校准](GUI_GROUNDING_20261020.md)保留6条完整响应。官方pixels要求下OK、Cancel、XY分别返回`(483,607)`、`(547,609)`、`(470,473)`，全部偏左、0/3落入预定标注；事后按1000换算为3/3，支持当前服务单位不匹配。显式normalized组Cancel执行点应为`(1048,645)`，比按钮上边界高2像素，其余两个命中也靠近边界，尚不足以稳定操作GUI。该轮未执行点击，不把事后解释当修复结果，不将历史长任务的每次失败都归为同一个原因。

校准首次离线测试出现1 failed/25 passed，原因是空history断言误判了协议后缀中的说明文字；修正断言后26项相关测试和159项全量测试通过，未改模型prompt。旧GUI任务失败和原生Invalid文件均保留，以下为各轮记录。

最新[坐标协议核对](GUI_COORDINATE_AUDIT.md)保留方向对话框失败：旧响应`(258,561)`按官方像素原样执行、或按额外normalized1000执行为`(495,606)`，均未命中约`(937,659)`的OK。没有修改历史失败、补文件或增加模型请求；当前不能把唯一根因归为换算公式或模型能力。

2026-10-20 GUI专项的新失败与处置见[GUI控件验收](GUI_CONTROLS.md)。其中controls004在新建文档后出现GNOME外部“FreeCAD未响应”弹窗，Qt心跳仍前进；单次New Body动作后状态等待失败，未重发。controls005越过平面选择并由GUI保存关闭，但重开对话框的文件名栏从y=675移到715，探针仍点击旧中心(968,688)，文件名为空，整轮FAIL。controls001人工中止、002截图超时、003观察器NULL Shape错误和重复Body均保留，不计模型episode或pair。

controls006在确认XY后被观察器内部30秒超时截断，最终画面仍显示Recompute；不能写作90秒完整阶段失败或已证实死锁。统一观察等待到90秒后，controls007完整保存关闭重开通过。006保持FAIL，原截图和JSONL不覆写；所有探针都不生成训练标签。

`gui_validation_qwen122_20261020_001`为一次有效任务失败，官方strict=0、no_output_file，25次生成且无API错误。模型先误点2D Draft，后在Choose Orientation里反复点击对话框外，未创建并保存目标。它不是宏超时，不以可信空Sketch补文件；完整证据和坐标映射见[本轮复测](GUI_VALIDATION_20261020.md)。GUI控制探针通过不能覆盖这次模型失败。

synthetic 行是明确注入的单测场景。早期报告的模型/pair 样本为 0；最新真实模型失败见末节，真实 pair 仍为 0。基础设施失败单列，不当作 Agent 任务错误。

| 样本 | 观察结果 | Trace |
| --- | --- | --- |
| case_01_gui_target_miss | GUI 未满足公开目标；target_progress=0，标签 api | `results/final_artifacts/case_01_gui_target_miss/trajectory.jsonl` |
| case_02_different_s0 | InvalidPair: different_S0: canonical state differs | `results/final_artifacts/case_02_different_s0/trajectory.jsonl` |
| case_03_stale_screenshot | InvalidPair: different_S0: screenshot differs | `results/final_artifacts/case_03_stale_screenshot/trajectory.jsonl` |
| case_04_execution_timeout | ExecutionUncertain: injected /execute timeout: no replay | `results/final_artifacts/case_04_execution_timeout/trajectory.jsonl` |
| case_05_api_preservation | API 改动非目标对象；preservation=0，标签 gui | `results/final_artifacts/case_05_api_preservation/trajectory.jsonl` |
| case_06_unknown_target | unknown public target; no directional supervision | `results/final_artifacts/case_06_unknown_target/trajectory.jsonl` |
| case_07_unknown_validity | quality evidence unavailable | `results/final_artifacts/case_07_unknown_validity/trajectory.jsonl` |
| case_08_invalid_native | API 原生重算失败；validity=0，保留失败证据 | `results/final_artifacts/case_08_invalid_native/trajectory.jsonl` |

## Mac 无模型基础设施失败

| 尝试 | 实测失败与处置 | 证据 |
| --- | --- | --- |
| `boot_001` | 官方容器默认 `tini -s` 在 amd64 user translation 下报 `PR_SET_CHILD_SUBREAPER is unavailable`，立即退出；没有 guest 动作或模型请求 | `evidence/mac_vm_20261016/boot_001/` |
| `boot_002` | 直接原入口后 QEMU 运行；iptables 初始化失败导致自动退回 user 网络，未转发 controller 5000。捕获 UEFI 截图后主动停止该独立容器，用新 overlay 显式配置 user forwarding | `evidence/mac_vm_20261016/boot_002/` |
| `boot_003` | 显式 user forwarding 后进入内核与 Ubuntu 动画，但 guest 出现设备 UUID 等待超时、`/boot/efi` 挂载依赖失败；900.001 秒后 controller 未就绪。`/platform` 也超时，未发 `/execute`；根因未完全确定 | `evidence/mac_vm_20261016/boot_003/` |

启动时限与最终结果见 [Mac VM 验证](MAC_VM_SMOKE.md)。这些失败均不产生 preference 标签，不计入官方 GUI-only、CLI 或 Hybrid 的 task success 分母。

## 原生 QEMU 的 GUI 宏失败

2026-10-19 用 ARM 原生 QEMU 启动同一官方 VM，三个独立 clone 的 controller 均成功；以下失败保留，不能被第三次 headless 成功覆盖。

| 尝试 | 观察与处置 | 证据 |
| --- | --- | --- |
| native `boot_001` | GUI 可见；可信宏 300 秒无 native JSON，终态未知，不重发、停机隔离。日志有 Wayland/DBus 警告，根因未确定 | `evidence/native_qemu_20261019/boot_001/` |
| native `boot_002` | 私有 overlay 改为 GDM X11 并 reset；宏仍超时，DBus portal NoReply。连续两路截图相同，未证实显示通道错误；同样不重发 | `evidence/native_qemu_20261019/boot_002/` |
| native `boot_002` 只读诊断 | VM 停止后一次 `/execute` 连接失败，ledger 记 uncertain；未重发，不能作为 CAD 动作失败或宏根因 | 同目录 `execute_trace.jsonl` 的 `macro-diagnostic-once` |

第三次 `boot_003` 在新 overlay 使用 FreeCADCmd，通过保存重开和参数修改；这不代表前两次 GUI 失败已修复。三次模型调用与 task episode 均为 0。详见 [原生 QEMU 报告](MAC_NATIVE_QEMU_SMOKE.md)。

## 2026-10-19 后续 GUI 与模型运行

本节覆盖前文“真实模型样本 N=0”和“GUI 尚未有成功路径”的历史状态。全部结果与分母见 `BASELINE_RUNTIME_SMOKE.md`，pair 数仍为 0。

| 尝试 | 实际观察 | 证据与分类 |
| --- | --- | --- |
| `desktop_env_acceptance_001` | 原始 reset/action/close PASS 后，诊断发现两个 FreeCAD GUI | 基础设施验收不足；新 gate 要求 singleton，不据此启用模型 |
| `desktop_env_acceptance_002` | GUI 单实例成功，但序列化写入字面换行，主机 JSONDecodeError | 工程故障，全次 FAIL；畸形 bytes 保存为 `gui_ready.malformed.txt`，修复后 003 通过 |
| 002 停机后的只读诊断 | 一次连接拒绝，ledger uncertain；未重发 | 不算 CAD 动作失败，也不能据此归因 GUI 宏 |
| `endpoint_live_001` | GPT 图片请求 HTTP 500，usage unknown | 1 次真实生成；原 body/request ID 未采集，不能追补。用户改选 Qwen 后保留失败并记录 correction |
| `endpoint_qwen_001` | 账本尚未恢复，本地 reserve 拒绝 | 0 次模型网络生成，不算第二次 API 故障；原结果保留 |
| `baseline_gui_sketch_001` | Qwen 连续 3 次点击 `(842,737)`，欢迎页未关闭，无输出文件；官方 strict=0 | 真实 GUI-only 任务失败，API 三次成功、219 输出 tokens；不是 run_error。截图为 1920×1080，按 0..1000 映射约为 `(1617,796)`，落在 Done 按钮附近，提示坐标约定不匹配，尚未用独立合同验证 |

第一道 GUI 的坐标错误原样保留，没有在评分后修正轨迹或补原生文件。GUI 宏修复证明图形进程和可信脚本可工作，不能由此推断模型已经具备可靠 GUI 定位能力。未打开 hidden reference 为模型生成答案。

`baseline_gui_part_001` 也连续 3 次点击 `(842,737)`，strict=0、`failure_class=no_output_file`，输出 196 tokens。它复现了首题的坐标问题；两题均有完整 screenshot/traj/result/evaluation，没有 API error。两题 creation 任务都未开始实际建模，不能据此估计 CAD 几何推理能力。

`baseline_cli_sketch_001` 是独立的工程失败：pinned `CLI/run_cli.py:100` 要求 `--results-dir` 位于 `CLI/` 边界内，原包装层给出项目 results，参数解析 exit=2。该尝试未启动 VM、未发模型生成请求，不计 episode 分母。修复为先在 `vendor/CADWORLD/CLI/results/actc/<run_id>` 运行，结束后复制原始产物到项目 `results/official_cli/<run_id>`；拒绝重复 run ID，保留这次失败，用 `_002` 新目录继续。实际 pinned CLI 计划已再次通过无模型 dry-run。

CLI `_002` 最终完成 7 轮，7 个 terminal 返回码均为 1；前三类具体错误为 `PrimitivePy` 没有 `Point1`、`Part::LineSegment` 不是文档对象类型、`doc.save(path)` 不接受路径参数。后者在后几轮重复出现，没有保存文件。官方评估 strict=0、termination=turn_limit、failure_class=no_output_file；没有 API/VM 超时或 pipeline error。它是 1 个真实 episode 内的 7 个失败命令，不扩大 episode 分母。当前 3 个真实 baseline episode 全部保留；真实 pair 仍为 0。

## Qwen3.6续跑中的失败

| 尝试 | 实际观察 | 处理与统计 |
| --- | --- | --- |
| `success_cli_qwen36_001` | 官方strict=1.0，但模型自己保存的Document.xml带Sketch.Invalid及`AttachEngine3D::calculateAttachedPlacement`错误 | 原文件和分数不改；工程审计FAIL，不导出有效preference |
| `native_artifact_audit_qwen36_001` | 审计命令失败，未捕获stdout | 审计器故障，不能追补根因；0模型调用，不算新episode |
| `native_artifact_audit_qwen36_002` | 实际FreeCAD绑定没有`Sketcher.SketchObject.movePoint` | 保留完整controller响应；审计器改用原生Distance constraint在一次性内存副本测试编辑 |
| `native_artifact_audit_qwen36_003` | 旧分类器只检查shape/solver，错误输出PASS，漏掉Invalid状态 | 原audit.json保留；audit_review.json纠正为FAIL，新增回归；未修改评分器或模型文件 |
| `success_gui_qwen36_001` | 25轮已进入绘图，Local ΔX=10、ΔY=0，第24轮Ctrl+S，第25轮仍等待保存框；多个未响应弹窗 | 官方strict=0、no_output_file；全部原始动作保留，不能按截图补文件 |
| `success_gui_qwen36_100_001` | 空白渲染预热ack成功；50次已完成请求后仍停在欢迎页，像素点击在Done内，活动窗口PID正确 | 主动阻断后不再发模型请求；随后50个WAIT是原adapter fallback。strict=null，保留官方原始0分，不计完整100步模型测量，未证明唯一根因 |
| `success_gui_qwen36_recovery_001` | 无预热，欢迎页关闭；第6轮将前轮执行pixel `(1546,306)`当作新normalized坐标输出 | 越界拒绝，strict=null、RUN_ERROR，6次/464输出tokens；修复混合单位history后用同一账本剩余44次继续，新run不覆盖 |
| `success_gui_qwen36_history_001` | v2在线history单位修复后用满44轮，仍未保存，平面选择未完成，后期未响应/窗口关闭 | strict=0、3558输出tokens；越界未重现，但关闭根因未知，不能根据模型reason定因 |
| `success_gui_qwen122_001` | 122B、v2、无预热，35轮仍卡在Select attachment，未输出文件 | strict=0、3405输出tokens；下一步先诊断控件可见性与事件循环，不盲加预算 |
| `success_cli_qwen122_001`的终止状态 | 官方1.0、原生审计PASS，但第8轮预算结束，没有finish | termination=turn_limit；保留成功文件与真实终态，不将文件有效等同agent主动宣布完成 |

续跑中的成功、恢复复测与累计成本见 `BASELINE_SUCCESS_SMOKE.md`。正式ACTC pairs仍为0，以上审计器或基础设施失败不扩大模型任务分母。
