# CLI 模型候选通过验证

2026-10-21，针对圆环测量代码的 FreeCAD API 和表达式错误，本轮取得一个有效模型配对：A、B 原文各执行一次，保存关闭重开后通过全部六个探针，Q=1/1，credit=0。两份 `.FCStd` 保留 `Part::Torus` 原生半径和 ExpressionEngine 测量绑定。独立审计通过，两个运行 VM 均已停止且 PID 不存在。

## 修复与证据

旧 A 使用 `math.pi ** 2`，FreeCAD 表达式解析失败；旧 B 调用不存在的 `hasProperty`，未进入表达式调用。新增通用 API 说明，并先在真实 FreeCAD 1.1.0 的独立 Box 文档中验证 PropertiesList、pi、^、单位表达式、保存重开和参数响应。探针通过后才发模型请求。说明用 Box 面积举例，圆环公式由模型生成，在线输入只有公开任务、当前工程状态和接口说明。

模型两次独立返回相同公式，代码字符串有空格差异。响应外层是单个 JSON 代码围栏，原严格 JSON 接口拒绝，两次原响应和拒绝记录保留。随后增加显式 `single_json_fence` 适配，只移除完整响应的外层围栏，不改 JSON 或内部代码；额外文字、多个围栏或 Python 围栏仍拒绝。该适配后的无模型执行单独记录，不改判首次拒绝为成功。

```python
torus_obj = doc.getObject('Torus')
if 'SurfaceArea_mm2' not in torus_obj.PropertiesList:
    torus_obj.addProperty('App::PropertyFloat','SurfaceArea_mm2')
torus_obj.setExpression('SurfaceArea_mm2', '4 * pi^2 * Radius1 * Radius2 / (1 mm^2)')
```

这是 A 的原代码字符串；B 的最后一行仅少一个参数分隔空格。两次请求使用相同 messages，B 不接收 A 或检查结果。代码生成冻结为 `4ae7ddd`，围栏适配在执行前冻结为 `4d8c544`。源码快照、实际派发 payload、响应及代码 SHA 对应关系均已核对。

## 同 S0 与隔离

使用模型请求前已经保存的原 S0，seed SHA 为 `65d32a355a16b483e52b84b55230765d3c35d838f47f5b354524c8e70b7a16b0`，canonical state SHA 为 `b3dde05a4a770a9b5431a77a1203ddd00cd3430b7c0781adfe91ada94a12f1da`。模型批从停止的原捕获磁盘 clone 恢复；围栏适配执行又从停止的模型批磁盘 clone 恢复，相同 seed 字节和工程状态均核对通过，backing 磁盘不变。

每候选使用独立 FreeCAD 进程、文档和 cwd，共用一台 VM。候选只执行一次，固定续执行为 `doc.recompute()`。保存关闭重开后，每个探针从 artifact 的字节副本开始，只在内存改变参数并重算，不再执行模型代码。

| 检查 | A | B |
| --- | --- | --- |
| 初始与保存重开测量 | 394.78417604 mm² | 394.78417604 mm² |
| Radius1 ×0.8 | 315.82734083 mm² | 315.82734083 mm² |
| Radius1 ×1.2 | 473.74101125 mm² | 473.74101125 mm² |
| Radius2 ×0.8 | 315.82734083 mm² | 315.82734083 mm² |
| Radius2 ×1.2 | 473.74101125 mm² | 473.74101125 mm² |
| Guard 负控制 | 测量不变、Guard 体积改变 | 测量不变、Guard 体积改变 |
| 原生重开状态一致 | PASS | PASS |
| 单次候选执行 | 1 | 1 |
| 原生几何有效性与保留检查 | PASS | PASS |
| 响应 Q | 1 | 1 |

存储值与原生 Shape.Area 相符。原生 XML 绑定为 `4 * pi ^ 2 * Radius1 * Radius2 / 1 (mm ^ 2)`。A artifact SHA 为 `aa79f92d57339b34a9dfb81cd62b1b4bb615db9303af987662f513e44a0cdf08`，B 为 `485045deda4eb128faf85920fb63a9de647184ac75fe497d8717af10e980108f`。

## 实际运行与用量

| 运行 | 新模型请求 | Native 派发 | 结果 | 耗时 |
| --- | --- | --- | --- | --- |
| cli_model_pair_api_guided_native_20261021_001 | 2 | 1 | API 探针 PASS，严格 JSON 围栏拒绝 | 244.312 秒 |
| cli_model_pair_api_guided_saved_20261021_001 | 0 | 3 | 原候选执行通过，pair valid，credit=0 | 234.091 秒 |

本轮总耗时 478.403 秒，两次模型请求共 2430 输入、1147 输出 tokens，API 错误为 0。服务价格未知，美元费用为 null。请求设置 thinking=false，但服务仍返回 reasoning_content 和合计 962 reasoning tokens；按完整 completion usage 记账，不能把请求参数当作服务已关闭思考的证据。

连同此前三个失败运行，此系列共 5 次实际模型请求，其中一次超时；已知输入 4574、输出 2430 tokens，超时的 2048 unknown reservation 保留。累计总输入、输出和费用均为 null。共 9 次 native 派发、uncertain=0，四次候选执行中旧两次失败、新两次成功。历史模型账本保持原 SHA。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_model_pair.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=0 PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_guided_cli_model_pair.py \
  --dry-run --output results/cli_model_pair_api_guided_mock_20261021_001
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_guided_cli_model_pair.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_model_pair_api_guided_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_guided_cli_model_pair.py \
  --run results/cli_model_pair_api_guided_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/execute_saved_cli_model_pair.py \
  --source results/cli_model_pair_api_guided_native_20261021_001 \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_model_pair_api_guided_saved_20261021_001 \
  --allow-json-fence --port 15065 --vnc-port 15965
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_saved_cli_model_pair.py \
  --run results/cli_model_pair_api_guided_saved_20261021_001
```

最终相关测试 26 项、全项目 257 项、上游 CLI 7 项通过。MCP 可用且显式完整刷新，保留两份旧诊断有限大数的局部解析告警；索引状态与测试结果分别记录。pinned upstream tracked 文件未改。

## GO 与下一步

GO：通用 API 说明、明确响应封装适配、同 S0 模型代码块执行与持久参数响应已通过。当前有效配对为一个 tie，训练样本增加为 0。官方 CLI baseline 历史成功记录保持，本轮属于开发任务上的扩展测量协议；新增官方 episode 和原 GUI/API ACTC pair 均为 0。

方法收益与 RL 训练仍为 NO-GO。当前 credit 与同一响应终局 Q 差值相同，单 pair 没有候选优劣；旧无说明失败与新说明成功只能说明调试经过，不能估计因果增益。下一步冻结两个新 CLI 构造任务及任务划分，在每次模型请求前捕获 S0，保持相同预算与公共输入，比较直接终局检查、参数干预检查与 Best-of-2。先取得能区分候选的非 tie 记录，再判断是否值得扩展和训练。远程执行需提供自己核验过的 S0 与 runtime，历史本机磁盘路径只是 provenance。

公开证据入口为 `reports/evidence/cli_api_guided_pair_20261021/INDEX.json`。模型响应、完整 JSONL、源码快照、拒绝和成功观测公开；凭证、端点、VM、固件、SQLite、原生文件及编码 payload 保留本地。

## 交付核验

109 份公开证据的来源和副本 SHA 全部通过，74 份 JSON/JSONL 严格解析通过，私有凭证与编码原生 payload 命中为 0。9 份中文文档按“好好说话”和 anti-defensive-writing 核对事实，执行四项机械扫描，命中均为 0，无豁免。扫描记录为 `reports/CLI_API_GUIDED_WRITING_SCAN.json`，`git diff --check` 通过。
