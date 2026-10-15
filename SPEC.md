# CADWorld Counterfactual Tool Credit：Codex 可执行技术规格（v1.0）

**日期**：2026-10-15  
**目标**：先复现 CADWorld 官方 GUI 与已有 CLI 基线，再建立同状态、同子目标的 GUI / FreeCAD Typed API 反事实执行实验，为学习 Tool Router 提供可验证的偏好监督。  
**交付边界**：本轮实现 P0–P3，包括代码、测试、少量 smoke 运行与实验报告；**不启动大规模付费推理、完整 200 题评测、模型训练或 RL**。P4–P5 只交付可运行接口与实验方案，等待前置验收。  
**平台**：Ubuntu Linux x86_64 + Docker + QEMU/KVM；Mac 仅做静态开发与纯 Python 单测，不能视为官方 VM 复现。  
**证据类型**：标注为 `[上游已存在]`、`[本项目新增]` 或 `[研究假设]`；不得把预期提升写作实际成绩。

---

## 0. 给 Codex 的总指令

> 你是负责工程复现和研究实验的高级 Research Engineer。**直接按本 SPEC 落地，不要再次进行文献调研或重做选题。**允许读取本文件列出的仓库 README、源码和相关 API 文档，以适配真实代码；不应再搜索新 benchmark 替换 CADWorld。所有上游代码版本固定。优先复用仓库已有 VM、GUI runner、CLI runner、评测器、诊断器；不得重写这些基础设施。
>
> 按 P0→P1→P2→P3 顺序执行，每个阶段生成机器可读证明；阶段未通过则停止下一阶段并报告 blocker。代码和 deterministic tests 尽量跑完；真实模型调用必须遵守 `ENABLE_PAID_RUNS=0` 默认限制，没有 API 凭证时实现 mock/dry-run 并明确 `NOT_RUN`，**不能伪造成功率**。只修改本项目代码；不要污染上游评测规则、参考模型、隐藏答案。若上游实现与 SPEC 有差异，以锁定 commit 的实际代码为准，并在 `docs/DEVIATIONS.md` 记录确切路径、差异、影响和替代实现；不要静默更换研究设计。
>
> 最终交付：仓库、运行脚本、配置文件、单测、至少一个 dry-run trace、若有合法环境则 smoke 结果，以及 `reports/REPRO_STATUS.md`、`reports/PILOT.md`、`reports/FAILURE_CASES.md`。返回确切命令、commit、任务 ID、评测状态及下一阶段是否达到 GO 门槛。

## 1. 研究边界与 Novelty

**研究问题 RQ1**：当 CAD Agent 可同时使用屏幕 GUI 与 FreeCAD 原生 API 时，哪一种操作方式更容易得到**几何正确且保留原生可编辑历史**的最终工程文件？

**研究问题 RQ2**：能否通过*同一工程状态 + 同一语义子目标 + 配对隔离执行*，估计 GUI 与 API 的工具选择反事实收益，得到比规则或普通轨迹奖励更可靠的路由监督？

**研究问题 RQ3（后续）**：离线配对 credit 训练的 Router 能否在推理时仅执行单一路径，在等预算下提升独立留出任务的 strict success / editability / cost？

**预期方法贡献（待实验证明）**：`Artifact-grounded Counterfactual Tool Credit (ACTC)`——对同一个子目标，复制相同工程状态，分别实施 GUI 和 typed FreeCAD API 候选，再以不依赖隐藏答案的工程自检衡量状态增益、未修改区域保持、参数化完整性和执行代价；将差值作为偏好/credit 监督。**GUI+API 混合、常规 verifier、局部修复本身都不是本论文 novelty**。

**关键区别**：ToolCUA 研究通用 GUI–Tool 路径学习；本项目研究 CAD 工程状态下的**同状态干预型 credit label**。仅报告末端 success 仍不足以论证此区别，必须测量 credit 质量/route regret，并与 Best-of-2、成本匹配的普通验证对比。

## 2. 已核实的资源（Codex 无需重搜）

### 2.1 主仓库及代码入口

| 类型 | 地址 / 路径 | 用途与注意事项 |
|---|---|---|
| **核心仓库** | https://github.com/Zdong104/CADWORLD | [上游已存在] CADWorld 200 题 FreeCAD GUI benchmark。固定 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`（2026-10-15 查询到的 `main` HEAD）；必须在启动时核对该 SHA，若不可获取则阻断并记录 |
| 论文 | https://arxiv.org/abs/2609.16251 | 200 任务、11 工作流；强模型原论文 strict success 为 17.5%，但**仅原 GUI-only 协议**，不是本项目目标或复现承诺 |
| 数据资产 | https://huggingface.co/datasets/Zihan1004/CADWORLD | 200 条任务及附件；**原仓库 `evaluation_examples/` 为运行时优先来源** |
| VM 镜像 | https://huggingface.co/Zihan1004/CADWorld | `vm_data/FreeCAD-Ubuntu.qcow2`，使用仓库 `scripts/python/download_vm_image.py` 获取；约 35GB 空间需求 |
| GUI runner | `scripts/python/run_cadworld.py` | 参数、模型 provider、自定义 agent、VM、结果目录 |
| GUI agent | `scripts/python/api_agent.py` | 截图→模型→合法 `pyautogui` action；参考 `docs/MODEL_OUTPUT_CONTRACT.md` |
| GUI rollout | `scripts/python/benchmark/run_single.py` | `run_single_example`、保存 `.FCStd`、评测与诊断；`--max_steps` 是决策循环，**不一定等于原子 GUI action 数** |
| VM / controller | `desktop_env/desktop_env.py`, `desktop_env/controllers/` | `DesktopEnv.reset/step/evaluate`；禁止以 evaluator 信息作为 Agent observation |
| 官方 CLI 实验 | `CLI/README.md`, `CLI/run_cli.py`, `CLI/terminal_agent.py` | [上游已存在] terminal-only 基线，不要从零写。`CLI/run_cli.py` 使用 `/execute` 一次性端点（避免 `/run_bash_script` 重试非幂等操作） |
| CLI 安全策略 | `CLI/audit_terminal_boundary.py`, `CLI/prompts.py` | 可借鉴边界检查及精确去掉 `Use GUI,` 前缀的 instruction normalization |
| 自动诊断 | `desktop_env/evaluators/diagnostics.py`, `docs/STAGED_DIAGNOSTICS.md` | [上游已存在] 完成、保存、文档有效性、结构、几何、process、strict 等阶段；`evaluation.json` 只能**离线评价**，不得暴露为执行时 oracle |
| 任务列表 | `evaluation_examples/test_easy.json`, `test_small.json`, `test_60.json`, `test_all.json` | 当前检查到 `test_easy` 10 题、`test_small` 50 题、`test_60` 60 题、`test_all` 全量；列表存在重叠，不能直接当相互独立的训练/测试分割 |
| CLI smoke | `CLI/tasks_smoke.json` | 6 题：sketch-061、part-076、measure-002/003、cloudpoint-003、appearance-003 |

**仓库代码确认**：`CLI/run_cli.py` 中已有 `TerminalDesktopEnv`、`execute_terminal`、`_save_generated_fcstd`、`_write_diagnostics_report`；`CLI/terminal_agent.py` 内已有 `TerminalModelAgent` 和终端工具定义。混合工具工程只增加 orchestration，不替换它们。

### 2.2 Related work：定位、代码、不可冒领的创新

| 研究（建议引用名） | 论文 / 代码 | 与本项目的关系；Code 状态 |
|---|---|---|
| **CADWorld** (Dong et al., 2026) | Paper: https://arxiv.org/abs/2609.16251 · Code: https://github.com/Zdong104/CADWORLD | 主测试环境与原生 artifact 严格评测；**代码/数据/VM 公开**。原论文主协议为 GUI-only，单独有 CLI 消融 |
| **ToolCUA** (Hu et al., 2026) | Paper: https://arxiv.org/abs/2605.12481 · Code: https://github.com/X-PLUG/ToolCUA · Model: https://huggingface.co/mPLUG/ToolCUA-8B | 已研究 GUI–Tool 路由、GUI-Tool trajectory 与 RFT/RL；**模型/评测代码公开，但 README 标记训练基础设施和数据流水线 TODO**，不能假定训练代码完整 |
| **MCPWorld** (Yan et al., 2025) | Paper: https://arxiv.org/abs/2506.07672 · Code: https://github.com/SAAgent/MCPWorld | GUI / API / Hybrid benchmark 已做，说明“支持混合操作”不是新颖性；此仓库仅作设计参考，**不是主复现工程** |
| **TraceCAD** (Fan et al., 2026) | Paper: https://arxiv.org/abs/2608.03062 | 已研究 trace-guided 错误诊断、依赖区域局部修复、保持已满足约束；**本次未核实官方代码仓库**，不写假的 repo 地址，也不将局部修复包装为新贡献 |
| **SPADA** (Zheng et al., ICML 2026) | Paper: https://proceedings.mlr.press/v306/zheng26q.html | 测试驱动 parametric assembly 生成和 compile–test–repair；**本次未核实官方代码地址**。一般 CAD 测试循环不是新颖性 |
| **CADTestBench / CADTests** (Mallis et al., 2026) | Paper: https://arxiv.org/abs/2605.07807 · Code: https://github.com/dimitrismallis/CADTestBench | 可执行几何/拓扑条件优于纯外观反馈；**代码公开**。借鉴通用自检思想，但不能把 benchmark 的期望结果泄给 agent |
| **BlenderGym** (Gu et al., CVPR 2025) | Paper: https://arxiv.org/abs/2504.01786 · Code: https://github.com/richard-guyunqi/BlenderGym-Open | Blender 图形编辑/代码重建验证；**代码公开**，跨软件实验可选 |
| **3DCodeBench** (Gao et al., 2026) | Paper: https://arxiv.org/abs/2606.01057 · Code: https://github.com/gaoypeng/3dcodebench · Data: https://huggingface.co/datasets/YipengGao/3DCode | Blender 5.0 Python 程序化 3D 基准，212 类，支持 coding-agent 与失败反馈；**代码/数据/日志公开**。不是原生 GUI/CLI 路由基准，只能作第二阶段迁移 |
| **FreeCAD Hybrid MCP** | Code: https://github.com/tamerkarakan/Freecad_MCP | typed FreeCAD tools 与 persistent sessions 的工程参考；**代码公开**。其部分配置针对 Windows；不要直接拿 Windows 路径接入 Linux VM |
| **Parametric CAD Bench V3** | Website: https://cadbench.ai/ · Harbor: https://hub.harborframework.com/datasets/gnucleus-ai/cad-bench/v3 · Validator: https://github.com/gNucleus-AI/freecad-validator | 100 题 parametric benchmark，create/edit 更相关；V3 **连续奖励**不等于严格通过率，且 FreeCAD 运行与计分协议不同；可做后续外部验证而非首阶段 |

**相关工作的论文 positioning（供后续写作，不要求 Codex 重新搜索）**：

- `ToolCUA`: learns when to select GUI/tool; **ours** studies *CAD artifact-grounded paired intervention* to supervise the selection, instead of only ordinary task/path-level return.
- `TraceCAD` / `SPADA` / `CADTests`: repair/testing verifies *a proposed CAD result*; **ours** estimates *relative action modality utility for the same state and intent*. Repairs and tests are components, not claims.
- `CADWorld`: contributes the benchmark and saved-project evaluator; **ours** changes the *agent interface / learning method*. All hybrid results must be labeled `CADWorld-Hybrid (extended protocol)`.

### 2.3 版本固定策略

```bash
# 在 Linux 主机的项目根目录执行。原始仓库仅作 vendored benchmark，不在 main 上开发。
mkdir -p vendor
if [ ! -d vendor/CADWORLD/.git ]; then
  git clone https://github.com/Zdong104/CADWORLD.git vendor/CADWORLD
fi
git -C vendor/CADWORLD fetch origin e5d0ebab8bd28da6e98c68c61db05747d1647f7b
git -C vendor/CADWORLD checkout --detach e5d0ebab8bd28da6e98c68c61db05747d1647f7b
test "$(git -C vendor/CADWORLD rev-parse HEAD)" = \
  "e5d0ebab8bd28da6e98c68c61db05747d1647f7b"
cd vendor/CADWORLD
uv sync                        # 仓库 .python-version 当前使用 Python 3.12
uv run python -m unittest CLI.test_terminal_agent
uv run python CLI/run_cli.py --dry-run
```

若上游 commit 不可获取：记录 `git ls-remote`/错误并停止，**不得悄悄换到最新 main**。配置中保存 `cadworld_commit`、VM 文件 SHA256、FreeCAD 版本、Python/uv 版本和 model identifier。VM 可能很大，只读 hash，不复制镜像进实验结果。

## 3. P0：环境与官方复现（必须先通过）

### 3.1 Linux 预检及安装

```bash
uname -s && uname -m                 # Linux / x86_64
ls -l /dev/kvm                       # 必须存在且当前用户可访问
docker info >/dev/null               # Docker 访问必须通过
qemu-system-x86_64 --version
uv --version
df -h .                             # 建议至少 100GB 可用以容纳 VM + 工作盘 + trace

# 缺少系统包时（Ubuntu）
sudo apt update
sudo apt install -y docker.io qemu-system-x86 qemu-utils
sudo usermod -aG docker "$USER"
sudo usermod -aG kvm "$USER"
sudo systemctl enable --now docker
# 刷新组权限需要重新登录。按照上游 README 检查网络内核模块。
```

`uv` 的安装按 https://docs.astral.sh/uv/getting-started/installation/ 完成。不要在本机 macOS 试图伪装 KVM。README 建议的 VM 资源是 8 CPU、8GB RAM、64GB 虚拟磁盘；宿主内存与磁盘需要额外余量。

### 3.2 下载并检查 VM（显式操作，不能后台静默下载）

```bash
cd vendor/CADWORLD
uv run python scripts/python/download_vm_image.py
ls -lh vm_data/FreeCAD-Ubuntu.qcow2
sha256sum vm_data/FreeCAD-Ubuntu.qcow2
```

记录哈希，不在文档里假造预期 SHA。**Full CAM 任务**需要宿主 FreeCAD 1.1.x `FreeCADCmd`（官方 README 给出 1.1.3 AppImage 安装方法），P0 smoke 可先跳过 CAM；若后续测试 CAM，没有宿主 FreeCAD 的评分应标记 `UNAVAILABLE`，不能当 Agent 错误统计。

### 3.3 官方 GUI smoke：先 `3 steps` 测连接，再 `25 steps` 测可执行

```bash
cd vendor/CADWORLD
cp -n .env.example .env   # 人工设置服务方 API KEY；不在日志中打印

# 先由 scripts/preflight.sh 生成只含 2 题的 manifests/smoke_2.json；
# 格式与 test_easy.json 相同，例如 {"sketch":["freecad-sketch-061"],"part":["freecad-part-076"]}。
# 官方 README 的 Gemini provider 示例；若凭证不可用，则改用实际可用 provider，并记录变更。
# 仅当 ENABLE_PAID_RUNS=1 时执行此命令，默认不得调用付费 API。
uv run python scripts/python/run_cadworld.py \
  --test_all_meta_path ../../manifests/smoke_2.json \
  --agent api --api_provider gemini \
  --model_name gemini-3-flash-preview \
  --max_steps 3 --run_id gui_connect_smoke --no-skip_finished

# 仅当连接通过且 ENABLE_PAID_RUNS=1 时才做下面的长一些的 2-task smoke：
uv run python scripts/python/run_cadworld.py \
  --test_all_meta_path ../../manifests/smoke_2.json \
  --agent api --api_provider gemini \
  --model_name gemini-3-flash-preview \
  --max_steps 25 --run_id gui_25steps --no-skip_finished
```

`--max_steps` 是**代理回合/循环上限**，动作列表可能含多条原子 GUI 命令；日志与分析中分别记录 `decision_turns`、`gui_atomic_actions`、`model_calls`、`tokens`、`wall_seconds`。单靠 `max_steps` 不能声称 GUI 与 CLI 等预算。

**GUI smoke 最低验收**：至少 1 题成功完成 `env.reset → action → evaluation → artifact collection` 流程（不要求任务通过），其文件夹包含 `traj.jsonl`、`result.txt`、`evaluation.json`、截图/运行日志，且正确区分 `score=0` 和 `run_error`。无模型凭证时允许 mock 的 executor / parser 单测，必须标为 `NOT_RUN_NO_CREDENTIALS`。

### 3.4 官方 CLI smoke：不要重新实现已有 CLI

```bash
cd vendor/CADWORLD
uv run python -m unittest CLI.test_terminal_agent
uv run python CLI/run_cli.py --dry-run

# 仅在相应本地 OpenAI-compatible server 可连通且运行已授权时：
uv run python CLI/run_cli.py \
  --task-id freecad-sketch-061 \
  --run-id cli_sketch_smoke \
  --model '<actual-served-model-id>' \
  --base-url 'http://127.0.0.1:8001/v1' \
  --max-turns 8 --max-terminal-calls 8 \
  --max-wall-seconds 600 --total-output-tokens 12000
```

上游 CLI 默认假设本地 Qwen3.6 server，**不负责自动启动模型服务**。测试是否 available 后再运行。官方 CLI 特别使用 VM 内的 `/execute` API 避免非幂等脚本重复执行；新实现要沿用该机制或证明替代方法恰好执行一次。

**P0 结果**：`reports/BASELINE_REPRO.md` 明确官方命令、环境、模型、每题 `strict`、任务产物路径、推理失败原因；不可把 `test_easy` 成功率称为 200 题公开结果的复现。

## 4. P1：最小 Hybrid Execution Harness（本项目新增）

### 4.1 目录契约

```text
cad-cf-hybrid/
├── SPEC.md                         # 本文
├── README.md
├── scripts/
│   ├── preflight.sh
│   ├── bootstrap.sh
│   ├── run_smoke.sh
│   ├── run_pilot.sh
│   └── summarize.py
├── vendor/CADWORLD/                # pinned, upstream-only，禁止对评测器打补丁
├── configs/
│   ├── smoke.yaml
│   ├── pilot.yaml
│   ├── model.example.yaml
│   └── experiment_matrix.yaml
├── cad_cf/
│   ├── cadworld_adapter.py         # reset / observe / GUI action / evaluate glue
│   ├── instruction.py              # 仅替换合法接口前缀，保留任务语义
│   ├── tool_protocol.py            # TypedAction / Intent / Observation schema
│   ├── typed_freecad.py            # FreeCAD API tool executor
│   ├── terminal_bridge.py          # 复用一次性 /execute；限时/限路由/只在 VM 内执行
│   ├── snapshot.py                 # same-state capture, restore, prove equivalence
│   ├── artifact_state.py           # 工程状态 canonical summary / digest
│   ├── candidate_generator.py      # same intent 的 GUI/API proposals
│   ├── counterfactual.py           # paired branch runner
│   ├── self_verifier.py            # 在线可用通用自检；绝不读取隐藏 evaluator
│   ├── router.py                   # gui_only/api_only/rule/llm/cf_preference
│   ├── metrics.py
│   └── trace.py
├── tests/
│   ├── test_instruction.py
│   ├── test_protocol.py
│   ├── test_snapshot_restore.py
│   ├── test_artifact_state.py
│   ├── test_verifier.py
│   ├── test_no_evaluator_leakage.py
│   ├── test_non_idempotent_execution.py
│   └── test_deterministic_mock_pair.py
├── manifests/                      # splits & allowed public task fields
├── reports/
│   ├── REPRO_STATUS.md
│   ├── PILOT.md
│   ├── FAILURE_CASES.md
│   └── DEVIATIONS.md
└── results/                        # .gitignore，保留 schema 示例
```

若现有工作区已有目录，请在其下创建 `cad-cf-hybrid/`；不要破坏正在进行的 ORSD、veRL 项目。支持 Git 常规 clone 或 submodule，但固定上游 commit 必须可审计。

### 4.2 混合协议：统一接入、保留官方基线

**官方成绩仍按原 GUI-only 跑**。扩展协议中，任务字段 `instruction` 常常以 `Use GUI, ` 开头。如果把这种指令原样交给 Hybrid Agent，API 路径会与任务约束冲突。

- 引入 `instruction_raw`（不改动）与 `instruction_effective`（只去掉精确接口短语，然后加一条“可用 GUI 或 approved FreeCAD API”的固定系统提示）。参考 `CLI/prompts.py:normalize_instruction()`，不得修改尺寸、对象、文件路径、任务要求。
- **在 Hybrid protocol 下**比较所有 baseline：GUI-only、typed-API-only、naive hybrid、rule router、LLM router、Ours；它们得到相同 `instruction_effective`。官方 GUI-only 原始指令成绩另列，**两套协议不可混成一张排行榜**。
- Agent 允许看到：原始自然语言、合法任务提供的参考图片、GUI 截图、以及只针对当前 `.FCStd` 的对象/参数状态摘要。`cadworld_adapter.py` 必须以字段白名单创建 `agent_view`；不能把原始 `task_config` dict 传给模型或候选生成器。Agent 不允许看到：`evaluation_examples/examples/*` 中 evaluator/expected/reference 字段、参考答案 `.FCStd`、隐藏得分、`evaluation.json`、宿主机文件及其他测试样本。
- **CLI-only 原仓库**允许运行沙箱 Bash，是既有对照；**本实验 typed-API-only**只暴露控制在白名单内的 FreeCAD API，不与 unrestricted-shell 等同。

### 4.3 Typed Tool Schema：先做 6–8 个稳定工具

最小可用工具：`inspect_document`、`inspect_sketch`、`set_sketch_constraint`、`set_object_property`、`recompute`、`save_as`、`verify_document`；若某子目标需要，再增加 `create_sketch` / `create_pad`。禁止默认暴露任意 `python -c` / shell 命令供 agent 调用。`FreeCAD Hybrid MCP` 可作为设计参考，但不要直接安装到官方 VM 里替代原 evaluator。

每个工具返回 JSON：

```json
{
  "tool": "set_object_property",
  "args": {"object_name": "Pad", "property": "Length", "value": 12.0},
  "precondition": {"document": "/home/user/Precondition_Unnamed.FCStd"},
  "result": {"ok": true, "changed_objects": ["Pad"], "recompute_ok": true},
  "trace": {"duration_ms": 123, "stdout_bytes": 512, "stderr_bytes": 0}
}
```

示意 schema 不能假定所有 fixture 都有 `Pad` 或叫同一个 Name。运行时**通过 FreeCAD 对象 introspection 验证对象/属性存在且类型匹配**。工具输入使用稳定的 object `Name` 与 `TypeId`，不能仅根据截图猜坐标后直接改 XML。保存 `.FCStd` 前运行 recompute 并检查可打开。GUI/API 工具只能在 VM 内作用于**当前任务**文件。

### 4.4 状态同步是硬性工程要求

- GUI 与独立 `FreeCADCmd` 不能无协调地同时写同一个 `.FCStd`：GUI 内存文档可能仍保留旧值。对 creation 任务若未给 precondition，先为每个分支准备具有相同初始工作台/空文档状态的干净 checkpoint。采用**每次工具执行提交工程文件、关闭或重新加载文档、刷新截图**的显式 commit boundary。
- 对任一配对实验，建立 `S0`：当前 native artifact 副本 + 对象树 canonical JSON + agent-visible screenshot + public intent。构建 `GUI`、`API` 两个完全隔离的 VM/工作目录分支。不能只在原 VM 串行执行 A 再撤销后执行 B，并声称 same-state。
- 初期较简单且可靠的办法：`env.reset(task)` 后复现同一合法前缀、保存检查点，再各自从相同快照/overlay 恢复；也可使用两个相同基线 VM 的 clone。**配对前必须比较可重计算的对象树 digest 和目标对象属性，并记录 source checkpoint hash**。如无可靠 restore 机制，则配对结果 `invalid_pair`，不可用于训练。
- 生成的 `.FCStd` 归一化后 hash（按对象 Name、TypeId、重要属性、参数约束及有效形体签名），**不能用 zip 文件字节 hash 作为几何状态相等的唯一证据**；ZIP 时间戳和元数据可能变化。
- 所有命令必须 timeout，必要时杀死进程/恢复隔离副本，避免一个坏脚本污染下一 task。参考上游 `CLI/run_cli.py` 的单次 `/execute` 机制。

## 5. P2：反事实 pair & 工程自检（最核心代码）

### 5.1 一个 pair 的明确构造

1. 从 Agent 可见的 `instruction_effective + screenshot + object summary` 提出**一个语义子目标**，如“将 Sketch 的 Radius 由 5mm 改为 7mm，保持其他草图与 body 不变”。
2. 为同一 `intent_id` 产生两个候选：GUI 是若干 `pyautogui` actions；API 是 typed FreeCAD call 序列。两个候选目标和成功判据必须一致；若不具备双路径实现能力，标记 `unpaired`，不得强行记胜负。
3. 保存 `S0`，分别恢复到 `S0` 的 clone A/B。执行业务操作，并收集终态文件 `A.FCStd`、`B.FCStd`；两条路径都要 recompute、save、reopen、verify。
4. 对 A/B 用**同一份、在执行前冻结的、从 public instruction 推导出的独立自检契约**评估，而不是以官方 evaluator 判定在线 winner。
5. 输出 `pair.json`、工具轨迹、输出文件、state diff、`verifier_checks.json`、有效性判定与成本，供规则 Router / 训练数据复用。

**首批可运行任务**：`freecad-sketch-061`（水平线 10mm）、`freecad-sketch-062`（圆 R=10mm）、`freecad-part-076`（圆柱）、`freecad-part-077`（三棱柱）来自 `test_easy`，可以先测创建模式双路径。注意四题的 `requires_precondition=false`，不适合验证“编辑时保留旧工程”主论点。**编辑主实验必须另选有 precondition 的 part/sketch 任务**，并由脚本自动核验 `requires_precondition==true`、具备可稳定测量的目标属性；不得将创建任务冒充 edit task。

### 5.2 数据结构契约

```json
{
  "pair_id": "<uuid>",
  "task_id": "freecad-...",
  "task_split": "train|val|test",
  "intent": {"id": "edit_sketch_radius", "object": "Sketch", "target": {"radius_mm": 7.0}},
  "s0": {"checkpoint_sha256": "...", "canonical_state_digest": "..."},
  "branches": {
    "gui": {"state_before": "...", "state_after": "...", "artifact_path": "...", "action_count": 5, "tokens": 1200, "wall_s": 31.2, "checks": {"...": null}},
    "api": {"state_before": "...", "state_after": "...", "artifact_path": "...", "action_count": 2, "tokens": 800, "wall_s": 8.2, "checks": {"...": null}}
  },
  "pair_valid": true,
  "label": "api|gui|tie|invalid",
  "credit_delta": 0.15,
  "label_source": "public_contract_only",
  "leakage_audit_passed": true
}
```

`checks` 的 unavailable/unknown 必须用 `null` + `reason`，不得无依据当 0 或 1；上例里的 token/time/credit 值仅为 **schema 示例**，不是实验结果。每个 pair 都记录工具版本、模型调用上下文/参数与 seed。

### 5.3 在线可用的 Verifier（不接触 official expected rules）

分层实现 `V(s, intent)`，每个分量附 `applicable`、`confidence`、`evidence`：

- `validity`: 输出文件存在、zip/XML 可解析、FreeCAD 重开/重算成功、形体有效。
- `target_progress`: 指令里**显式**的尺寸、数量、约束在新状态是否满足。例如 radius/mm、Pad Length、约束数量等；任务表达不清则 `unknown`。
- `preservation`: 从 S0 推断非目标及非依赖对象应保留，比较稳定 Name/TypeId、约束、尺寸和 B-Rep 摘要；因父子 feature 变更导致合法拓扑变化时，不要用全对象 hash 一票否决。
- `editability`: 检查是否仍保留原生 PartDesign / Sketcher 结构、可访问参数，必要时在隔离 clone **轻微扰动目标参数并 recompute，再恢复**，验证结构仍可编辑。
- `cost`: model calls/tokens、GUI atomic actions、API calls、wall time 与失败恢复次数。

初始固定：`quality = 0.25*validity + 0.35*target_progress + 0.20*preservation + 0.20*editability`，`utility = quality - 0.05*normalized_cost`，`ε=0.05`（utility 归一化到约 0–1；normalized_cost 是当前预算上限内的截断成本比例）；写进 `configs/pilot.yaml`。对于**不适用**的项用适用权重重归一化，但**缺少可验证 target_progress 时不得给有方向的 GUI/API preference**，只能 `tie/invalid`，防止单凭低成本制造监督。权重、`λ` 和 epsilon 只允许在验证集上调参并冻结，不能根据 test 结果修改。对每个 pair，`Δ = V(s_after_API,intent) - V(s_after_GUI,intent)`；阈值 `ε` 外给 GUI/API preference，阈值内 tie。报告 label coverage 与 uncertainty。

**严禁**：生成时读取 `evaluation_examples/examples/<domain>/<id>.json` 中的 `evaluator.expected`、参考 fixture / golden solution、`desktop_env/evaluators` 的 task-specific expected rule 或原始 `evaluation.json` 作为 reward/选择信号。官方评测器可由单独 post-hoc 进程在 episode 结束后评分，只供论文统计。

### 5.4 保证反事实有效性的单测

- `test_same_intent`: GUI/API proposals 引用同一个规范化 intent；不同目标的 pair 必须 reject。
- `test_restore_equivalence`: A/B 前的 native document canonical digest 严格一致；不一致 abort。
- `test_no_double_mutation`: 模拟 `/execute` 超时/5xx，非幂等 API edit 不得无 idempotency key 自动重试。
- `test_ui_refresh`: API 提交后 GUI 重新打开文件并获取新的截图；不能看到旧文档。
- `test_clean_clone`: 改 A 的文件不会改 B 初态，B 完成也不会污染原任务。
- `test_leakage`: mock agent 尝试访问 `evaluation`, `reference_solution_path`, host eval metrics -> policy deny；验证 `agent_view` JSON 中绝无这些键。
- `test_verifier_unknown`: 无明确目标属性或没有可检验项，不输出有方向性的 preference。
- `test_paired_mock`: 不调用模型 API，执行固定 GUI/API stub 和 dummy artifact，得到可复现 JSON trace。

## 6. P3：最小实证计划和基线矩阵

### 6.1 Pilot 样本选择与分割

- `smoke`：2–4 个 `test_easy` creation 任务，只做功能检查，**不估计论文成功率**。
- `pilot`：从 `test_all.json` 中仅筛 `part` / `sketch` 且 `requires_precondition=true` 的 edit-oriented 任务，优先可从自然语言明确出目标参数的任务；加入创建任务只是作为辅助 sanity group。
- 目标收集 **至少 24 个 valid pairs**（不是选 24 题后默认全有效）；每个 pair 的 provenance、重复题型与 invalid 理由必须保存。若无法在 24 个 pair 内取得异号 preference，要诚实说明“路由区分能力不足”，不可后选漂亮样本。
- 训练/验证/测试：按**规范化 task family / 来源工程文件**分组、按领域分层进行 60/20/20 划分（固定 seed=20261015），并写出清单与 SHA。候选创建与 Router 训练只用 train；阈值与参数只用 val；test 完全隔离。不能把官方 `test_small` 与 `test_60` 当独立 split，因为存在重叠。
- 如果 pilot 的任务数量太少，报告置信区间与 `N`，不能将该小样本外推到 200 题。若训练使用了 CADWorld 任务，则只能在其独立 held-out 部分报告方法增益；**不得与原论文 full-200 17.5% 直接进行数值胜负比较**。

### 6.2 实验组（先实现接口，再开预算）

| 名称 | 决策策略 | 衡量的问题 |
|---|---|---|
| `G0_OFFICIAL_GUI` | 原仓库截图→pyautogui，原 prompt | 文献协议复现；单独报告 |
| `G1_GUI_EXT` | Hybrid-neutral prompt，强制 GUI | 同协议公平 GUI 对照 |
| `G2_TYPED_API` | Hybrid-neutral prompt，强制 typed API | API 控制的几何/历史能力 |
| `G3_NAIVE_HYBRID` | 给 Agent 两类工具，让基础模型直接选 | 简单集成的增益 |
| `G4_RULE_ROUTER` | 固定规则：可明确修改数值属性优先 API；依赖视觉定位优先 GUI；失败回退 | 工程规则基线 |
| `G5_CONVENTIONAL_VERIFY` | 常规执行后自检 + 最多一次重试，**成本匹配** | 排除 verifier 或额外尝试的贡献 |
| `G6_CF_ROUTER` | 用离线 pair preference 训练工具选择，运行时单路径执行 | ACTC 的独立贡献（P4 才做完整训练） |
| `G7_BEST_OF_2` | 两路都执行，self-verifier 选最佳，并计入双倍预算 | 离线 oracle-like 上界，不是公平在线对照 |

分组 `G0` 不应和 `G1–G7` 的 hybrid extended protocol 混算。**G6 不允许在 test 时再执行另一分支来挑选**，否则不是低成本 route policy。`G7` 应标为额外计算上界。

### 6.3 必须报告的指标

**主指标（独立评测、后处理）**：`Strict Success`（CADWorld 原评测器，binary）+ `valid_saved_artifact_rate`。  
**结构指标**：`native_feature_tree_validity`、`unmodified_component_preservation`、`parametric_editability_probe_pass_rate`；报告适用覆盖率。  
**反事实指标**：`pair_valid_rate`、`label_coverage`、`route_preference_accuracy`（仅有置信标签的 held-out pairs）、`route_regret`（相对于 pair 中 utility 较大者）、`gui_preferred_ratio` / `api_preferred_ratio` / `tie_ratio`。  
**效率**：调用次数、完成 tokens、wall time、GUI atomic actions、typed API calls、验证与离线 counterfactual 数据生成成本。  
**诊断**：复用 `evaluation.json` 中 `failure_class`，报告 stage funnel；**只能事后分析**。  
**统计**：按 task paired bootstrap 95% CI；比较 success 用同任务配对差与 McNemar（N 足够时）；按 `part` / `sketch` 及 creation/edit 分层。所有结果附分母 N，不得只报告成功案例。

### 6.4 工程预算（默认保守）

`ENABLE_PAID_RUNS=0`；`MAX_LIVE_TASKS=2`；`MAX_PAIRS=3`；`MAX_MODEL_CALLS_PER_TASK=12`；`MAX_WALL_SECONDS_PER_TASK=600`；`MAX_RETRIES=0`；API 失败不偷偷重试。Pilot 24 pairs **只在有明确许可、可统计预算和健康监控后启动**，先测试 3 pairs 的合法恢复与内容质量。默认先构造 mock pairs，不花 API 费用。运行前展示预计任务数量、模型、预算上限，不允许无限自旋。

## 7. P4 / P5：后续研究，不作为本次阻塞项

**P4：Preference Router**。输入 `instruction_effective + canonical object summary + screenshot embedding + candidate intent`，输出 `P(GUI),P(API)`；使用 train 的有效 non-tie pair 做 pairwise preference 或二分类训练，val 调 confidence threshold，test 只执行一路。先用小 router 或 LoRA/SFT，不需要启动 veRL；对比：同 backbone 的直接 LLM routing、规则、随机、无 editability 信号、无 preservation 信号、仅终局 reward。

**P5：RL（条件启用）**。若 P3 证明反事实标签预测 route utility 优于规则且 strict success 有潜力，才将单步 route credit 送入 veRL 的 step-level reward（不是每个 GUI token 直接套 GRPO），规定 off-policy 反事实 label 与 on-policy task reward 的权重以及成本。先跑 frozen backbone + router，避免因修改 GUI 操作模型导致归因混乱。**论文先证明 credit 有效，再证明 RL 能放大改进**。

**重要消融**：`ours` vs `no-counterfactual`、`no-preservation`、`no-editability`、`equal-cost conventional verifier`、`random routing`、`API-only`，额外做 `different S0` 的伪配对负控制，证明配对初态等价是必要条件。

## 8. 验收门槛（Stop/Go）

| 阶段 | 硬验收要求 | 未通过怎么办 |
|---|---|---|
| P0 | upstream 固定 SHA；`uv sync`；CLI unittest + dry-run；Linux VM 可用时 GUI smoke 有轨迹、结果与诊断 | 停止开发 GUI/API fork；记录环境 blocker |
| P1 | 模型无关 mock 与协议测试通过；官方 GUI runner 不变；typed API 可修改并正确保存/重开一个原生文件 | 先修同步/保存，不做 pair |
| P2 | 相同 S0 可恢复两次；两个分支相互隔离；产生可审计的 `pair.json`；不泄漏评分规则；无非幂等自动重试 | `invalid_pair` 不入训练；修复隔离后再继续 |
| P3 | ≥3 个合法 smoke pairs；尝试 24 pairs 并完整报告成功/失败/invalid；至少有具有辨别性的非 tie pair 且差异可重测 | 无工具差异或规则基线等效：**暂不做 RL**，重新评估研究方向 |
| P4（后续） | held-out route regret 优于 rule / LLM router，等预算 strict success 不下降，编辑结构无退化 | 若没有统计支持，停止论文大实验 |

**绝对禁止**：以 reference `.FCStd` / fixture 文件冒充模型生成；使用 `fixture_freecad` 模式计入模型 success；在 agent prompt 中放 expected rules；读 `evaluation.json` 当在线 reward；修改 evaluation 逻辑来提高成绩；删除失败样本；隐瞒 API 成本；以 `test_easy` 成绩等同 full benchmark；无记录改 benchmark 版本；Mac 无 KVM 时编造 VM 测试；只按成功 case 生成报告。

## 9. 交付物 schema / 终端报告要求

必须产出：

```text
reports/REPRO_STATUS.md        # 完整环境、sha、已运行/未运行、命令及日志路径、error taxonomy
reports/BASELINE_REPRO.md      # GUI / official CLI 基线分开
reports/PILOT.md               # 任务选择、有效/无效 pair 数、方法与数据摘要、N/CI
reports/FAILURE_CASES.md       # ≥5 个有代表性的失败或 invalid pair（不足则全部列出）
reports/DEVIATIONS.md          # 上游接口变动、方案偏离及原因
manifests/splits.json          # 可重建的 train/val/test
manifests/selection_audit.csv  # 每题能否配对与选取原因（不使用隐藏规则）
results/<run_id>/manifest.json # model/provider、token/step/wall budgets、git SHA、VM SHA
results/<run_id>/<task_id>/{trajectory.jsonl, artifact.FCStd, evaluation.json, pair.json*}
configs/{smoke,pilot,experiment_matrix}.yaml
```

报告 `reports/REPRO_STATUS.md` 至少要包含 6 个状态：`PASS`、`FAIL`、`BLOCKED_BY_ENV`、`BLOCKED_BY_CREDENTIALS`、`NOT_RUN_BUDGET`、`NOT_IMPLEMENTED`。未运行不能写作 PASS。检查仓库中 `.env`、token、证书和秘密未泄漏。所有命令以 `scripts/*.sh` 包装并支持 `--help`、`--dry-run` 和失败非零退出码。

**最终只需向研究者回答**：本次实际跑过的任务与结果、哪些代码模块完成、准确的运行命令、是否有 >0 的有效 GUI/API 差异、后续 P4 是否有依据、具体 blocker。不要以一篇新的泛泛调研代替代码与实验。

---

## Appendix A. 已确认的轻量命令

```bash
# 不启动 VM、不访问外部模型：CLI 单测与任务协议预检
cd vendor/CADWORLD
uv sync
uv run python -m unittest CLI.test_terminal_agent
uv run python CLI/run_cli.py --dry-run

# 本项目：在实现后执行下列标准命令（脚本由 Codex 新增）
cd ../..
bash scripts/preflight.sh
bash scripts/run_smoke.sh --dry-run
pytest -q tests
python -m cad_cf.counterfactual --config configs/smoke.yaml --dry-run
python scripts/summarize.py --input results/<run_id> --output reports/PILOT.md
```

## Appendix B. 注意事项（研究有效性）

1. CADWorld 论文成功率评测是 *all-or-nothing*；工程价值不能仅由截图相似性代替，且不同软件 benchmark 不可直接平均。
2. `test_small`、`test_60`、`test_easy` 有 ID 交叉；split 用 task family group + 显式 manifest，不以文件名理解为“验证集/测试集”。
3. `CLI/README.md` 的 terminal-only 不给运行时桌面截图；Hybrid 有截图，所以不能拿 CLI-only 的 observation budget 当成完全同等设置。展示 interfaces 可见信息差异。
4. 反事实 probe 的额外两路计算属于**训练数据/诊断成本**，不能在最终在线推理成本里遗漏，也不能把它算作免费 oracle。
5. 设计应能迁移到 Blender 的 `bpy`，但 v1 不引入 Blender 二次安装与额外评测工程，避免掩盖最重要的 FreeCAD 约束实验。
6. 本 SPEC 是**实现计划**；仓库路径已在线核对，未在本次环境真实启动 KVM/VM、未产生任何 benchmark success 结果。Codex 需如实填充可复现报告。

