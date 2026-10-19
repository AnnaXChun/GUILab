# 复现状态

2026-10-19 更新：本机原生 QEMU/TCG 已完成 3 个真实 baseline episode，strict 均为 0，无模型输出文件。可信 GUI 宏、单实例空 GUI 的 DesktopEnv 闭环和 Qwen3.5 图片接口通过。逐题结果与累计成本见 [本批运行记录](BASELINE_RUNTIME_SMOKE.md) 和 [基线结果](BASELINE_REPRO.md)，历史无模型报告不代表当前调用数。

| 检查项 | 状态 | 证据与限制 |
| --- | --- | --- |
| pinned upstream | PASS | `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，tracked 文件未改 |
| 本项目 + baseline 受限依赖 | PASS | baseline group 的 16 个直接版本取自 pinned lock；没有下载模型权重 |
| upstream 全量依赖 | NOT_RUN | 405 包未全部安装；不能把受限依赖运行通过写成完整 sync |
| upstream CLI unittest | PASS | 本轮重新执行 7 tests |
| 原始 CLI dry-run + 延迟导入适配 | PASS | 原始 `CLI/run_cli.py --dry-run`，保留旧 dotenv 失败；未替换 metric/getter 函数 |
| 本项目单测 | PASS | 96 passed in 3.59s；含预算跨进程、错误隔离、序列化回归、HTTP mock 与结果归类 |
| synthetic campaign | PASS | 9 case，6 valid mock、3 invalid；不能计真实任务或 pair |
| 官方 VM/controller，TCG | PASS | 同一官方 qcow2，ARM 原生 QEMU 11.1.2，2 vCPU / 8 GiB，无 KVM |
| FreeCAD GUI 可信原生建模 | PASS_NATIVE_INFRASTRUCTURE_ONLY | FreeCAD 1.1.0；Body/Sketch/Pad、参数修改、保存关闭重开两次，形体有效；不是模型产物 |
| 官方 DesktopEnv 空 GUI 闭环 | PASS_BASELINE_INFRASTRUCTURE | 003 单实例、空文档、reset/observe/action/observe/close；001 双实例和 002 JSON 失败保留 |
| 模型服务 | PASS_IMAGE_PROBE | 用户配置的服务，`qwen3.5-35b-a3b`，图片识别成功，usage 可计量；服务价格与权重身份未核验 |
| 参考 Linux x86_64/KVM 环境 | BLOCKED_BY_ENV | 用户不能提供 KVM；本机 TCG 独立记录，参考 gate 未改成 PASS |
| 正式 NativeBackend/TypedWorker/GUI bridge | BLOCKED_BY_ENV | 固定可信宏通过不等于正式模块已部署验收 |
| same-S0 双 VM 与真实 ACTC pairs | NOT_RUN | N=0；不能以单路 baseline、mock 或同 VM undo 代替 |
| GUI 25-turn、24-pair pilot、full-200 | NOT_RUN_BUDGET | 不在当前首批授权范围 |
| P4 训练 / P5 veRL | NOT_IMPLEMENTED | 接口和后续方案已交付，本轮不启动 |

[本项目新增] native QEMU provider、GUI bootstrap、endpoint/SDK guard、共享整批账本、一次派发隔离和离线结果汇总已实现。GUI agent、CLI agent、任务 config、官方评分与 diagnostics 复用 pinned 实现。完整 source snapshot、失败 trace、截图与脱敏日志见 `evidence/baseline_runtime_20261019/INDEX.json`。

默认付费为 0；本机同一小批已有用户授权，实际命令单次设为 1。此前 GPT 图片请求 HTTP 500 继续计入额度；用户改选 Qwen3 后记录 correction 才恢复同一本账本。未知 usage 保留 128-token 占用，不能用零成本或新账本覆盖。

P1/P2 静态开发和 9 个 mock case 不代表真实阶段验收。P3 的 ≥3 个合法真实 smoke pairs、差异重测和 24 valid pairs 均未完成，P4 为 NO-GO。SPEC 的阶段门槛继续约束真实实验；TCG 的环境差异和模型差异见 `DEVIATIONS.md`。

下一步先依据本批结果定位模型动作、保存或 CLI 接口问题，再验收正式 worker 与 GUI 同步。不重选 benchmark，不增加未经授权的调用，不把 3-turn smoke 外推为论文 17.5% 或 full-200 成绩。

本批最终：GUI 两题 + CLI 一题，共 3 个真实 episode、2 个不同任务，均有效评估为 strict=0 / no_output_file；没有 agent 原生文件。生成请求 15/15，已知输入 28304 / 输出 1369 tokens，早期 500 的 usage unknown，保留 128-token 占用。全部 QEMU/viewer 已停止，base/固件 SHA 再核验一致。基础设施 GO，模型任务成功/论文复现、追加首批调用与 ACTC pairs 均 NO-GO。项目最终测试仍为 96 passed（最新 3.59 秒），上游 CLI 7 passed；机器可读汇总见本批归档。
