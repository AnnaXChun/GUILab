# GUILab

GUILab 当前承载 CADWorld Counterfactual Tool Credit（ACTC）复现工程。仓库根目录即项目根目录。

远程 Codex 接手请先读 [HANDOFF.md](HANDOFF.md)，将 [REMOTE_CODEX_PROMPT.md](REMOTE_CODEX_PROMPT.md) 作为任务提示；执行约束见 [AGENTS.md](AGENTS.md)。

```bash
git clone --recurse-submodules https://github.com/AnnaXChun/GUILab.git
cd GUILab
bash scripts/bootstrap.sh
bash scripts/test.sh
```

未递归 clone 时，`bootstrap.sh` 会初始化 pinned submodule。以上步骤不启动 VM、不请求模型。远程是否具备 KVM 需要单独检查。全新 clone 的交接验证见 [HANDOFF_VALIDATION.json](reports/HANDOFF_VALIDATION.json)。

[本项目新增] 在同一原生工程状态、同一公开语义子目标下，用隔离 GUI/API 分支采集工程自检 preference。规格见 [SPEC.md](SPEC.md)。上游固定 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。

当前结果：70 个项目测试、7 个 upstream CLI 单测通过；9 个 synthetic dry-run case。真实 VM/API 任务 N=0。P0 live 与 P3/P4 均为 NO-GO，原因见 [复现状态](reports/REPRO_STATUS.md)。

```bash
bash scripts/bootstrap.sh
bash scripts/test.sh
bash scripts/preflight.sh   # Mac / 无 KVM 环境预期 exit 2，并保存 blocker
bash scripts/run_smoke.sh --dry-run --output results/my_mock_run
.venv/bin/python scripts/summarize.py --input results/my_mock_run --output reports/PILOT.md
```

`scripts/*.sh` 支持 `--help`、`--dry-run`，并传播非零退出码。`scripts/verify.py --run-id <new_name>` 保存确切命令、输出和退出码。目录已存在时拒绝覆盖；失败尝试必须留存。完整上游依赖只在 Linux x86_64 上用 `bash scripts/bootstrap.sh --full-upstream` 安装。

真实基线先使用 `bash scripts/run_baseline.sh --kind gui-connect --dry-run` 查看固定命令。`ENABLE_PAID_RUNS=0` 默认关闭实时执行；不自动下载 VM，不启动模型服务，不发起 full-200。基线启动时由外部 SDK guard 强制关闭重试并限制调用数、输出 tokens 与总时长；guard 只经 mock transport 验证，尚无真实 provider 运行。

原生配对入口为 `python -m cad_cf.counterfactual --config configs/smoke.yaml --live-plan <reviewed-plan.json> --output results/<new-run>`。它要求 Linux preflight、P0/P1 的真实验收证据、同一停机 disk checkpoint 的两个新 overlay、当前 native checkpoint、两个固定候选和公开 task view。它不调用模型生成代码。`cad_cf.live.run_plan` 复用 upstream DesktopEnv 启动两个独立实例，拒绝用同 VM undo 冒充恢复。

每个 guest 的 checkpoint 需启动受限 GUI bridge：将本项目固定模块部署至任务目录，在 FreeCAD GUI 的受控启动宏中执行 `from cad_cf.guest_gui_bridge import start; ACTC_BRIDGE = start('/home/user/current')`，确保模块路径已配置。桥只绑定 guest loopback，所有 FreeCAD 操作经 Qt 主线程完成；host 经 `/execute` 访问，不把任意 Python/shell 暴露给 agent。此步骤必须在独立 P1 smoke 验证后才允许 P2。

Native worker 提供 inspect_document、inspect_sketch、set_sketch_constraint、set_object_property、recompute、save_as、verify_document、create_sketch、create_pad。所有写入检查 Name、TypeId、属性类型和任务路径；保存后重开。API 前 GUI 保存关闭，API 后 GUI 重开、摘要比对并刷新截图。编辑性在第三份原生临时文件中扰动参数、重算、恢复与重开。

`PairRunner` 在任何干预前冻结公开契约与双路候选，先验证两个 S0 再执行；检查状态、截图和 workbench/camera/selection。每条分支保留 artifact、state diff、checks、成本和轨迹。timeout/5xx 后持久化账本拒绝重放，clone 销毁。NativeBackend 的 FreeCAD/Qt/QEMU 代码目前未在真实环境执行。

自检不导入官方 evaluator。官方采集与 diagnostics 只允许 episode 结束后的独立可信 post-hoc 入口，结果不回流候选、router 或 credit。未知值使用 null 和 reason；目标不可验证时只产生 tie/invalid。训练数据须过滤 synthetic、invalid、unknown 与 tie；test-time G6 仅执行一路。

选样为 part/sketch 公开字段与明确给定前置工程来源，140 题、32 题初筛 edit 候选，实际可配对性等待 native introspection。split 按 family/前置来源并集分组，seed=20261015（完整任务 92/25/23，edit 初筛 19/7/6）；清单与 SHA 见 manifests。G0 原始 GUI-only 与 G1–G7 extended protocol 分开，官方 CLI 的无限定 shell 也单列。

[研究假设] ACTC 是否能减少 held-out route regret 仍待检验。P4/P5 仅保留接口和实验计划，不启动训练或 veRL。不能把 mock 差异、test_easy 小样本、工程 verifier 或局部修复当作论文效果或 novelty。
