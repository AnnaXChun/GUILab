# Pocket 下游信用验证

本轮完成一个新的 CLI 下游边界设计、原生准备和两次模型采样。模型两原文均被静态接口拒绝，天然执行0、有效自然 pair=0、credit=null、新增训练样本0。原生 S1、可信 Pocket 续执行和六探针通过，文本负控制 Q=1/1、credit=0。结果和原始失败分别保存，不推导方法收益。

| 实验 | 范围与结果 | 模型成本 | 判定 |
| --- | --- | --- | --- |
| 已完成官方 terminal CLI | 200尝试、185可评估、14通过、15运行错误；交付率7.00% | 3163请求；32025357输入/1582168输出 | 历史完整基线，未重跑 |
| 已完成 Pad 模型候选 | part-014两原文各执行一次；一个有效tie，Q=1/1、credit=0 | 原四请求小批另计 | 执行可用，方法收益未测 |
| 新 Pocket 模型候选 | 同 prospective S1、相同messages，两原文静态拒绝；原生质量unknown | 2请求；7098输入/1772输出tokens；费用null | 新下游候选可执行性 NO-GO |
| 新原生 S1/控制 | 准备一次与两控制，共3派发complete；六探针通过，控制credit=0 | 0模型请求 | 原生准备 GO |
| 新独立克隆控制 | 两个独立VM的synthetic文本控制，Q=1/1、credit=0、各六探针通过 | 0模型请求；2次complete派发 | clone执行与API核对 GO |

公开任务为 `freecad-part-014`，继续归 development。原供应草图的圆心、半径和旋转从原生观察绑定；可信 Pad 前缀保存关闭重开为 S1，S1 是本轮局部分叉的 S0。模型子目标明确要求半径4mm、深度6mm的同心Pocket，后续Pad.Length编辑时仍处于外端。该响应要求属于工程扩展协议，可信前缀不计作模型完成的多步 episode。

准备目录 `cli_pocket_prepare_20261023_001` 在停止的旧捕获磁盘新overlay中执行。S1字节SHA为 `436c5e8566284be7c4e7dd55fa3bce0c24201546d4ccfe6bf60a6db7f17ec972`；native SHA、固定finish代码、六探针和源码均在请求前冻结。独立XY工程API七项检查通过，任务可信续执行通过。模型只接收公开instruction、明确子目标和S1原生状态，不接收可信Pocket代码、探针结果、官方evaluator或reference。首次源码提交为 `9955779`，原prompt/scoper已保存于run源码快照。

两条独立Qwen3.5-122B响应使用相同messages、temperature=0.7、thinking=false，每次上限2048输出tokens，总预算4096，SDK重试0。原响应和代码SHA、完整model/provider JSONL、静态拒绝与账本全部保留。A的原代码SHA为 `88785a39e2125f1f3339d12c48e3f7c0753088e4e111eb200e9b1851cbc96740`；B为 `13d80b124490f4720f1618d3d3e98c26affac6149f1e7f0acb9b04dfd5c1f373`。两原文均未执行或改写，没有人为修补响应后标为成功。

原第一拒绝都是“mutation outside new Pocket scope”。离线AST继续检查发现：A使用未定义的 `pocket_radius_mm/pocket_depth_mm` 和当前未暴露的 `str`，写 `pocket.Depth` 和 `Type='Dimension'`；B还含 `try/except`、`hasattr`、`geo.append` 及未定义深度变量。A假设Face3、B假设Face7，面编号未核验。静态发现不等于这些代码已在FreeCAD报错，原生质量保持null。

后续无模型clone检查只执行可信AuditNote控制，并只读核对公开Pocket属性和新建局部Circle。已观察到 Length 是 App::PropertyLength、Depth不存在、有限Type为Length且没有Dimension、双字符串Quantity报TypeError、局部Circle.Radius/Location可修改。当前通用说明修为 `pocket_api_contract_v2_not_sampled`，明确JSON字段与Python变量的区别，最小放行原生验证的局部Circle构造；v2没有新增模型调用。

两clone使用不同VM overlay、PID、工作目录与文档副本，同seed字节/native SHA和同停止快照已独立审计。准备与clone合计5次native派发，全部complete、uncertain=0；三台VM均已停止。五份可信final artifact的六探针共30次检查，另有独立XY API检查。它们全为synthetic/可信程序输出，天然候选仍没有进入执行。clone探针的host脚本在运行后补了失败退出码；原脚本源码经精确反向恢复，与启动前manifest SHA完全一致，标为posthoc恢复，实际deployed worker和派发内容在运行前已冻结。

选择对照复用相同两条候选和响应奖励，tie固定选A，交换A/B标签也保持tie选A。局部credit与相同奖励的终局Best-of-2必须等价。两候选质量unknown，本轮所有质量选择为null；没有独立的全轨迹奖励对照或训练结果。此前helper中的强制反选与本轮的真正标签交换分别记录。

模型账本已结束，不追加采样。准备目录的单次采样claim在本批结束后补建为 `posthoc_completed_batch_binding`；它不是请求前已有的证据。后续runner在请求前独占创建claim，结束或unknown也不删除。原生磁盘与旧账本SHA不变。历史审计从当时源码快照加载parser/prompt，避免当前说明变化改写旧拒绝。

机器结果为 `CLI_POCKET_STATUS_20261023.json`，证据在 [INDEX.json](evidence/cli_pocket_credit_20261023/INDEX.json)。实际命令和验证记录为 `CLI_POCKET_VALIDATION_20261023.json`。GUI未恢复、200题未重跑、没有训练、下载权重或接veRL。当前GO是原生准备与受控检查；下游天然标签、方法增益和训练NO-GO。下一步先用当前源码新建S1准备并核验v2契约，再冻结独立小批；不能消费旧准备claim或把API提示修正当方法创新。

完整项目回归318项和上游CLI七项通过，最终相关回归另见验证记录。归档134文件、268次source/export SHA核对、77个JSON与68行JSONL解析通过；密钥、服务地址、FCStd、qcow2和controller编码响应不导出。MCP状态与代码检查独立记录，不代替上述原生验证。
