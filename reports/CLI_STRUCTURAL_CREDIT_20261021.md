# CLI 结构信用验证

2026-10-21，按用户“继续验证”执行三个受控 CLI 程序对照：圆环构造、圆环测量、圆柱构造。代码、mock、单测和原生执行分别保留。本轮不调用模型、不训练，不增加 CADWorld episode、原 ACTC pair 或 SFT 样本。

## 验证范围

每对从同一 `.FCStd` seed 字节复制，候选前核对原生 canonical state；两个候选的公开 intent、参数绑定、探针、前缀和续执行 SHA 一致。分支各用独立进程、文档和 artifact 目录，第二轮还核验独立 cwd。共用同一 VM，隔离级别为 document/process/workdir，未验证强 OS sandbox。

Q 只检查实际几何是否符合公开圆环/圆柱契约、测量是否与 Shape 一致、原生状态是否有效、Guard 是否保持。两个参数分别做 ±20% 干预，另有零扰动和 Guard 负控制，每分支六个探针。候选只执行一次，探针各从保存文件的副本开始，只修改内存；续执行脚本在修改后刷新测量属性。

Q 不使用 TypeId、候选名称或预设故障标签，也不读取 CADWorld evaluator 或参考文件。`Measure.Source` 是原生 Link，面积/体积更新由固定脚本执行；这轮没有验证测量对象脱离脚本后的自动更新。

## 首轮检查器失败

`structural_credit_native_20261021_001` 完成 7 次单次派发，耗时 371.261 秒，controller 就绪用时 162.269 秒。原始信用为 `[0, 0, 1]`，三个 pair 均满足配对校验；两个圆环 pair 的 Q 被包围盒取值问题压为 0。六个分支中只有两个圆柱分支通过初始检查，合计 40 项检查失败。

圆环面积和体积都是 `394.78417604`，符合公开公式。`Shape.BoundBox` 却返回 x/y 范围 ±7.5767454，解析边界为 ±7。修正版使用 `optimalBoundingBox(False, False)`，真实 API 说明确认两个参数分别控制三角网格与 Shape tolerance；输出为 x/y ±7.0000001、z ±2.0000001，满足原有 `1e-6` 容差。首轮源码快照、原始 Q、JSONL、文件 SHA 和错误解释都保留，未覆盖成绩。

## 修正后原生结果

第二轮 `structural_credit_native_20261021_002` 完成 7 次单次派发，耗时 429.346 秒，controller 就绪用时 124.717 秒。全部配对校验与原生执行审计通过，六个 artifact 的保存、关闭、重开及 SHA 核验通过；六个 worker 的实际 cwd 各自独立。六个分支初始几何检查全部通过，36 次探针观测产生 20 项预设结构故障检查失败。

| 干预位置 | A 的 Q | B 的 Q | credit | 实际含义 |
| --- | ---: | ---: | ---: | --- |
| 圆环上游构造 | 1 | 0 | 1 | 原生参数驱动几何；静态 Shape 的同名参数不驱动几何 |
| 圆环下游测量 | 0 | 0 | 0 | 改测量实现后，上游几何仍不随参数更新 |
| 圆柱上游构造 | 1 | 0 | 1 | 原生圆柱参数响应通过；静态 Shape 响应失败 |

两轮共 14 次 `/execute`，全部 complete、uncertain=0，共 800.607 秒。保存的 12 个原生文件来自同三个 fixture 的两轮执行，不能作为 12 个任务或 6 个独立语义对照。两台顺序启动的 VM 都已停止。付费模型调用为 0，训练样本增加 0，原 CLI baseline 成绩和原 ACTC pair N=0 保持原记录。

离线审计从实际 SQLite payload 解析 request 与 worker 源码，逐项重算候选、前缀、续执行和公开 intent/probe SHA；核对部署源码冻结清单、artifact SHA、`Document.xml` 类型树与实际 FreeCAD 状态，重新计算所有 pair 结果。两轮均 PASS，公开账本只保存 payload SHA，不含原生文件 base64。

## 对照如何解释

当前依赖图只记录 `Target` 的下游 `Measure`，不进入 Q。图与无图信用相同属于实现核查，不能作为图方法增益。离线分析复用同一组观测，记录相同检查器终局 Q、Best-of-2 选择和循环打乱信用对应；这些尚未构成独立的训练或归因效果对照。

| 离线对照 | 修正轮结果 | 可据此判断什么 |
| --- | --- | --- |
| 普通初始逐步检查 | 6/6 通过 | 初始几何检查遗漏本轮静态 Shape 故障 |
| 相同检查器终局奖励 | Q 与上表完全一致 | 相减信用尚未提供额外的故障区分能力 |
| Best-of-2 选择 | 各对可选 Q 为 `[1, 0, 1]` | 使用同一批观测作选择，尚未独立运行算法对照 |
| 无图检查 | credit 完全相同，额外区分为 0 | 当前图只作记录与解释 |
| 循环打乱信用对应 | `[0, 1, 1]` | 仅核查对应关系，尚未测量训练影响 |

真实结果支持参数响应检查识别预设上游故障；单独修改下游测量不能消除几何不更新。当前信用就是同一检查器终局 Q 的差值，方法是否优于终局奖励仍未验证。下一阶段需要模型真实轨迹、多步原生依赖、未用于选方法的任务，以及等采样/执行预算的终局奖励、逐步验证、Best-of-2 和打乱信用对照。

GO：复用原生参数响应检查和严格配对证据，设计少量真实 CLI 构造块验证。NO-GO：将本轮写成方法创新、泛化增益或 RL 优势；当前 3 条 SFT、可训练权重/GPU 未验收，也不足以启动训练。

完整公开证据见 [INDEX](evidence/cli_structural_credit_20261021/INDEX.json)，机器状态见 [CLI_STRUCTURAL_CREDIT_STATUS.json](CLI_STRUCTURAL_CREDIT_STATUS.json)。原文件与含 base64 的 controller 原响应留在本地 results，不上传。

## 实际命令

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_structural_credit.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=0 PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --dry-run --output results/structural_credit_mock_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/structural_credit_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --dry-run --output results/structural_credit_mock_20261021_002
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/structural_credit_native_20261021_002
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/analyze_structural_credit_diagnostic.py \
  --run results/structural_credit_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_structural_credit_evidence.py \
  --run results/structural_credit_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/analyze_structural_credit_diagnostic.py \
  --run results/structural_credit_native_20261021_002
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_structural_credit_evidence.py \
  --run results/structural_credit_native_20261021_002
```

初版新增模块 21 tests、全项目 204 tests 通过；补充隔离与来源检查后模块 25 tests；修正版补充缺 runtime 和缺资产两个环境失败 case 后，模块 27 tests、全项目 210 tests 通过。upstream CLI 7 tests 通过，固定 commit 与 tracked 文件未变。mock 两轮均完成，结果 `[1, 0, 1]`，只用于测试。

本轮曾尝试读取 FreeCAD 对应源码，raw URL 返回 404、GitHub contents API 返回 403 rate limit，未获得该源码。包围盒适配依据实际 VM API 说明与原生输出，不将失败源码检索写成源码核验通过。

## 交付核验

通过 `scripts/archive_baseline_evidence.export` 的显式文件白名单生成 91 份公开证据，原始来源和公开副本 SHA 全部一致，85 份 JSON/JSONL 文件严格解析通过。没有导出 FCStd、VM、固件、SQLite 或原生文件 base64，已有凭证/私有 endpoint 扫描命中为 0。执行账本、完整观测 JSONL、pair trace、两轮源码快照及失败解释均可回读。

交付前按“好好说话”和 anti-defensive-writing 核对事实、术语与结论，10 份中文文档机械扫描的章节编号、翻案句式、元话语、半角标点四项命中均为 0，无需豁免或改动历史原文。`git diff --check` 通过。模型调用和训练增益分别报告，方法边界保留一次明确说明。
