# 捕获S0模型小批

2026-10-21，用户在上一轮“先捕获S0、让模型生成代码块”的交接后要求继续。本批配置`configs/cli_model_pair_20261021.json`限2次独立生成、4096输出tokens、3次原生派发。目标为已有开发任务`freecad-measure-003`的原生测量代码块，非官方baseline完整episode，无训练。

## 实际结果

VM/controller就绪用时173.304秒。准备worker创建并保存原生Torus与Guard，关闭重开、重算并记录canonical state，host落盘`captured_s0.json`后才发送第一次模型请求。S0字节SHA为`529905d6bb7e7dee1612529c91234336086d280aac0a2409e01e0657c9f869be`，canonical state SHA为`b3dde05a4a770a9b5431a77a1203ddd00cd3430b7c0781adfe91ada94a12f1da`。

第一次Qwen3.5-122B请求以`APITimeoutError`结束。配置的请求timeout为60秒，SDK重试0；无模型response或usage。模型circuit立即打开，第二次请求未发送，没有生成或执行候选。原生派发仅prepare一次，complete=1、uncertain=0；VM已停止且PID不存在。运行耗时296.277秒。

| 项目 | 结果 |
| --- | --- |
| 本批模型请求 | 1，超时 |
| 第二次模型请求 | 未发送，circuit阻断 |
| 候选生成/执行 | 0 / 0 |
| 完成pair/credit | 0 / null |
| 模型总输入/输出tokens | null，服务未返回usage |
| 已知返回tokens | 0；不能代替总usage |
| 未知输出预留 | 2048 tokens，保留占用 |
| 总费用 | null，服务价格与usage未知 |
| 历史模型账本 | 6份SHA均未变 |
| 官方episode/ACTC pair/训练样本增加 | 0 / 0 / 0 |

结果记为`BLOCKED_BY_MODEL_SERVICE`。凭证存在，controller和FreeCAD准备成功，因此该阻塞来自本次模型请求超时。API服务的实际生成/计费状态未知，不推断服务侧没有生成；不重发该请求，不清空账本，不恢复剩余一次额度。

## 原始记录与审计

原runner写出的`summary.json`保留`DIAGNOSTIC_ERROR`及已知用量，新增`reviewed_summary.json`明确服务阻塞和总usage为null。这只是事后分类及unknown解释，原模型账本、错误、request与源码快照不变。

独立失败审计核对实际prepare payload、deployed worker SHA、capture state SHA和模型输入；SQLite模型请求唯一一行是`uncertain, reserved=2048, output=null`。确认没有A/B目录或候选派发，旧6份账本未变，VM停止。审计结果`PASS_FAILURE_ACCOUNTING`证明记录完整；模型实验本身仍未完成。

代码实现和mock先验证：模型请求前必须有capture proof，两次请求messages完全相同、第二次不接触首候选/质量、只允许改数值测量属性。返回格式或代码接口失败均保留拒绝，不自动修复。mock用明确人工样本检查管线，不能作为模型成功或原生pair证据。

## 实际命令

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_model_pair.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=0 PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_model_pair.py \
  --dry-run --output results/cli_model_pair_mock_20261021_001
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_cli_model_pair.py \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_model_pair_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_cli_model_pair.py \
  --run results/cli_model_pair_native_20261021_001
```

本批18项新增测试、全项目249 tests、上游CLI7 tests通过。固定upstream tracked文件未变。仅上述真实命令单次开启付费保护，默认0不变；没有模型下载、训练、full-200或veRL。

## GO/NO-GO与下一步

GO：捕获S0再生成候选的接口、失败账本和隔离停止已可用。NO-GO：真实模型pair、算法选择收益和训练，本批没有候选结果。

下一批先解决服务响应时限：已有服务凭证可复用，但60秒没有返回结果，宜把单请求deadline恢复为此前guard使用的110秒，并在新批次明确记录模型时限与总预算。旧失败账本及未知占用保留；不把该调整当作既有请求可自动重试的许可。新批次仍只需同S0的两个候选，拿到实际结果后再决定是否扩展任务。

同一用户继续授权下已定义一次有界服务适配，配置`cli_model_pair_service_fix_20261021.json`、新账本、新S0，单请求110秒、模型窗口300秒，最多2请求。两批累计最多3实际模型请求，SDK重试仍0，不追加第三批。19项相关测试及service mock通过。

服务适配已结束，真实返回两候选，用量2144输入/1283输出tokens、API错误0。A通过接口，B的只读`hasProperty('SurfaceArea_mm2')`被原白名单遗漏而拒绝；该轮仅prepare派发，候选未执行，原拒绝与账本保留。总模型请求为3，其中首批超时1、适配成功2，总usage仍因首超时未知而null，已知返回用量单列。

复核B后，白名单只增加固定测量属性的只读查询，未改模型代码。全项目251 tests通过。使用停止的捕获overlay作为只读backing，新执行overlay恢复原seed SHA和canonical state，运行已有A/B，无新增API请求。模型表达式是否合法仍按FreeCAD实际执行记录；不人工改候选、不补模型调用。

恢复执行已结束，两条原代码均失败：A在`setExpression`解析`4 * math.pi ** 2 * Radius1 * Radius2`时返回`Base.ParserError`；B调用`torus_obj.hasProperty`时返回`AttributeError`，当前原生对象没有该方法。白名单允许查询只代表执行范围可接受，不证明当前API存在。B的表达式未执行，不能断言它也已被解析器判错。

恢复执行3次派发全部complete、uncertain=0，耗时245.641秒，VM已停止且原backing磁盘SHA未变。两候选从同一模型请求前保存的seed字节/native state开始，源码原文与模型response核验一致；没有保存artifact，pair invalid、credit=null。失败审计`PASS_PROTOCOL_ACCOUNTING`，不改为Q=0/0或tie。

本轮3台顺序VM、5次原生派发、总耗时791.888秒；没有同时间共享进程。实际模型请求总3，其中超时1、完整response2。已知输入2144/输出1283 tokens，累计总usage因首请求未知而null；旧账本含首失败账本都保留。有效模型pair、官方episode、ACTC pair和训练样本增加均0。

该任务已用于开发，候选接口与响应工程目标属于扩展协议，不能把结果合并进官方baseline成功率。相同响应终局Q与credit选择当前一致，方法优势仍需独立任务和等预算对照。完整交接见`HANDOFF.md`、`docs/CLI_MODEL_PAIR.md`和`CLI_MODEL_PAIR_STATUS.json`。

最新判断：模型服务在110秒配置下已返回，但真实候选因表达式/API错误没有完成。pipeline与失败保留GO；有效模型pair、方法优势、训练NO-GO。下一步宜先做公开FreeCAD表达式/API说明对照，使用`PropertiesList`查询和实际版本的表达式语法资料，说明只提供接口通用知识，不包含任务答案。固定同S0、同模型、同采样和执行预算，再验证新候选，不重开本批或改写原代码。

恢复执行与审计命令：

```bash
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_cli_model_pair.py \
  --config configs/cli_model_pair_service_fix_20261021.json \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_model_pair_service_native_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/execute_saved_cli_model_pair.py \
  --source results/cli_model_pair_service_native_20261021_001 \
  --runtime-config results/cli_focus_runtime_20261021.json \
  --output results/cli_model_pair_saved_execution_20261021_001
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/audit_saved_cli_model_pair.py \
  --run results/cli_model_pair_saved_execution_20261021_001
```

## 最终交付核验

156份公开证据的来源与副本SHA全部核验通过，108份JSON/JSONL严格解析通过，编码原生payload和私有凭证扫描命中0。模型原response、失败账本摘要、源码快照、同S0恢复和完整trace公开；FCStd、VM/固件、SQLite、含二进制payload的controller原响应未上传。

9份中文文档按“好好说话”和anti-defensive-writing核对事实与范围，四项机械扫描命中均0，无需豁免。`git diff --check`通过，全项目251 tests、上游CLI7 tests通过。失败/拒绝/执行源记录保持原样，旧7份模型账本均未改。
