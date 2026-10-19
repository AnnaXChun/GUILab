# pinned CADWorld 的 sh 能怎样复用

核对 commit：`e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。可以复用脚本里的原 Python runner、模型 adapter 和工具协议；本机不能原样执行整批脚本。以下结论来自脚本原文，未修改 upstream tracked 文件。

## GUI 的真实入口

`baseline/Qwen3-6/experiment_qwen3_6.sh` 设置 `CADWORLD_BASELINE_PROVIDER=Qwen3-6`，然后调用 `uv run python scripts/python/run_cadworld.py`。主要参数如下。

| 参数 | pinned sh | 本轮单题复测 |
| --- | --- | --- |
| 模型 | `Qwen/Qwen3.6-35B-A3B` | 已有服务实际列出的 `qwen3.6-35b-a3b` |
| 服务 | `local`、`http://localhost:8001/v1` | 用户已有的兼容 API，地址不公开 |
| 推理模式 | `--think_level none` | 相同，使用原 Qwen adapter 的 chat-template 参数 |
| 任务清单 | `evaluation_examples/test_rest.json` | 固定 smoke manifest，用原 `--domain sketch` 只取 sketch-061 |
| 决策轮数 | `--max_steps 100` | 首个续跑25轮；预热100步尝试在50次生成后诊断中止；撤掉预热的独立复测最多50轮 |
| 历史窗口 | `--max_trajectory_length 10` | 沿用原 runner 默认 10 |
| 动作后等待 | `--sleep_after_execution 0.3` | 沿用原默认 0.3 |
| VM | 官方 qcow2、原 provider | 同一官方 qcow2，外部接 native QEMU/TCG 生命周期 |

关键缺项：pinned commit 中没有该脚本引用的 `evaluation_examples/test_rest.json`，`Path.exists` 与 `git ls-tree HEAD` 均核对为空。存在的 `test_small.json` 为 50 题、`test_all.json` 为 200 题。不能因脚本写了路径就假定对应资产已提交。

脚本末尾不透传 `"$@"`，模型、服务、任务清单和 max_steps 都是固定值。因此不能靠在 `bash experiment_qwen3_6.sh` 后追加参数来可靠地变成单题。当前外层 launcher 调用的是同一个原 Python runner，替换必要参数并加零重试/预算保护；没有另写 GUI agent 或评分器。

`baseline/Qwen3-6/run_vllm_qwen3_6.sh` 是服务端启动脚本，固定 `CUDA_VISIBLE_DEVICES=3`，运行 `vllm serve Qwen/Qwen3.6-35B-A3B`，启用 `--reasoning-parser qwen3`、`--enable-auto-tool-choice` 和 `--tool-call-parser qwen3_coder`。本机不具备其 NVIDIA CUDA 条件；已有模型服务也无需重新下载/部署 35B 权重。本轮没有执行该服务脚本。

## CLI 的真实入口

`CLI/launch_wave1.sh` 会启动 Qwen、Holo、Kimi、MiniMax 四个 tmux 任务。Qwen 使用 `CLI/run_cli.py`、Qwen3.6、本地 8001 服务、`--send-chat-template-kwargs`，并选择 `test_small.json` 的 50 题。它不是单题连接 smoke 脚本。

| 参数 | pinned wave sh | 本轮 CLI |
| --- | --- | --- |
| wall | 1200 秒 | 1200 秒 |
| 累计输出 | 51200 tokens | 16000 tokens，另受整批 32000 上限约束 |
| 单轮输出 | 8192 tokens | 4096 tokens |
| turns / terminal calls | 10000 / 10000，实际由 wall/tokens 截断 | 20 / 20 |
| 任务 | 50 题 | sketch-061 一题 |
| prompt / tools / parser | 原 CLI | 完全复用，没有注入答案脚本、API 修复提示或评分反馈 |

本轮 CLI 已成功：14 次生成、13 次 terminal 调用，5823 输出 tokens，agent 140.134 秒，官方 strict=1.0；第 12 次 terminal 才保存，第 13 次重新打开并重算，最后 finish。此前 7 轮不能覆盖这条实际成功轨迹。模型版本和预算也同时变化，不能把结果解释为单一因素的效果。

## GUI 坐标兼容

用同一个 pinned GUI agent 在公开启动截图上作了一次未执行动作的合同探针。原像素 adapter 下，Qwen3.6 输出 `(841,740)`；截图为 1920×1080，位置不在 Done 按钮。显式要求 0..1000 坐标后，模型输出 `(842,739)`，外层转换为 `(1617,798)`。

新增 `--qwen-coordinates normalized1000` 是明确的模型接入适配：转换绝对鼠标位置，保留键盘、相对位移、scroll 数量；不猜坐标单位，不接受越界/动态坐标。原始输出、转换后的 action 和实际 screenshot 均保留。它不提供按钮位置或 CAD 答案；原像素协议失败与新 adapter 结果分开报告，不混称为完全相同的原始协议。

v1适配的恢复运行在第6轮暴露混合单位history：模型照抄前轮pixel值，触发越界拒绝。v2保留原`predict`和parser，通过外层`_remember_turn`适配使在线历史的action统一以normalized单位表示，实际返回的pixel action和JSONL不变，并增加显式mapping元数据。无网络两轮测试验证了模型历史与执行输出各自的单位；这是接入修复，不能与原像素协议合并报成功率。

## 可复用的本机命令

```bash
ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind cli \
  --task-id freecad-sketch-061 --model qwen3.6-35b-a3b --qwen-no-thinking \
  --campaign-config configs/baseline_success_20261019.json \
  --run-id success_cli_qwen36_001 \
  --runtime-config results/baseline_success_20261019/runtime_cli.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/success_batch_20261019.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui-25 \
  --task-id freecad-sketch-061 --model qwen3.6-35b-a3b --qwen-no-thinking \
  --qwen-coordinates normalized1000 \
  --campaign-config configs/baseline_success_20261019.json \
  --run-id success_gui_qwen36_001 \
  --runtime-config results/baseline_success_20261019/runtime_gui.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/success_batch_20261019.sqlite
```

以上 run ID 已用于真实执行，不能覆盖重跑；移机时路径、资产与共享预算必须恢复或重新核验。默认付费仍为 0，本轮依据用户“继续跑，直到模型任务能够成功”的新授权开独立续跑批次，首批 15 次的账本与失败不变。

后续实际执行的两条GUI命令如下，第一条已因欢迎页不响应而停止计费。它完成50次生成，之后原adapter的50个WAIT没有请求模型，不能视为100次完整模型决策。第二条撤掉预热、使用全新overlay，最多50次；两次生成合计不超过100，前一账本保持blocked，不清空消耗。

```bash
ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui \
  --task-id freecad-sketch-061 --model qwen3.6-35b-a3b \
  --qwen-no-thinking --qwen-coordinates normalized1000 \
  --campaign-config configs/baseline_gui100_20261019.json \
  --run-id success_gui_qwen36_100_001 \
  --runtime-config results/baseline_success_20261019/runtime_gui100.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/gui100_batch_20261019.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui \
  --task-id freecad-sketch-061 --model qwen3.6-35b-a3b \
  --qwen-no-thinking --qwen-coordinates normalized1000 \
  --campaign-config configs/baseline_gui_recovery_20261019.json \
  --run-id success_gui_qwen36_recovery_001 \
  --runtime-config results/baseline_success_20261019/runtime_gui_recovery.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/gui_recovery_batch_20261019.sqlite
```

前一恢复run在6次后结束，协议v2沿用同一本recovery账本，实际新run的max_steps与生成上限自动收紧至44：

```bash
ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui \
  --task-id freecad-sketch-061 --model qwen3.6-35b-a3b \
  --qwen-no-thinking --qwen-coordinates normalized1000 \
  --campaign-config configs/baseline_gui_recovery_20261019.json \
  --run-id success_gui_qwen36_history_001 \
  --runtime-config results/baseline_success_20261019/runtime_gui_history.json \
  --environment-evidence results/baseline_debug_20261019/desktop_env_acceptance_003/acceptance.json \
  --batch-ledger results/gui_recovery_batch_20261019.sqlite
```

## 代码检索验证

按用户要求使用本地 codebase-memory CLI。沿用工具返回的两个绝对路径项目标识，分别核对 main 与 upstream DETACHED commit；fast 索引最初排除了 scripts，改用 full 后读取原 `.sh`、API agent、CLI prompt 和调用关系。索引仅在本地，缓存、索引与诊断日志不上传。最终提交仍以 git diff 为准，代码正确性另由单测与真实运行验证。
