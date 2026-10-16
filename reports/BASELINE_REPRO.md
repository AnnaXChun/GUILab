# 基线复现

[上游已存在] 仓库 https://github.com/Zdong104/CADWORLD，固定 commit `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`。本轮没有 benchmark success 结果。

| 协议 | 实际执行 | 任务与结果 |
| --- | --- | --- |
| 官方 GUI-only，原始 instruction | 仅生成确切启动命令 | 计划 `freecad-sketch-061`、`freecad-part-076`；实际 N=0，strict=null，BLOCKED_BY_ENV / BLOCKED_BY_CREDENTIALS |
| 官方 CLI terminal-only | 7 个 upstream 单测通过；原始 `CLI/run_cli.py --dry-run` 依赖导入失败 | 未运行其 6-task smoke manifest；实际模型任务 N=0，strict=null |
| CADWorld-Hybrid (extended protocol) | 9 synthetic mock pairs；无真实 FreeCAD/GUI | 实际 CADWorld 任务 N=0；不计入官方或扩展协议成功率 |

实际命令：

```bash
uv sync --frozen
PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
(cd vendor/CADWORLD && ../../.venv/bin/python CLI/run_cli.py --dry-run)
(cd vendor/CADWORLD && uv sync --frozen --dry-run)
bash scripts/preflight.sh
bash scripts/run_baseline.sh --kind gui-connect --dry-run
bash scripts/run_baseline.sh --kind gui-25 --dry-run
bash scripts/run_baseline.sh --kind cli --dry-run
```

原始 CLI dry-run exit=1，缺少 `dotenv`。完整上游 `uv sync` 没有执行；Mac 无 KVM，安装全部 405 个依赖也不能达到 VM 复现门槛。未用 stub 替代这些上游导入来宣称 CLI dry-run 通过。

GUI 计划命令保留原始 runner，并显式加入 `--no-download_vm`，防止镜像缺失时自动下载。`--max_steps` 记录为 decision-turn 上限，不当作 atomic action 数或等预算证据。25-step smoke 也受默认 12-model-call 安全边界限制；需要另行提高默认调用上限才会开放该实时入口。

新增外部 `upstream_launch` guard：OpenAI max_retries=0、Gemini attempts=1（含首次请求），异常后打开 circuit，记录 usage，限制实际调用与输出 tokens。原始 runner 源码、prompt、parser、evaluator 不变；这项预算适配单独记录。guard 经本地 MockTransport 的 HTTP 500 验证，未发出真实 provider 请求。原始命令保留供人工核对。

CLI-only 无运行时截图；扩展协议中 GUI/API/router 使用同一 effective instruction 和当前工程摘要。两者的 observation budget 不等同。`test_easy` 结果即使日后得到，也不能外推 full-200 或与论文 17.5% 直接比较。

没有 `result.txt` / `evaluation.json` 的官方 episode，本报告的 strict、failure_class 与 stage funnel 为 unavailable，而非 0。预算与环境失败也不计作 Agent 任务错误。

2026-10-16 本机另行执行了无模型的官方 VM 软件模拟检查，详见 [Mac VM 验证](MAC_VM_SMOKE.md)。官方 qcow2 已下载并通过完整 SHA256 校验；默认入口和默认网络的失败均保留，兼容配置未改 upstream tracked 文件。本轮没有启动官方 GUI/CLI 模型 runner，没有 agent 生成的 `.FCStd` 或官方评分结果，因此本表的模型任务 N=0、strict=null 不变。
