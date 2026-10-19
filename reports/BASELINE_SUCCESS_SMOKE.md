# 单题 baseline 续跑

用户要求继续运行至模型任务成功，并核对能否复用 CADWorld 的 sh。本轮保留首批 15 次请求及全部失败，增加明确的单题续跑配置，模型改为 pinned Qwen sh 对应的 Qwen3.6 系列服务。

## 最终结果

CLI已跑通单题的模型调用、执行、保存、官方评分和独立原生验收。`qwen3.5-122b-a10b`的文件通过原生审计；GUI仍未成功，ACTC pairs=0。下一方向按[下一阶段验收](../docs/NEXT_ACTC_VALIDATION.md)执行，当前停止新增推理。

以下7个续跑attempt都使用`freecad-sketch-061`，加上首批3个attempt，共10个attempt、8个有效评估episode、2个运行/诊断错误；涉及2个不同任务。不同模型、预算和坐标协议不合并估计成功率。

| run_id | 模型 | 生成次数 / 已知输出tokens | 官方strict | 模型文件 / 独立原生审计 |
| --- | --- | --- | --- | --- |
| success_cli_qwen36_001 | qwen3.6-35b-a3b | 14 / 5823 | 1.0 | 有 / FAIL，原文件Invalid |
| success_gui_qwen36_001 | 同上，坐标v1 | 25 / 2393 | 0 | 无 / 不适用 |
| success_gui_qwen36_100_001 | 同上，v1、空白预热 | 50 / 4343 | null，保留raw 0 | 无 / 诊断中止，后50个WAIT不是模型调用 |
| success_gui_qwen36_recovery_001 | 同上，v1、无预热 | 6 / 464 | null，raw缺失 | 无 / 坐标越界RUN_ERROR |
| success_gui_qwen36_history_001 | 同上，v2、无预热 | 44 / 3558 | 0 | 无 / 不适用 |
| success_gui_qwen122_001 | qwen3.5-122b-a10b，v2 | 35 / 3405 | 0 | 无 / 不适用 |
| success_cli_qwen122_001 | qwen3.5-122b-a10b | 8 / 1869 | 1.0 | 有 / PASS_NATIVE_ARTIFACT_AUDIT |

最新122B CLI由turn_limit结束，未发finish；agent/task用时69.123/77.232秒。文件2924 bytes，SHA256为`ebc2e5cbcee52bc49f0b081d67d5d3979a6e10f7205795d6945771403f47d673`。原生审计在独立新VM中打开、重算、关闭重开，恢复同一Sketcher对象树，状态Up-to-date、shape有效、solver=0。模型保存的是10mm normal LineSegment及1条约束；没有Body不等于没有原生参数化结构。仅在一次性内存副本增加Distance约束，将长度10改为11；原文件SHA不变。此审计不核对官方隐藏规则，也不算新episode或模型调用。

累计5本账本共201次生成请求，包含历史失败、接口和坐标探针，并非201道题。已知输入702267、输出23385 tokens；初次HTTP500 usage未知，128-token预留保留，总token和美元费用为null。价格未提供，不能报0美元。账本请求数依次为首批15、success50、gui100实际50且blocked、recovery50、122B图片加GUI36。success账本最初42次，最后CLI122使用剩余8次，没有重置上限。

最新项目单测122 passed，上游CLI 7 tests和原CLI适配dry-run通过。所有模型和审计VM已停止；原镜像、固件SHA与pinned upstream tracked文件未变。原始结果保留在ignored results；脱敏副本、源代码快照与完整JSONL见[INDEX](evidence/baseline_success_20261019/INDEX.json)。运行时为ea2a4b1父提交上的dirty worktree，每个run首次请求前记录实际36个cad_cf文件的SHA；最终提交不能冒充当时的干净运行版本。

sketch-061反复用于调试和模型选择，不能当独立未见held-out结果。CLI官方成功、原生质量、agent是否finish、GUI成功、论文复现和ACTC效果分别判断。

## 已得到的官方成功

`success_cli_qwen36_001`，任务 `freecad-sketch-061`，原 CLI prompt/tools/parser，模型 `qwen3.6-35b-a3b`、thinking=false。官方 `result.json` score=1.0，`evaluation.json` stored/recomputed 均为 1.0，failure_class=pass。

| 测量 | 实际值 |
| --- | --- |
| model calls / terminal calls | 14 / 13 |
| 输出 tokens | 5823 |
| agent_seconds / task_seconds | 140.134 / 158.945 |
| termination | finish |
| agent 文件 | `results/official_cli/success_cli_qwen36_001/freecad-sketch-061/freecad-sketch-061.FCStd` |
| 大小 / SHA256 | 3463 bytes / `3ae807fd800ef3c8da1a89362c52f8c902cda50b76ccc870a5dd7cc4eb93a8eb` |

模型在第 12 次 terminal 调用保存，第 13 次用 `FreeCAD.open` 重开并重算，第 14 次生成 finish。未由可信脚本补建模型，未提供参考文件、评分反馈、API 答案或人工修复。原始 runner、评分器与 diagnostics 均为 pinned 实现。

## 官方得分与工程质量分开

这个 CLI 文件保留了 Body、Sketcher::SketchObject、1 条 normal geometry 线段与 1 个 Horizontal constraint；端点为 `(0,0,0)`、`(10,0,0)`。Sketch 未完全约束，原任务不要求完全约束，不能把约束检查通过写成 FullyConstrained=true。

独立的无模型 VM 审计证实：文件可重开，原生类型树恢复一致，形状有效、Sketch 求解返回 0；在一次性内存副本增加原生 Distance constraint，可把长度 10 改为 11，关闭重开后原文件仍为 10，SHA 不变。

但 Sketch 的 State 包含 Invalid。进一步直接读取**模型自己保存的** Document.xml，已确认文件原本就保存了以下错误，而非审计器环境新引入：

```text
Sketcher::SketchObject, Touched=1, Invalid=1
AttachEngine3D::calculateAttachedPlacement: not enough shapes linked (at least two are required).
```

文件的 AttachmentSupport 只有 XY_Plane 的 Plane，MapMode 为 OXY。官方 strict=1.0 保留；独立工程自检为 `FAIL_NATIVE_ARTIFACT_AUDIT`。原始审计器曾只检查 shape/solver，错误地输出 PASS；`audit_review.json` 保留该原记录并给出纠正，新增回归测试防止 Invalid 状态再次被当作通过。没有修改官方评分规则或模型文件，也不将此文件记为工程质量全部通过的训练样本。

前两次审计器失败也保留：001 返回码失败但 stdout 未保存，不能追补根因；002 完整响应显示实际 FreeCAD 1.1 绑定没有 movePoint。003 改用原生约束在内存副本测试编辑，记录与模型任务严格分开。审计器修正不是方法贡献。

## GUI 的独立复测

原坐标合同探针复现 Qwen3.6 输出 0..1000 坐标。新的显式 `normalized1000` adapter 转换绝对鼠标坐标，保留原始输出与执行像素；键盘、相对位移和 scroll 数量不变。它不提供任务操作步骤或按钮位置，原像素协议失败继续保留。

`success_gui_qwen36_001` 的 25 轮复测已评估为 strict=0、no_output_file。模型关闭了欢迎页、进入空文档、绘图时把 Local ΔX 设为 10、ΔY 设为 0；第 24 轮 Ctrl+S，第 25 轮仍在等待保存对话框，因此未保存。多个“FreeCAD 未响应”弹窗消耗了轮数。这个结果不能视为成功，也不能据此判断官方 100 步预算的结果。

随后按 pinned sh 的 100 步上限，仅续跑同一题。开启可选空白绘图视图预热：在 agent 介入前创建无对象的临时文档，渲染空白图，再关闭，核对空文档集与单实例。没有任务几何或 `.FCStd` 输出。新批最大 100 请求 / 32000 输出 tokens，前两批账本不变；成功、失败与成本分别记录。

`success_gui_qwen36_100_001`的预热ack成功，但50次已完成请求、4343输出tokens后欢迎页仍未响应。截图确认像素点击落在Done内，只读诊断确认活动窗口属于唯一FreeCAD PID；未确定唯一根因。主动阻断共享账本后不再发生成请求，原adapter继续50个WAIT并得到raw score=0。离线分类为`RUN_ERROR / externally_stopped_diagnostic_run / strict=null`，不计完整100次模型测量。

撤掉预热的`success_gui_qwen36_recovery_001`成功关闭欢迎页，但第6轮出现混合坐标单位：模型输出上一轮执行的pixel `(1546,306)`，违反0..1000合同，转换器拒绝执行。本次6个请求、464输出tokens，全部usage可计量；strict=null，保留pipeline_error。pinned agent会把原model_action与pixel executed_action共同放入下一轮history；协议v2将在线history统一为normalized单位，而原response/完整JSONL仍保留pixel执行值与coordinate_mapping元数据。该修正经过真实pinned agent的两轮无网络测试验证。

`success_gui_qwen36_history_001`在全新VM、无预热、协议v2下复测同题，使用同一本recovery账本，自动收紧至剩余44次；不清空前6次请求，不覆盖旧run。最终结果见本报告末尾与机器可读汇总。

该35B运行最终用满44轮，仍无保存文件，官方strict=0。坐标越界未再出现；模型在折叠的Select attachment面板反复确认OK，后期出现未响应弹窗和FreeCAD窗口关闭。没有足够独立证据确认关闭的唯一原因，模型自己的reason不能当作根因诊断。结束后的stdout读取遇到连接拒绝，仅记录一次只读失败，不重放执行。

一次只读`/models`检查确认服务已有`qwen3.5-122b-a10b`，没有下载模型。图片验证返回FREECAD、3输出tokens，随后35轮GUI仍卡在Select attachment平面选择，没有文件，官方strict=0。截图中的控件展开状态、输入送达和事件循环尚未独立验收，不能断言完全由模型能力或TCG造成。未使用`qwen3-vl-plus`作为开源权重证明。随后122B CLI仅使用success账本剩余8次，得到上表中的官方与原生成功；没有再开新模型预算。

## sh 复用结论

详见 [UPSTREAM_SH_REUSE](UPSTREAM_SH_REUSE.md)。原 GUI sh 的 100 步、原 CLI 的 1200 秒与工具协议已核对；GUI sh 引用的 test_rest.json 在 pinned commit 中缺失，CLI wave 脚本会启动四个模型和 50 题，vLLM sh 固定 NVIDIA GPU 3 并可能下载权重。本机使用原 Python 入口，替换为已有服务、单题清单和 native QEMU/TCG；未执行这些整批/服务启动脚本。

122B单题的实际命令如下；同一配置的图片验证先通过才启动GUI。该run ID已使用，不得在远程原样重开。

```bash
ENABLE_PAID_RUNS=1 .venv/bin/python -m cad_cf.model_probe \
  --model qwen3.5-122b-a10b --qwen-no-thinking \
  --screenshot results/baseline_debug_20261019/desktop_env_acceptance_003/reset.png \
  --output results/qwen122_endpoint_001 \
  --campaign-config configs/baseline_qwen122_20261019.json \
  --batch-ledger results/qwen122_batch_20261019.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui \
  --task-id freecad-sketch-061 --model qwen3.5-122b-a10b \
  --qwen-no-thinking --qwen-coordinates normalized1000 \
  --campaign-config configs/baseline_qwen122_20261019.json \
  --run-id success_gui_qwen122_001 \
  --runtime-config results/baseline_success_20261019/runtime_gui_qwen122.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/qwen122_batch_20261019.sqlite
```

最后CLI与不调用模型的审计命令如下，已运行目录不得覆盖或重复启动：

```bash
ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind cli \
  --task-id freecad-sketch-061 --model qwen3.5-122b-a10b \
  --qwen-no-thinking --campaign-config configs/baseline_success_20261019.json \
  --run-id success_cli_qwen122_001 \
  --runtime-config results/baseline_success_20261019/runtime_cli_qwen122.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/success_batch_20261019.sqlite

ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_native_artifact.py \
  --artifact results/official_cli/success_cli_qwen122_001/freecad-sketch-061/freecad-sketch-061.FCStd \
  --runtime-config results/baseline_success_20261019/runtime_cli_qwen122.json \
  --output results/native_artifact_audit_cli_qwen122_001

ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q tests
```

## 协议与阶段边界

这是 TCG 单题接入与成功验证，不是 full-200 或论文成功率复现。GUI 模型 adapter 和渲染预热的差异单列；CLI 原 prompt 与工具协议不变。所有官方评分只在 episode 后执行，独立工程检查没有接触官方 expected/reference。

真实 ACTC pairs 仍为 0。同一 base SHA 和同一 task ID 不等于经过恢复证明的同一 S0；本轮两条 baseline 不能当作 counterfactual pair。正式 TypedWorker、GUI bridge、same-S0 clone 和训练验收仍未完成。
