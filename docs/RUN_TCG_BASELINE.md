# 在无 KVM 环境执行小批 baseline

首批15次请求及失败保留，后续CLI单题已通过官方评分与122B原生审计；Qwen3.6原文件Invalid失败仍保留。GUI仍无成功文件，当前停止新增推理。最新结果见[单题续跑](../reports/BASELINE_SUCCESS_SMOKE.md)，下一步按[阶段验收](NEXT_ACTC_VALIDATION.md)做无模型GUI诊断与同步/隔离。下方Qwen3.5/15次命令属于历史首批，不能在新账本重复执行；原Python入口复用见[官方sh核对](../reports/UPSTREAM_SH_REUSE.md)。

2026-10-19 用户要求当前会话继续解决 GUI 宏超时并真正开始 baseline。这项新授权将此前“本机只做无模型检查”的执行位置限制扩展到当前 Mac；模型请求仍受首批 15 次、16000 输出 tokens 上限约束。没有接口与凭证时不调用模型，也不以 mock 冒充真实实验。

## 配置与启动条件

```bash
bash scripts/bootstrap.sh --baseline
cp .env.example .env
```

在项目根 `.env` 中填写 `CADWORLD_API_BASE_URL`、`CADWORLD_MODEL_NAME`、`CADWORLD_API_KEY`。GUI 需要支持图片输入；本批优先使用 OpenAI Chat Completions 兼容接口。密钥只从所选环境变量或 ignored `.env` 读入，通过进程环境注入 SDK；命令、dry-run、launch manifest 均不包含 key 值。

用户指定开源多模态 Qwen3 系列。本轮选服务实际列出的 `qwen3.5-35b-a3b`，图片验证已返回 `FREECAD`，3 个输出 tokens。后续命令均加 `--model qwen3.5-35b-a3b --qwen-no-thinking`。GUI 复用 pinned `baseline/Qwen3-6/adapter.py`，设置 `--think_level none`；CLI 复用 `--send-chat-template-kwargs`，保持 `enable_thinking=false`。这是接入已有服务，不下载或部署模型权重；服务返回的模型名不是后端权重哈希证明。

复制 `configs/native_tcg.example.json` 到 ignored results，为当前实际资产填写路径，先独立计算 qcow2 和固件 SHA。每次 launch 使用新的 `output`，不得复用已运行的 runtime 目录；不要把本机固件路径当作远程已存在的文件。探针和 runner 都不会自动下载 VM、模型或推理服务。

## 无模型验收

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/probe_baseline_env.py \
  --config results/my_tcg_config.json \
  --output results/my_env_acceptance
```

这条命令实际使用 pinned `DesktopEnv`，冷启动新 overlay，等待 GUI readiness 宏确认文档集为空，再做 `reset → observe → pyautogui action → observe → close`。生成 `acceptance.json`，必须为 `PASS_BASELINE_INFRASTRUCTURE`，且资产 SHA 与后续 runtime 配置一致。这个 PASS 只验收基础设施，不代表已完成 CADWorld 模型任务。

`cad_cf.upstream_runtime` 按 pinned `metrics/getters/__init__.py` 的导出表延迟导入原始函数，避免为 part/sketch 加载无关 Office/OCR 模块；没有替换 metric/getter 实现或评分规则。原始 CLI 也可使用该导入适配做 dry-run：

```bash
cd vendor/CADWORLD
PYTHONPATH=../..:. ../../.venv/bin/python -m cad_cf.upstream_launch \
  --kind cli --lightweight-imports --log ../../results/cli_preflight_usage.jsonl \
  -- --dry-run
cd ../..
```

完整 upstream 全量 sync 和参考 Linux/KVM 环境仍单列为未完成；不能把这条适配 dry-run 写成全部 405 个官方依赖已安装。

## GUI 超时的处理

`cad_cf.gui_startup` 直接启动同一 snap 安装中的 FreeCAD ELF，沿用 snap 的 Python/库路径，显式使用当前 X11 display；不覆盖 HOME。可信输出目录在部署宏时写入，避免依赖 GUI/snap 对自定义环境变量的继承。仅在私有 overlay 内禁用镜像的 FreeCAD 自动启动条目，并结束已有启动实例。GUI ack 后再核验 PID；若仍有已启动的空白 autostart 实例则结束它，发现其他带文档参数的实例就拒绝验收。原始 qcow2 不变。固定 native GUI 探针增加分阶段 JSONL，能分辨是否进入宏、是否完成几何、保存重开和 GUI 刷新。

GUI readiness 宏只检查空文档集、版本、workbench 和窗口可见性，不创建任务几何，不预填答案。真实 baseline 的 prompt、parser、agent、任务 config、评分与 diagnostics 都来自 pinned upstream。

后续可选 `gui_warmup` 曾创建0对象的临时空文档、渲染后关闭；ack 成功的 GUI100 仍卡在欢迎页，50次请求后主动阻断。该尝试按诊断失败单列，不能把 ack 当作交互验收。恢复复测显式关闭 `gui_warmup`，不根据这一单例声称已确定根因。Qwen 的 `--qwen-coordinates normalized1000` 会追加坐标合同并转换绝对鼠标位置，这是原 GUI-only 基线的接入差异，必须与原像素合同结果分开。

本轮可信 GUI 建模探针已成功。多个启动条件共同变化，尚不能唯一归因旧宏失败；不能把“某个环境变量就是根因”写成已证实结论。实际时延和失败见最新报告。

## 运行已授权的小批

先使用无模型验收得到的**空 FreeCAD GUI**截图，验证一次图片 API 请求。勿使用可信圆柱探针文件作为 baseline 的初始工程或产物。

```bash
ENABLE_PAID_RUNS=1 .venv/bin/python -m cad_cf.model_probe \
  --model qwen3.5-35b-a3b --qwen-no-thinking \
  --screenshot results/my_env_acceptance/reset.png \
  --output results/endpoint_001 \
  --batch-ledger results/first_baseline_batch.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui-connect \
  --model qwen3.5-35b-a3b --qwen-no-thinking \
  --run-id gui_sketch_001 --task-id freecad-sketch-061 \
  --runtime-config results/new_gui_sketch_tcg_config.json \
  --environment-evidence results/my_env_acceptance/acceptance.json \
  --batch-ledger results/first_baseline_batch.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind gui-connect \
  --model qwen3.5-35b-a3b --qwen-no-thinking \
  --run-id gui_part_001 --task-id freecad-part-076 \
  --runtime-config results/new_gui_part_tcg_config.json \
  --environment-evidence results/my_env_acceptance/acceptance.json \
  --batch-ledger results/first_baseline_batch.sqlite

ENABLE_PAID_RUNS=1 bash scripts/run_baseline.sh --kind cli \
  --model qwen3.5-35b-a3b --qwen-no-thinking \
  --run-id cli_001 --runtime-config results/new_cli_tcg_config.json \
  --environment-evidence results/my_env_acceptance/acceptance.json \
  --batch-ledger results/first_baseline_batch.sqlite
```

两道 GUI 题分别 launch，使用 upstream `--domain` 过滤同一 smoke manifest，避免第二次冷启动占用前一题的模型计时窗口；不增加整批调用额度。GUI 为 sketch-061、part-076 各最多 3 turns、每次最多 512 输出 tokens；CLI 只运行 sketch-061，最多 8 turns / terminal calls、12000 输出 tokens。整批包含 1 次最多 128 输出 tokens 的 endpoint 验证，共用 SQLite 账本，上限 15 次、16000 输出 tokens。失败或进程崩溃留下的未知请求会关闭账本，不会自动重发。不能换新账本绕过第一批上限。

SDK 关闭重试。GUI `/execute` 使用持久化一次派发账本；CLI 保留 pinned runner 的一次 `/execute` closure。模型 wall gate 从首次请求开始，包含该 launch 后续间隔，上限 600 秒；每次请求上限 110 秒。OS boot 与 GUI bootstrap 分别限时，整个 runner 进程上限 1800 秒，超时终止该运行的进程组，避免留下 QEMU。

实际批次先前已有 1 次 GPT 图片验证失败（HTTP 500，usage 未返回）。用户随后明确改用 Qwen3，账本记录配置变更后才恢复执行；失败请求及 128-token 未知占用仍保留。Qwen 图片验证额外使用 1 次，因此 GUI 两题若各用满 3 次，CLI 剩余最多 7 次。入口按共享账本剩余请求数自动收紧 CLI，不能换新账本或删除失败记录恢复额度。

当前仅开放这批 gui-connect/CLI；`gui-25` 不在当前授权批次。GUI 禁用视频录制以控制 TCG 负担，仍保留原始截图、轨迹、评分与 diagnostics。这个录制差异、TCG、固定 GUI bootstrap、导入适配、一次执行 guard 均须记录；官方 GUI-only、CLI 和 Hybrid 分开统计。

## 实时桌面

已有 `launch.json` 后，可打开只读的本机查看页；不修改 VM 网络认证，不需要配置 VNC 密码：

```bash
.venv/bin/python -m cad_cf.desktop_viewer \
  --launch results/my_runtime/vm_001/launch.json --port 15011 --seconds 900
```

浏览器访问 `http://127.0.0.1:15011`。页面读取 QMP framebuffer，不显示宿主桌面，也不向外部网络传输。VM 停止或 900 秒到期后 viewer 退出；截图与日志仍留在 run 目录。它只供人观察，不给 CLI agent 增加运行时截图。
