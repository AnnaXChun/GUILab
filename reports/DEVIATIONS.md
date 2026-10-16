# 差异与适配

| 来源与确切路径 | 实际差异 | 影响与本项目适配 |
| --- | --- | --- |
| `vendor/CADWORLD/desktop_env/providers/docker/provider.py:362` | `save_state` 抛出 `NotImplementedError`；revert 只停止 emulator | 不调用它伪造快照。`snapshot.create_overlay` 要求停机 source disk + SHA；两路独立 disk/VM/endpoint，原生状态与截图再比对 |
| `vendor/CADWORLD/desktop_env/controllers/python.py:136` | GUI `execute_python_command` 内有重试循环 | 配对 GUI/API 共用一次性 `TerminalBridge`，持久化 dispatch ledger。HTTP timeout/5xx 判 outcome uncertain，隔离并销毁 clone，绝不重发 |
| `vendor/CADWORLD/CLI/run_cli.py:420` | CLI 内联 `/execute` closure 不能直接导入复用；snap runtime 有环境预设 | 本项目仅封装同一 endpoint/payload，保留 timeout 和无 shell 暴露。固定 worker 复用 snap 的 PATH/PYTHONPATH/LD_LIBRARY_PATH 设置；不修改 HOME |
| `vendor/CADWORLD/scripts/python/run_cadworld.py:93` | `--download_vm` 默认 true | 启动命令增加 `--no-download_vm`；下载保持显式操作 |
| `vendor/CADWORLD/CLI/prompts.py:39` | normalize 支持三种精确前缀且会 strip/lstrip | 本项目逐字复用同样的前缀规则。raw 保留，effective 单独记录，官方 GUI 使用 raw |
| `vendor/CADWORLD/desktop_env/evaluators/diagnostics.py:717` | diagnostics 读取 evaluator.expected | 仅 `posthoc.py` 离线可信入口引用官方收集/诊断函数；verifier、candidate、router 不导入它，模型不接触 raw task config |
| `vendor/CADWORLD/pyproject.toml` / `uv.lock` | full sync 405 包含大型推理/视觉运行时 | 本机 Mac 先用轻量本项目 venv 跑 upstream CLI 单测；full sync 只预览，原始 CLI dry-run 失败如实保留。Linux 上由 bootstrap --full-upstream 执行完整依赖 |
| SPEC P0–P3 Stop/Go 与无环境静态交付 | 本机不具备 Linux KVM / VM / provider credentials | 真实实验停在 P0；P1–P3 继续静态实现和 mock，所有真实阶段门槛仍为 blocked，不以 synthetic 满足 ≥3 real pairs |
| native fork 工作文件 | 任务公开路径常为 `/home/user/Unnamed.FCStd`，并行 worker 需要每任务私有目录 | NativeBackend 在 guest `/home/user/current` 操作 checkpoint/artifact；正式 post-hoc 前由可信适配层发布已保存文件到任务输出路径。官方 baseline 原路径不变；该发布尚未真实验证 |
| GUI 进程同步 | 上游未提供可复用的同步 FreeCAD GUI IPC | 新增 guest-only loopback/Qt 主线程桥。仅 summary、commit/close、reopen；启动宏是受控 checkpoint 准备步骤。没有桥或无 ack 时拒绝配对；本机未运行 Qt/FreeCAD |
| same-S0 | 精确截图哈希容易受光标/动画/通知影响 | 初版宁可拒绝 pair，要求稳定 workbench/camera/selection/文档集与截图。未用近似截图相等放宽证据 |
| 任务分组 | 原 test_easy/test_small/test_60 重叠，且 precondition 工程可能重复 | 仅公开操作 family + 明确提供的 precondition 文件 SHA 做并集分组，兼顾领域与 edit 初筛池，尽量接近 60/20/20，seed=20261015。完整任务实际 92/25/23，edit 初筛候选 19/7/6；分组完整性优先于精确比例 |
| 原生执行失败的归类 | 已知无效形体与网络结果不确定需要分开 | 文件可重开且终态已知时保留低质量候选；timeout/5xx 或无法恢复终态时判 invalid_pair。全部记录失败分支成本，未知动作数用 null，不当作零成本 |
| verifier unknown | SPEC 允许不适用项重归一化，但未指定 unknown 的乐观处理 | 仅不适用项重归一化；任何适用质量项 unknown 则不产生方向标签。当前目标 grammar 保守，未覆盖项显式 unknown；只在 val 上扩展/冻结规则 |
| `CLI/terminal_agent.py:236` 与 `scripts/python/api_agent.py:732` | SDK client 没有显式禁用默认重试 | 外部 `upstream_launch` 仅覆写 SDK constructor/request 预算，OpenAI max_retries=0、Gemini attempts=1；错误后不再调用 provider，usage 独立 JSONL。未改 prompt、parser 或评分器；原始命令与受限执行命令分开记录，guard 仅 mock transport 验证 |
| P3 24 valid pairs | 默认限 3 live pairs，且没有额外授权 | 24-pair pilot 不启动，NOT_RUN_BUDGET。9 个 mock campaign case 不计入 3 个合法真实 smoke pair 或 24 valid pair 目标 |
| 运行时模型生成 | 本轮凭证/环境不可用 | deterministic candidate stub + reviewed live-plan 接口；没有伪造模型 proposal、tokens、provider 时间或任务成绩。P4 predictor 接口提供，训练 NOT_IMPLEMENTED |

所有上述变化均位于本项目。上游 evaluator、规则、参考 artifact 与 tracked 文件未改动，也未读取 golden `.FCStd` 来生成答案。选样只 hash `fixtures/precondition/` 下明确作为任务输入的文件，未打开这些文件解析几何。真实 native worker 路径目前只静态验证，验收仍需 Linux VM。

## 2026-10-16 Mac 环境验证

用户后续要求“开始验证”，因此在原“Mac 静态开发”边界之外增加独立、限时、无模型的软件模拟检查。它不是正式 baseline，不改变 `preflight.py` 和 `reports/stages.json` 的 Linux x86_64/KVM gate。

| 来源与确切路径 | 实测差异 | 最小适配与影响 |
| --- | --- | --- |
| `desktop_env/providers/docker/provider.py:start_emulator` | 本机为 ARM64，只有 amd64 binfmt；外层 preflight 会拒绝参考环境以外的启动 | 新增 `scripts/probe_mac_vm.py`，以显式 Docker CLI 检查同一官方容器/VM 的基础设施，不声称执行过 `DesktopEnv.reset` 或 baseline runner |
| 官方容器 Config.Entrypoint | `/usr/bin/tini -s /run/entry.sh` 在 QEMU user translation 下立即报 subreaper 不支持 | 保留默认入口失败；显式 `--direct-entry` 直接执行未修改的 `/run/entry.sh`。仅验证短期独立容器，不替换正式 Linux 入口 |
| 官方容器 `/run/network.sh` | legacy iptables 查询失败；模块加载后仍失败，nft 查询也不支持。自动 user fallback 未转发 5000 | 显式 `--user-network` 使用镜像既有 `NETWORK=user`、`USER_PORTS=5000,9222,8080`；不改评分或 guest 工程 |
| 官方容器及 provider 的资源参数 | 参考约 8 vCPU/8 GiB/KVM；本轮为 2 vCPU/8 GiB/TCG | 记录真实时延与超时，不用于等硬件效率比较或 stage PASS |
| pinned `scripts/python/download_vm_image.py` | 单连接传输过慢 | 同一官方 URL 续传，保留失败/切换记录；完整 Python SHA256 与 HF 内容哈希一致后才改为正式 qcow2 文件名。没有替换镜像或重选 benchmark |

逐次命令、结果、截图和清理证据以 `MAC_VM_SMOKE.md` 及其版本化证据为准。没有模型生成、官方评分或真实 pair，不把可信基础设施探针用于 preference 数据。
