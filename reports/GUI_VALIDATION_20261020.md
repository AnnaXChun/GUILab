# GUI 单题复测

本轮在[无模型GUI控件验收](GUI_CONTROLS.md)通过后，使用新官方原始base overlay运行`freecad-sketch-061`。模型服务别名为`qwen3.5-122b-a10b`，图片能力已在历史探针验证，本次只读`/models`检查HTTP 200且存在该别名，没有额外图片生成探针。

实现提交为`77d10d070757fcaebe6f7aca0783fe89849dd75d`，pinned upstream仍为`e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。运行时CAD源码与实现提交一致；报告在运行期间补充，submodule历史CLI/results保持未跟踪。原始GUI runner、模型adapter、parser、官方评分器与diagnostics复用pinned源码，tracked upstream未改。

## 本轮设置

| 项目 | 设置 |
| --- | --- |
| run ID | `gui_validation_qwen122_20261020_001` |
| 任务 | `freecad-sketch-061`，已反复用于调试，不作独立held-out估计 |
| 模型 | `qwen3.5-122b-a10b`服务别名，thinking=false；不证明后端权重哈希 |
| 环境 | Mac ARM原生QEMU/TCG，官方qcow2，2 vCPU / 8 GiB，FreeCAD 1.1.0，1920×1080 |
| GUI协议适配 | normalized1000 v2；原始和实际像素动作均记录；动作后等待由0.3改为5秒 |
| 桌面适配 | 新overlay显式将GNOME alive timeout从5000设为600000ms，读取原值并验证读回；最大化窗口、启动前后单实例核验 |
| 工程预算 | 最多25次生成、16000输出tokens，每次1024输出tokens；模型wall 1200秒，整进程3000秒 |
| 账本 | 新增且仅限本轮的`results/gui_validation_20261020/model_batch.sqlite`；此前201次生成的5本历史账本不变 |
| 默认与重试 | 仓库默认付费0，当前命令单次设置1；SDK与非幂等执行自动重试均0 |

可信控件探针的Qt对象摘要、控件坐标和0.7秒鼠标停留序列均未加入模型baseline。模型从空GUI开始，通过自己的截图与动作完成任务；探针文件没有进入其VM。

## 实际命令

```bash
ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui \
  --model qwen3.5-122b-a10b --qwen-no-thinking \
  --qwen-coordinates normalized1000 \
  --run-id gui_validation_qwen122_20261020_001 \
  --task-id freecad-sketch-061 \
  --runtime-config results/gui_validation_20261020/runtime_config.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/gui_validation_20261020/model_batch.sqlite \
  --campaign-config configs/gui_validation_20261020.json
```

这里的runtime配置是本机资产路径。远程应核验自己的base/固件SHA与无模型环境验收，不将历史绝对路径当成可用路径。已执行批次不能更换ledger重新跑25次；配置保留用于审查与dry-run。

## 结果

本次完成了官方reset/action/evaluation闭环，状态`EVALUATED`，官方strict=0、`failure_class=no_output_file`。25轮均有模型响应，25次生成、88918输入tokens、2328输出tokens，无API错误、无未知usage，无原生文件；原生审计为`NOT_RUN_NO_ARTIFACT`。上游GUI结果没有单独termination字段，轨迹用满25步且没有DONE动作。不是宏超时或本轮运行错误。

第2轮把所述“Empty File”点到了2D Draft卡片，随后在工作台选择上消耗多轮。第14轮打开Sketcher的Choose Orientation；第15–25轮未确认成功，实际点击多次落在约(495,606)的对话框外空白处，另一次(939,606)也未落在OK按钮上。原始normalized动作、实际pixel动作和截图共同保留。这里能确认本轮定位失败，不能据此把历史GUI失败全部归为同一根因。模型没有获得Qt坐标或人工纠正。

| 项目 | 本轮结果 |
| --- | --- |
| 官方GUI评分 | 0.0，完整有效评估 |
| 模型请求与用量 | 25次；input 88918 / output 2328 tokens |
| 共享预算剩余 | 0次调用；剩余输出额度不能用来绕过调用上限 |
| 原生文件与审计 | 0文件，NOT_RUN_NO_ARTIFACT |
| 宏与桌面 | GUI ready，空文档、最大化、活动窗口、PID与单实例核验通过；本轮模型启动ack约218.912秒 |
| 清理与资产 | VM退出码0，本项目QEMU进程0；原base与固件SHA前后不变 |
| 费用 | 美元费用null，服务价格未知；不报0 |

完整[JSONL与清单](evidence/gui_validation_20261020/INDEX.json)、[机器摘要](evidence/gui_validation_20261020/gui_validation_20261020/summary.json)保留。运行前先冻结代码commit；运行后将37个当前cad_cf文件逐一与该commit比较并归档为`posthoc_source_snapshot`。这是运行后核对，不声称有本轮首次请求前自动快照。

随后用实际第24步截图与第25步原始返回，通过pinned agent和mock SDK做两轮离线复放，`PASS_OFFLINE_PROTOCOL_REPLAY`。两轮请求中的当前图片均与原PNG字节一致，分辨率1920×1080；normalized `(258,561)`确实映射为执行的pixel `(495,606)`，在线history保持normalized单位，没有回灌pixel动作。零网络、零模型生成，仅为本地协议验证；不验证服务端内部图像处理，也不计新episode。证据见[离线复放清单](evidence/gui_protocol_replay_20261020/INDEX.json)。

远程可直接使用已归档截图复验，不需要VM或API key：

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/replay_gui_protocol.py \
  --episode reports/evidence/gui_validation_20261020/official_gui/gui_validation_qwen122_20261020_001/freecad-sketch-061 \
  --output results/my_offline_gui_replay.json
```

加入此前历史后，累计226次生成、11个attempt、9个有效评估episode、2个历史运行/诊断错误，涉及2个不同任务；已知输入791185/输出25713 tokens。早期HTTP500未知usage和128-token占用保留，完整token总量与美元总费仍为null。原有5本账本及其失败不变，本轮新增25次账本也已用尽。

原论文GUI-only、显式坐标适配GUI、CLI和CADWorld-Hybrid分别报告，不合并成功率。本轮不是ACTC配对；真实pair仍为0。GUI控制基础设施和离线协议复放GO，模型GUI任务成功与原生GUI产物NO-GO；正式TypedWorker/GUI bridge同步、same-S0双clone和P3/P4未放行。下一步做正式worker同步验收；不继续追加本轮生成，不重开旧账本。
