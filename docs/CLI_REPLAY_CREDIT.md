# CLI 模型代码块重放

本轮复用 `freecad-measure-003` 的真实 Qwen CLI 轨迹，验证模型代码的测量存储和参数响应。配置为 `configs/cli_replay_credit_20261021.json`，不新增模型推理。该任务已用于开发和方法选择，不能作为独立测试集。

## 来源与配对

第 4 轮创建静态圆环并保存，第 6 轮添加空字符串测量属性，第 7 轮添加数值测量属性。源码选择只读取已归档轨迹和公开 instruction，记录 tool call ID、原始脚本/Python/片段 SHA、连续源码行和原返回码。官方评分、诊断和规则不传入 worker。

只支持已经检查的单个 Python heredoc。适配移除 shell、import、文档打开/新建和保存/关闭外层，保留连续 AST 源码片段；固定 worker 提供新文档和保存边界。候选禁止文件/网络操作，通过 CAD 调用白名单检查并使用受限 builtins。该白名单用于约束本轮已检查片段，不等于强 OS sandbox。

| 对照 | 共同 S0 | A | B |
| --- | --- | --- | --- |
| 模型第 6/7 轮存储 | 第 4 轮构造片段在新文档创建的静态圆环 | 模型第 6 轮原片段 | 模型第 7 轮原片段 |
| 数值赋值/表达式 | 新建原生参数圆环 | 模型第 7 轮原片段 | 同片段追加 `Shape.Area / (1 mm^2)` 表达式绑定 |

第二组 B 是人工定义的绑定修正，不能写成模型自行生成。所有分支各从相同 seed 字节复制，候选前核对原生 canonical state、intent、探针和固定续执行 SHA，候选只执行一次。各分支独立进程、文档和 cwd，共用一台 VM。

首轮发现 `Shape.Area` 绑定在原生半径变化后仍保留旧面积。失败保留后，修正版只对第二组使用公开圆环公式 `39.47841760435743 * Radius1 * Radius2 / (1 mm^2)`。配置为 `configs/cli_replay_expression_fix_20261021.json`，限 3 次单次派发、900 秒；公式不读取官方规则或黄金文件。

历史中间 S0 没有保存。因此本轮是新建 S0 上的 model-sourced prospective replay，不能声称恢复了历史 episode 的精确状态。原历史模型文件只核对 SHA，保持不变。

## 两种质量分开记录

`initial_proxy_q` 检查初始圆环公开几何、有效性和是否有数值面积存储。它仅支持数值属性，原模型 label 中的面积文本是另一种表示，不能据此断言第 6 轮没有任何测量信息。公式来自公开几何，初始存储 proxy 不等于官方 task success。

`q` 进一步检查两个半径各 ±20% 修改后，Shape 和已保存测量是否一起更新。所有探针从 artifact 副本开始，只有 FreeCAD `recompute`，不重新执行模型测量代码。零扰动、Guard 负控制和文件保持一起记录。缺少半径属性时返回 null 和 `missing_native_parameter_binding`，不补假参数。

固定续执行为 `doc.recompute()` 和共同保存边界。表达式必须在 `.FCStd` 保存关闭重开后保留响应，seed 阶段另记录真实表达式 API 检查。原生响应 Q 为工程扩展目标，与官方“测量并保存”的任务目标单列。

配对信用为 `Q(A)-Q(B)`，所以 B 优于 A 时为 -1。未知响应、不同 S0、缺少单次执行或原生边界证明均不导出 preference。本轮训练 eligibility 恒 false。

## 执行与下一步

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_replay.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --dry-run --output results/<fresh-replay-mock>
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_replay_credit.py \
  --runtime-config results/<verified-native-runtime>.json \
  --output results/<fresh-replay-native>
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_cli_replay_evidence.py \
  --run results/<completed-replay-native>
```

一次 VM、最多 5 次单次 `/execute`、worker 110 秒、整体派发窗口 1200 秒。不下载模型，不训练，不改变历史 API 账本。timeout/5xx 不重发并停止隔离。缺 runtime/资产记 `BLOCKED_BY_ENV`。

结果只能支持本任务代码块的工程诊断。方法优势还需多步依赖、更多任务和真实模型提出的候选，用相同终局检查器、逐步验证、等预算 Best-of-2 和打乱信用做独立对照。当前图只作状态记录，不把表达式修正当方法创新。
