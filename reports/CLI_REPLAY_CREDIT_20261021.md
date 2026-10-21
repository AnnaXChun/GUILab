# CLI 模型代码块重放

2026-10-21，本轮使用 Qwen3.5-122B 在 `freecad-measure-003` 中实际生成并执行的代码，验证面积存储与参数响应。保留原始模型脚本、tool call ID、片段 SHA 和返回码。没有新增模型调用，未运行训练。

## 模型来源与重放边界

第 4 轮创建 `Part::Feature` 静态圆环；第 6 轮添加 `SurfaceAreaMeasurement` 字符串属性但未赋值，原终端输出为空；第 7 轮写入 `SurfaceArea_mm2=394.7841760435743`。源码选择只读取公开 instruction 与轨迹，不传入官方评分、诊断或规则。

历史 episode 没有保存第 6/7 轮前的工程 S0。本轮从模型构造片段重新创建 seed，因此属于 model-sourced prospective replay。各对候选从新建的相同 seed 字节和 native state 开始；这证明本轮配对，不证明恢复了历史 episode 的精确状态。原历史模型文件 SHA 为 `bac6abd0941f1db7e0d03c2d5c783012eb4744b2878d812e7d3217ef42be7b30`，保持不变。

模型片段保留连续 AST 源码，只移除 shell、import、open/new 和 save/close 外层。worker 使用新文档、独立 cwd 和共同保存边界；候选只执行一次。只允许已检查的 CAD 方法和受限 builtins，未验证强 OS sandbox。

## 第一轮原生结果

`cli_replay_native_20261021_001` 完成 5 次单次派发，耗时 351.365 秒，uncertain=0，VM 已停止，4 个 FCStd 与源码派发审计通过。

| 对照 | 初始数值存储 proxy A/B | 参数响应 Q A/B | credit |
| --- | --- | --- | --- |
| 模型第 6/7 轮，同一静态圆环 | 0 / 1 | null / null | 初始 proxy -1；响应 null |
| 模型第 7 轮/Shape.Area 表达式，同一原生圆环 | 1 / 1 | 0 / 0 | 0 |

第一组缺少 `Radius1`/`Radius2` 原生属性，四个半径探针无法执行，原因 `missing_native_parameter_binding` 保留。第 6 轮虽无数值属性，圆环 Label 中已有面积文本；本轮 proxy 只检查数值存储，不能据此断言文件不含任何测量信息，也不能把 proxy 当作官方 task success。

第二组 A 是真实模型第 7 轮片段，B 是人工追加 `Shape.Area / (1 mm^2)` 绑定。保存重开后，该表达式仍在 `ExpressionEngine`，但半径变化使 Shape 面积从 `394.78417604` 变为 `473.74101125` 时，存储值仍为 `394.78417604`，四个响应检查失败。API 探针还在首次 Shape 未重算时返回 `shape is invalid`，记录为 UNAVAILABLE；分支结果证明该绑定方式没有满足本轮响应目标，未改判为成功。

## 绑定修正复测

首轮源码、表达式、失败状态与原始 credit 保留。修正版配置 `cli_replay_expression_fix_20261021.json` 只重测第二组，用公开公式系数 `39.47841760435743 * Radius1 * Radius2 / (1 mm^2)` 绑定测量，并在 API 探针绑定前先重算 Shape。固定续执行、几何契约和容差不变；最多 3 次单次派发。

修正版 `cli_replay_expression_native_20261021_001` 已完成 3 次单次派发，耗时 303.879 秒，uncertain=0，VM 已停止。API 探针和两个保存后的 FCStd 都通过原生重开及 SHA 核验。修改两个半径各 ±20% 时，模型直接赋值 A 保持旧面积、Q=0；公开半径公式绑定 B 的存储面积与 Shape 面积同步、Q=1。初始数值 proxy 均为 1，初始 credit=0，响应 credit=-1。

两轮共 8 次真实派发、655.244 秒、6 个 artifact，派发全部 complete；两台 VM 进程均已退出。四个真实模型代码候选与两个人工扩展候选来自同一开发任务的重放/复测，不作为六个独立样本。原历史模型文件未变，没有新增 API 调用、官方 episode 或训练样本。

修正版单组 mock 首次因 runner 将完成条件写死为两组，返回 INCOMPLETE；单测发现后改为实际配置组数。失败输出保留，新的 mock 完成，全项目 229 tests 通过。

首轮 mock 曾预设 `Shape.Area` 会自动刷新，真实执行推翻该假设。增加已观察行为的回归测试后，新 mock 返回 credit=0，旧 mock 与源码快照仍保留；当时全项目 230 tests 通过。修正版公式 API 探针及保存重开后的两分支均已完成。

最终补充非有限测量返回 unknown、探针禁止重放模型代码的检查，并重新审计两轮实际证据通过。这是离线校验完善，不改写原生执行源码或结果；执行时源码快照与 deployed worker SHA 保留。

最终全项目 231 tests、upstream CLI 7 tests 通过。固定 CADWorld commit `e5d0ebab8bd28da6e98c68c61db05747d1647f7b` 的 tracked 文件未变，默认付费开关保持 0。

## 如何使用结果

参数响应是工程扩展目标；原官方任务要求测量并保存，两者分别报告。探针从已保存的 artifact 副本开始，只调用 FreeCAD `recompute`，不重新执行模型测量代码。因而 Q 检查的是保存后的依赖，而不是外部脚本能否重新计算面积。

| 对照 | 结果 | 解释 |
| --- | --- | --- |
| 普通初始数值检查，修正版第二组 | A=1，B=1 | 初始数值无法区分持久依赖 |
| 参数响应检查，修正版第二组 | A=0，B=1 | 原生重算可以揭示真实模型直接赋值的陈旧测量 |
| 相同终局响应 Q 的差值 | -1 | 与当前信用相同，尚无独立方法增益 |
| Best-of-2，复用已有观测 | 可选 Q=1 | 人工候选已给定，尚未独立执行候选生成算法 |
| 无图与对应打乱 | 图未参与；单组打乱无区分能力 | 不据此声称归因或训练优势 |

GO：工程检查从“初始数值”扩展到保存后的参数响应，继续在新捕获 S0 的真实 CLI 任务上验证。NO-GO：方法创新、总体成功率提升和训练效果。当前相对信用仍是同一终局 Q 差值，依赖图未参与选择；独立政策/训练对照未执行。该任务已用于调试，人工绑定候选和新建 S0 均限制结论范围；训练 eligibility 恒 false。

下一批应在执行候选前保存 S0，并让模型分别提出构造或测量代码块。按同一公开 intent、相同参数绑定、预算和固定后续执行比较，多步依赖至少涵盖上游参数、几何和独立测量对象。候选生成成本计入 Best-of-2 对照，尚未采集的任务先冻结开发/验证/测试分组，不将本任务纳入 held-out。

代码与完整证据分别见 [执行协议](../docs/CLI_REPLAY_CREDIT.md)和 [INDEX](evidence/cli_replay_credit_20261021/INDEX.json)，机器记录见 `CLI_REPLAY_STATUS.json`。

## 实际命令

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_replay.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=0 PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --dry-run --output results/cli_replay_mock_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_replay_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --config configs/cli_replay_expression_fix_20261021.json \
  --dry-run --output results/cli_replay_expression_mock_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --config configs/cli_replay_expression_fix_20261021.json \
  --dry-run --output results/cli_replay_expression_mock_20261021_002
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --config configs/cli_replay_expression_fix_20261021.json \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_replay_expression_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_cli_replay_evidence.py \
  --run results/cli_replay_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/analyze_cli_replay.py \
  --run results/cli_replay_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_cli_replay_evidence.py \
  --run results/cli_replay_expression_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/analyze_cli_replay.py \
  --run results/cli_replay_expression_native_20261021_001
```

原生阶段缺资产/配置时应记 `BLOCKED_BY_ENV`，本轮真实失败是表达式依赖行为，不归咎于 KVM 或 API key。没有模型调用，也不重开旧 API 账本。

## 交付核验

123份公开证据的来源与副本SHA全部核验通过，87份JSON/JSONL严格解析通过，编码原生payload与已有私有凭证扫描命中0。公开清单包含所有完成/失败mock、两轮原生pair trace、源码快照和原生执行审计；FCStd、VM/固件、SQLite及含base64的controller原响应未导出。

交付前按“好好说话”与anti-defensive-writing核对事实、范围和结论，10份中文文档机械扫描的章节编号、翻案句式、元话语及半角标点命中均0，无需豁免。`git diff --check`通过。先冻结来源再执行，执行后只完善离线校验，原始运行证据保持不变。
