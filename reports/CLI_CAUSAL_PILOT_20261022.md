# 多步原生管线通过，模型候选被拒绝

本轮实现并验证了供应 Sketch→Pad 和 Sketch→Pad→Pocket 的同 S0 管线。两道任务的可信构造、固定后续代码、保存关闭重开和各六个参数/控制探针通过；PocketSketch 完全约束，DoF=0。两对不相关文本控制均 Q=1/1、credit=0。随后按同一账本采完四次模型请求，四条原响应均被冻结接口拒绝，没有执行模型构造块，没有有效自然模型 pair，credit=null。

## 实际采样

| 任务 | 请求 | 原响应的接口问题 | 原生模型候选执行 |
| --- | --- | --- | --- |
| part-001 A | 1 | doc.addObject 创建 Pad，BaseFeature 列表写法超出约定接口 | 0 |
| part-001 B | 1 | 使用 Base 和 Mode，未按约定绑定 Profile | 0 |
| part-014 A | 1 | App.ActiveDocument 创建后 body.addObject，使用 Base，超出约定接口 | 0 |
| part-014 B | 1 | App.ActiveDocument 创建、BaseFeature 列表写法，超出约定接口 | 0 |

原代码与 JSON 围栏完整保留，未人工修改，未放行单边 pair。上述是静态接口拒绝，不能宣称这些代码已经在 FreeCAD 中返回相应异常。其原生运行质量为 unknown，不能设 Q=0。消息只包含公开任务、S0 原生观察和共用接口说明，未传可信后续代码、verifier 结果、官方规则或参考模型。

实际模型请求为 4，11268 输入/2491 输出 tokens，API 错误为 0，剩余调用为 0。请求设置 thinking=false，服务仍返回 2169 reasoning tokens，全部按 completion usage 记账。服务价格未知，费用为 null。两个任务各两个独立候选，同题 messages 一致，第二候选不接触第一候选或质量反馈。

第一题接口拒绝导致原 runner 提前退出，第二题尚未采样。后续仅补采第二题，沿用原四次上限的同一 SQLite 账本，新增两行，未重开额度。补采使用原提示、原 S0、原设置及已有控制证明；四个 response 和各阶段预算摘要保留。runner 已改为将接口拒绝局限于单题，继续其他已冻结任务；模型服务错误和 unknown usage 仍停止采样。

## 原生实现与结果

来源为 pinned upstream 的 fixtures/precondition，原文件 SHA 与设计一致；没有读取 fixtures/part 参考文件或 evaluator。part-001 圆半径为 5 mm，XZ 平面，Pad 长度 12 mm；part-014 圆心局部 Y=-2.25 mm、半径 10.25 mm，XZ 平面，Pad 长度 10 mm，固定 Pocket 半径 4 mm、深度 6 mm。两题均归 development。

新增 observer 记录 Sketch 几何/约束/DoF、Body.Tip、Pad.Profile、Pocket 上游关系、表达式及实际几何。固定 Pocket 位置按供应草图姿态和 Pad.Length 表达式绑定，不依赖候选 Face 编号。原生 `.FCStd` 与探针副本的来源核对 SHA，探针只改参数并 recompute，不重放候选或后续代码。

| 原生检查 | part-001 | part-014 |
| --- | --- | --- |
| 固定后续代码保存重开 | PASS | PASS |
| 目标体积 | 942.47779608 mm³ | 2999.04288693 mm³ |
| 面积、包围盒、质心 | PASS | PASS，按偏移圆心检查 |
| 参数与负控制探针 | 6/6 PASS | 6/6 PASS |
| 不相关代码块控制 | Q=1/1，credit=0 | Q=1/1，credit=0 |
| 自然模型 pair | 0，接口拒绝 | 0，接口拒绝 |

控制代码只修改独立 AuditNote 文本，每分支执行一次；各控制使用独立 FreeCAD 进程、cwd、文档和 artifact。它们属于 synthetic 控制，不作为模型成功、官方 episode 或训练样本。隔离在同一 VM 内，不声称强 OS sandbox。

## 失败与最小适配

- 预检 001：Compound 无 CenterOfMass，观察器异常。修正版按实际 solid 获取质心，没有质量时保留 null。
- 预检 002：固定后续代码保存重开状态不一致，原失败保留。
- 预检 003：两题几何/参数响应通过，PocketSketch DoF 保存前 2、重开后 0；其他字段一致。保留完整差异，按供应圆心补中心约束，未删除 DoF 检查。
- 预检 004：截图就绪超时，而 GET /platform 返回 Linux。暂停本项目的启动等待父进程，使用同一 VM 做一次有账本的原生准备，再恢复父进程并清理。两个原生状态和固定后续代码最终通过；后续 CLI 使用显式 controller-only 就绪，GUI 默认仍要求 PNG。
- 模型运行 001：准备参数约 265 KB，server 返回 Errno 7 Argument list too long。保留 uncertain dispatch、停止 clone；不重发该请求。恢复 worker 去除重复 verifier 历史，缩至 37 KB，发送前检查参数上限；新 clone 的准备参数约 55 KB。
- 模型运行 002：两个控制完成，第一题两候选被接口拒绝。剩余采样阶段在原账本完成第二题，仍均拒绝。

这些是实现/接口失败，未伪造 preference。六台 VM 已停止且 PID 不存在。累计 native /execute 为 10：9 complete、1 uncertain；其中四个 synthetic 控制执行，模型候选执行为 0。预检 004 的手工有账本准备单列计入总数，自动截图等待没有 /execute。六次 VM 生命周期总计 2217.526 秒；手工准备已包含在第四次生命周期内，不重复相加。额外补采无 VM，模型用量单列。

设计的九次派发上限用于模型小批；前置无模型调试与失败 clone 单列，总成本全部报告。模型上限四次未改变，旧八份模型账本 SHA 均未变，当前活动账本仅追加第二题两次完成请求。

## 命令与审计

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=0 PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_causal_credit.py \
  --dry-run --output results/cli_causal_mock_20261022_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/inspect_cli_causal_s0.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_causal_inspect_native_20261022_004
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_cli_causal_credit.py \
  --source results/cli_causal_inspect_native_20261022_004 \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_causal_model_native_20261022_002
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/complete_cli_causal_sampling.py \
  --source results/cli_causal_model_native_20261022_002 \
  --output results/cli_causal_remaining_sampling_20261022_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_cli_causal_sampling.py \
  --source results/cli_causal_model_native_20261022_002 \
  --remaining results/cli_causal_remaining_sampling_20261022_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/archive_cli_causal_evidence.py \
  --output reports/evidence/cli_causal_pilot_20261022
```

预检 001–003 与模型运行 001 的命令使用相同入口和各自新 output，全部失败保留。预检 004 的 controller 准备通过独立 manual_dispatch.sqlite 派发，不能把上方自动入口写成独立一键通过。对应 request、worker SHA、单次派发与原生观察均归档。

全项目 272 tests、上游 CLI 7 tests 通过。独立采样审计 PASS，核对四条原文、相同 messages、实际控制 payload/原生文件 SHA、活动账本四行与总用量、历史账本不变。MCP 可用且显式刷新，旧两份有限大数局部解析告警保留。pinned upstream tracked 文件未修改。

交付归档共 167 份文件、4.7 MB；逐份源文件/导出 SHA 一致，128 份归档 JSON、两份交接/状态 JSON 和 292 行 JSONL 严格解析通过，凭证/端点及编码 ZIP 检查通过。源码里的七处 artifact_base64 接口标识按实际内容核验，未含原生产物编码。结果见 `CLI_CAUSAL_DELIVERY_VALIDATION_20261022.json`。本轮归档与最终测试均 `ENABLE_PAID_RUNS=0`，未增加模型调用。

## 判断与下一步

GO：多步原生 observer、相同 S0、固定后续代码、参数响应和零信用控制。NO-GO：自然模型结构信用数据、方法优势、训练。当前失败暴露 API 使用和接口遵循问题；没有模型进入原生构造执行，不能判断自然候选的下游结构差异，更不能估计局部归因的训练收益。

下一步已定义于 [通用 API 说明对照](../docs/CLI_CAUSAL_API_COMPARISON.md)：先核验 Profile、body 内 feature 创建和长度单位，资料来自公开接口或独立原生 introspection，不给任务完整代码。相同模型/任务/S0 的两组各计划四次新请求，共八次，当前未执行；旧结果不能代替新的原说明组。对比接口接受率、原生完成率和参数响应，再决定是否扩大局部标签采集。当前四次账本已结束，不为成功或非 tie 重开；此前 Torus 模型 tie 与本批分别保留。

本轮新增官方 baseline episode、原 GUI/API ACTC pair 和训练样本均为 0。源码、完整 JSONL、拒绝、原生观察及预算审计见 `reports/evidence/cli_causal_pilot_20261022/INDEX.json`；凭证、端点、VM、固件、SQLite、FCStd 和编码原生产物留在本地。
