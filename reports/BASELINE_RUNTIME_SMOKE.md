# 本机 GUI 与 baseline 运行记录

本轮使用同一官方 qcow2，在 Mac ARM 原生 QEMU/TCG 下接入 pinned CADWorld runner。可信 GUI 建模与单实例空 GUI 验收已经通过；真实模型任务、成本和结论见下方本批结果。TCG 结果单独报告，不能作为参考 Linux/KVM 硬件复现或论文全量成功率。

## 环境与版本

- upstream：`e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，tracked 文件未修改。
- 宿主：Apple M5 Pro，ARM64，48 GiB；ARM 原生 QEMU 11.1.2，TCG，guest 2 vCPU / 8 GiB，无 KVM。
- 官方 qcow2：28,310,503,424 bytes，SHA256 `edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12`。
- 官方固件 SHA256：`2df617a6fd1bae41ec7c0e3bceca96c928a5a88d8dc198468d34733393ab2792`。
- guest FreeCAD：1.1.0；Python 依赖使用 pinned lock 中的 16 个 baseline 直接版本，未安装全部 405 个上游包，未下载模型或 OCR 权重。
- 模型：服务实际列出的 `qwen3.5-35b-a3b`，用户指定开源多模态 Qwen3 系列；图片验证返回同一 model ID。服务别名不证明实际后端权重哈希。

## GUI 宏与单实例

`visible_gui_001` 在真实 FreeCAD GUI 内完成 Body → Sketch → Pad，半径 5、Length 10 → 12，保存关闭重开两次；形体有效、1 solid、2 constraints、Profile 和 Body Tip 保留。宏开始后用时 98.886 秒。原生文件 SHA256 `d93b982b1a29de4c1551288406fdd0c61e1b83dc37b5ca9dd118d697589856e2`。它是可信固定探针，`agent_generated=false`，不能计模型成绩。

启动改为同一 snap 内的 FreeCAD ELF，沿用 Python/动态库路径、不覆盖 HOME；显式 X11 display，宏输出目录固定嵌入。仅在私有 overlay 禁用镜像 autostart，结束启动实例。GUI ack 后再次核验 PID，只清理额外的无文档参数空白 autostart 实例；其他实例直接拒绝。多项条件共同变化，旧超时的唯一根因仍未确定。

| 无模型验收 | 实际结果 | 处置 |
| --- | --- | --- |
| `desktop_env_acceptance_001` | 原始记录为基础设施 PASS，之后只读诊断发现两个空白 GUI | 新 gate 拒绝缺少 singleton 证据的历史 PASS，原始记录保留 |
| `desktop_env_acceptance_002` | 单实例边界成功，但新序列化代码写入字面换行，主机读取 JSON 失败 | 全次记 FAIL；原畸形 bytes 保存在 `gui_ready.malformed.txt`，补回归测试后再运行 |
| `desktop_env_acceptance_003` | `PASS_BASELINE_INFRASTRUCTURE`，空文档集，PartDesignWorkbench，单实例；reset/observe/action/observe/close 通过 | controller 151.027 秒后就绪，GUI 准备另用 340.325 秒；已停机 |

003 的 GUI PID=2006，清理迟到的空白 autostart PID=1966。没有给任务创建任何几何。固定 mouse move 仅验证动作链路。

## 模型与预算

默认 `ENABLE_PAID_RUNS=0` 保留；本轮真实小批已有用户授权，单次命令设为 1。共享账本为 ignored `results/first_baseline_batch.sqlite`，整批 15 次生成 / 16000 输出 tokens，SDK 自动重试 0；GUI 两题各最多 3 turns，每次最多 512 输出；CLI 额度按剩余调用收紧，不能分别重置。

早期 GPT 图片验证发出 1 次请求，HTTP 500，usage 未返回，按未知占用预留 128 tokens。第一次错误采集未保存 body/request ID，后续已补采集，但不追补不存在的证据。用户随后明确要求 Qwen3，记录 correction 后才恢复账本；失败行仍保留。中间 `endpoint_qwen_001` 因账本未恢复而本地拒绝，网络生成调用为 0；`endpoint_qwen_002` 图片请求成功，回答 `FREECAD`，输入 2077、输出 3 tokens。

GUI 复用 pinned `baseline/Qwen3-6/adapter.py`，`--think_level none`；CLI 复用 `--send-chat-template-kwargs`，默认 thinking=false。图片 probe 同样发 `enable_thinking=false`。禁用 thinking 用于本次有限连接 smoke，不代表论文默认推理设置。

GUI/CLI `/execute` 均单次派发；结果不确定时停止 VM 并隔离，不重发。GUI 仍用原 prompt/parser/action loop，CLI 仍用原 terminal prompt/tools/parser。评分与 diagnostics 只在 episode 后执行，没有把 expected、reference 或评分输出传入在线 agent。

## 实际命令

运行位置为项目根；忽略目录内保存原始命令和日志，公开副本已移除 key、真实 endpoint 和完整服务模型目录。

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent

ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_baseline_env.py \
  --config results/baseline_debug_20261019/desktop_env_config_003.json \
  --output results/baseline_debug_20261019/desktop_env_acceptance_003

ENABLE_PAID_RUNS=1 .venv/bin/python -m cad_cf.model_probe \
  --model qwen3.5-35b-a3b --qwen-no-thinking \
  --screenshot results/baseline_debug_20261019/desktop_env_acceptance_003/reset.png \
  --output results/endpoint_qwen_002 --batch-ledger results/first_baseline_batch.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui-connect \
  --task-id freecad-sketch-061 --model qwen3.5-35b-a3b --qwen-no-thinking \
  --run-id baseline_gui_sketch_001 \
  --runtime-config results/baseline_debug_20261019/runtime_gui_sketch.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/first_baseline_batch.sqlite
```

上述探针各次实际参数以归档的 config、source snapshot 和 console 为准。原始 CLI dry-run 使用 `cad_cf.upstream_launch --kind cli --lightweight-imports` 执行 pinned `CLI/run_cli.py --dry-run`，已通过；这不等于全部上游依赖安装完成。

## 证据位置

公开归档为 [evidence/baseline_runtime_20261019](evidence/baseline_runtime_20261019/INDEX.json)，包含逐次失败、JSONL、当次派发源码、截图、预算与脱敏日志。INDEX 记录公开文件 SHA 和原始文件 SHA，脱敏字节差异显式标注。002 畸形 JSON 改为 `.txt` 保留原始 bytes。完整模型目录、`.env`、SQLite、qcow2、固件、FCStd 和持续写入的 viewer frame 不进 Git。

原始日志和大型产物只存在本机 ignored results，远程不能假定它们已随 clone 取得。真实 artifact 若产生，只报告其实际路径、SHA 和实际完成的校验；ZIP 内有 Document.xml 不能证明 FreeCAD 可重开或保留参数化历史。可信 GUI 探针文件不补入 baseline 输出。

## 后续实际启动命令

```bash
ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui-connect \
  --task-id freecad-part-076 --model qwen3.5-35b-a3b --qwen-no-thinking \
  --run-id baseline_gui_part_001 \
  --runtime-config results/baseline_debug_20261019/runtime_gui_part.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/first_baseline_batch.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind cli \
  --task-id freecad-sketch-061 --model qwen3.5-35b-a3b --qwen-no-thinking \
  --run-id baseline_cli_sketch_002 \
  --runtime-config results/baseline_debug_20261019/runtime_cli_sketch_002.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/first_baseline_batch.sqlite
```

CLI 首次 `_001` 因 pinned runner 的 results-dir 边界检查而在启动前 exit=2，没有 VM 或模型调用。最小修复为先在 upstream `CLI/results/actc/<run_id>` 运行，结束后原样复制到项目 results；未改上游检查，未绕过为 symlink。新计划已通过实际 CLI dry-run，后续使用新 run ID `_002`，原失败保留。

## 本批最终结果

3 个真实 episode、2 个不同任务均已完成官方评估；strict 均为 0，failure_class 均为 `no_output_file`，agent 原生输出文件共 0 个。三次均没有 API error、pipeline error 或不确定执行；CLI 的 7 个已知错误命令属于模型任务失败。此前 CLI `_001` 参数错误不计 episode。不能把这批写成任务成功或论文 baseline 已复现。

| run ID | 协议 / 任务 | 模型请求 | 输出 tokens | strict | 原生文件 | 记录时长（秒） |
| --- | --- | --- | --- | --- | --- | --- |
| `baseline_gui_sketch_001` | GUI / sketch-061 | 3 | 219 | 0 | 无 | 531.694 |
| `baseline_gui_part_001` | GUI / part-076 | 3 | 196 | 0 | 无 | 535.447 |
| `baseline_cli_sketch_002` | CLI / sketch-061 | 7 | 951 | 0 | 无 | 556.986 |

时长为 host console 首末日志间隔，包含冷启动，不是精确 provider latency。CLI 原 runner 的 agent_seconds=103.027、task_seconds=153.501、termination=turn_limit、terminal_calls=7。三个 VM 的 controller/GUI 准备分别为 133.987/273.887、128.197/296.955、150.214/222.636 秒，两项顺序执行。

GUI 两题各连续 3 次点击 `(842,737)`，未关闭欢迎页。1920×1080 截图中，若按 0..1000 归一化解释，换算约为 `(1617,796)`，接近 Done 按钮；这是待独立验证的坐标合同问题，不是已证实的唯一根因。保留原始动作，没有事后改坐标或补轨迹。

CLI 七次终端返回码均为 1。前几轮使用错误的 `Part::Line` 属性或不存在的 `Part::LineSegment` 文档类型；后几轮使用 `doc.save(path)`，接口返回不接受参数。模型没有在本批修复为正确的保存用法，也没有保存文件。未由可信脚本替模型完成任务。

整批累计 15/15 次生成：早期 GPT 失败 1 + Qwen 图片验证 1 + GUI 6 + CLI 7。成功响应已知输入 28304、输出 1369 tokens；初次 GPT 500 的实际 usage 未知，保留 128-token 占用。总输出与美元费用为 null，不能把未知部分报成零。剩余生成请求=0，剩余保守输出上限=14503；调用次数先达到边界，不再新增请求。另有只读模型目录健康检查，不计生成请求；完整目录未上传。

两道 GUI 的执行账本各有 3 次已完成 action dispatch；CLI 有 7 次已完成 terminal dispatch，加 1 次任务 setup。没有 uncertain 任务变更。所有本批 QEMU 和 viewer 已退出，官方 base 和固件完整 SHA 再校验一致，上游 tracked 文件未改。项目最终 96 tests（3.59 秒），上游 CLI 7 tests，通过；没有为追求成功追加运行。

GO：baseline 基础设施与受限 GUI/CLI 模型循环可运行；可据失败 trace 修正坐标合同并设计下一批验收。NO-GO：声称任务成功或论文复现、继续使用已耗尽的首批调用额度、开始 ACTC pairs、24-pair pilot/full-200/训练。下一步先做离线坐标映射合同检查和 FreeCAD API/saveAs 最小兼容验证，再提出新的明确小批预算；正式 TypedWorker/GUI bridge 与 same-S0 clone 仍须独立验收。

机器可读证据为 [campaign_summary.json](evidence/baseline_runtime_20261019/campaign_summary.json)，完整来源哈希见 INDEX。GUI-only、CLI 和 Hybrid 分开统计；真实 Hybrid pair 继续为 0。
