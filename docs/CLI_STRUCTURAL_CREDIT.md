# CLI 结构信用验证

本轮回答一个具体问题：初始几何已经正确时，参数干预能否发现失效的工程依赖，并把改善归到相应的 CLI 构造块？配置为 `configs/cli_structural_credit_20261021.json`。先做三个受控程序对照，再决定是否采集模型轨迹；结果统一进入 `reports/CLI_STRUCTURAL_CREDIT_20261021.md`。

## 对照如何构造

圆环和圆柱的两个构造块分别创建原生参数对象、带同名参数的静态 Shape。初始尺寸、面积、体积、包围盒和质心应相同。静态 Shape 的参数可以写入，却不驱动几何，这是本轮预设的结构故障。

圆环测量对照固定同一个静态 Shape 上游，分别用实际 Shape、公开参数公式计算测量值。固定续执行脚本写入 `Measure.Area` 和 `Measure.Volume`，`Measure.Source` 指向 `Target`。测量更新由脚本执行，尚未验证保存后的测量对象能靠 FreeCAD 自身自动更新。

每对分支从同一 `.FCStd` seed 字节复制，候选前重算并核对原生 canonical state。各分支使用独立 FreeCAD Python 进程、文档和工作目录，共用一台 VM；这一级隔离用于可信程序诊断。它与原 ACTC 的双 VM GUI/API 实验分别验收。

每个分支只执行一次候选代码；保存、关闭、重开后，对两个公开参数分别做 ±20% 干预，另做零扰动和修改 `Guard` 的负控制。六个探针各从保存 artifact 的副本开始，只在内存中修改。原文件、seed 和各探针来源均核对 SHA。native canonical state 仅覆盖本轮 primitive，包括对象类型、参数、placement、依赖、实际几何、Invalid/Error；排除文档名和 Touched 等易变字段，浮点量化到八位小数。

## 信用代表什么

公开契约使用圆环、圆柱的面积、体积、包围盒与质心公式。Q 是几何响应、测量一致性、原生有效性和保持检查全部通过的二值值。任何必要观测缺失都返回 null 和原因；不读取 CADWorld evaluator、参考文件或官方期望规则。分数不使用候选名称、故障标签或 TypeId。

对同一 S0、公开 intent 与固定续执行 C，记录：

`credit = Q(C(A(S0))) - Q(C(B(S0)))`

这表示固定续执行下的相对收益。每对还报告初始几何等价、source/intent/probe/continuation SHA、单次派发状态、原生重开和依赖影响范围。synthetic fixtures 一律标记 `training_eligible=false`，CADWorld episode、原 ACTC pair 和训练样本计数均为 0。

依赖图从实际 `OutList` 提取，目前只记录受影响对象，不参与 Q。因此不使用图的信用与当前信用相同，这是实现核查，图带来的额外区分能力记为 0。涉及图的实际归因收益仍需多步依赖和独立对照。

首轮发现该 VM 的圆环 `Shape.BoundBox` 返回保守包围盒，无法直接对照解析边界。修正版明确使用 `optimalBoundingBox(False, False)`，禁用三角网格和 Shape tolerance，并保留旧值及 API 说明。Q 公式和容差保持原值，首轮原始结果不覆盖。该 API 的输出需在真实 FreeCAD 中验证。

## 执行命令

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_structural_credit.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --dry-run --output results/<fresh-mock-run>
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_structural_credit_diagnostic.py \
  --runtime-config results/<verified-native-runtime>.json \
  --output results/<fresh-native-run>
```

真实模式只复用已核验的本地 VM 与 Snap FreeCAD 环境。配置限 7 次 `/execute`、每 worker 110 秒、整体派发窗口 1200 秒，无模型调用或下载。timeout/5xx 的不确定执行立即停机隔离，不重发；已知失败保留 `error.json`、controller 原响应和 JSONL。输出目录拒绝复用。

远程先填写自己的 VM/固件路径与 SHA，不能直接用本机 runtime 配置。没有资产时保留 mock 与单测结果，将真实阶段记为 `BLOCKED_BY_ENV`；本轮无模型阶段不需要 API key。

## 进入下一阶段的条件

三例通过只说明检查器能识别预设结构故障。方法优势需要另一组实验：来自模型的真实失败轨迹、多步原生依赖、未用于选方法的任务，以及相同检查器终局奖励、普通逐步验证、等执行预算 Best-of-2 和打乱信用对应的对照。先冻结任务划分和预算，再收集；不把这三个 fixture 导入 SFT/RL。

当前没有可训练权重和 GPU 的验收结果，托管 API 仅用于推理。训练效果、泛化和完整策略优势须独立测量；先不接 veRL。
