# 远程 Codex 交接

交接日期：2026-10-16。代码来源：本项目 main，历史已保留；本文件与移植检查随本次交接提交。规格的证据类型、实验边界与 Stop/Go 继续有效。

## 下一步执行指令已更新

用户后续明确要求由远程 Codex 索取 base URL、API key、model ID 并真正跑少量 baseline。先读 [下一批真实 smoke](docs/NEXT_BASELINE_RUN.md)：其中给出参数收集方式、需要修正的 endpoint 接入、首批 15 次生成请求 / 16000 输出 tokens 上限及验收顺序。环境和参数就绪后，远程在该范围内启用调用并执行，不继续停在 mock 或重复询问是否允许相同小批实验。

用户随后要求本机“开始验证”。本轮使用独立 Colima profile 做限时、无模型的软件模拟检查，实际结果见 [Mac VM 验证](reports/MAC_VM_SMOKE.md)。不收集或使用模型密钥，以下模型任务数尚未增加。

## 先看结论

**当前没有完成真实 baseline 复现。远程第一个目标是打通 P0。**

| 已有证据 | 实际状态 |
| --- | --- |
| pinned upstream | `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`；submodule 原始 tracked 文件未改 |
| 本项目单测 | 历史 70 tests 通过，需在远程重新执行 |
| upstream CLI unittest | 历史 7 tests 通过；用的是本项目轻量 Python 环境 |
| 原始 CLI dry-run | 历史 exit 1，缺少 `dotenv`；full upstream sync 当时仅预览，未安装 |
| synthetic campaign | 9 case：6 个有效 mock pair、3 个 invalid；标签 api=1、gui=2、tie=3、invalid=3 |
| 真实官方 GUI / CLI 任务 | N=0；无模型任务的 `.FCStd`、strict、`evaluation.json` |
| 真实 counterfactual pairs | N=0；P3/P4 为 NO-GO |
| 真实 provider 网络调用 | 0；`ENABLE_PAID_RUNS=0` |

`reports/commands.json` 是早期 Mac 验证记录；`reports/evidence/mock_smoke/` 是完整 synthetic 归档，`INDEX.json` 有哈希。里面的 Mac 绝对路径只用于追溯，远程不可直接执行。不要把历史报告重命名成远程成果。

本次交接已在全新本地 clone（起初 submodule 未初始化）重新验证 bootstrap、70 个项目测试、7 个 upstream CLI 测试和 9 个无付费 mock case。验证记录见 `reports/HANDOFF_VALIDATION.json`。该检查仍不等于 Linux VM 实验。

按需读取：`SPEC.md`、`reports/REPRO_STATUS.md`、`reports/BASELINE_REPRO.md`、`reports/DEVIATIONS.md`、`reports/stages.json`。后续研究接口见 `docs/P4_P5_PLAN.md`，无需重新调研论文。

## 克隆与无付费验证

```bash
git clone --recurse-submodules https://github.com/AnnaXChun/GUILab.git
cd GUILab
export ENABLE_PAID_RUNS=0
bash scripts/bootstrap.sh
bash scripts/test.sh
```

如果远程平台已经 clone 了主仓库，直接从项目根运行 `bash scripts/bootstrap.sh`。它会处理未初始化的 submodule，再核对 SHA。禁止把 submodule 切到最新 main。

```bash
git -C vendor/CADWORLD rev-parse HEAD
git -C vendor/CADWORLD status --porcelain --untracked-files=no
bash scripts/run_smoke.sh --dry-run --output results/remote_mock_001
.venv/bin/python scripts/summarize.py \
  --input results/remote_mock_001 \
  --output results/remote_mock_001/PILOT.md
```

SHA 必须等于 pinned commit，tracked 状态应为空。结果目录已存在会拒绝覆盖，要换新的 run_id；保留失败尝试。默认 bootstrap 只安装轻量依赖，不下载 VM 或大模型。

## 先确认远程机器是否适合实验

“远程 Codex”不等于“有 KVM 的主机”。普通容器即使显示 Linux，也可能没有 Docker daemon、`/dev/kvm` 或嵌套虚拟化权限。GPU 不是这个阶段的必要条件；可用的模型 API 或已有推理服务可以承担模型调用。

```bash
uname -s
uname -m
ls -l /dev/kvm
test -r /dev/kvm && test -w /dev/kvm
docker info
qemu-system-x86_64 --version
qemu-img --version
uv --version
df -h .
```

参考环境为 Ubuntu/Linux x86_64 + Docker + QEMU/KVM。SPEC 建议至少 100 GB 空闲空间，单路 VM 约 8 vCPU、8 GB RAM、64 GB 虚拟磁盘；两路原生 pair 需要额外宿主资源。KVM 必须在当前执行环境内可访问，只有宿主支持却未传入容器仍算 blocker。

Ubuntu 缺少运行时且具有安装权限时，可按 pinned upstream README 安装 `docker.io qemu-system-x86 qemu-utils`，配置 docker/kvm 组后重新登录；不要把权限失败绕过成 root 下不受控执行。uv 缺失时使用其官方安装方式。主机安装操作与模型运行额度分别记录。

本机是 Apple M5 Pro / ARM64，没有 x86 KVM。已使用独立 ARM Colima profile 实测官方容器与 VM 的 TCG 路径，逐次结果见 `reports/MAC_VM_SMOKE.md`。默认入口与网络都遇到兼容性错误，不能把“支持关闭 KVM”理解为原样即可运行。当前 preflight 仍按参考协议严格要求 x86_64/KVM；软件模拟单列 exploratory 结果，不放宽正式 gate。

## P0：官方基线闭环

先在合适的 Linux 上完成完整依赖与原始 CLI dry-run：

```bash
bash scripts/bootstrap.sh --full-upstream
```

该脚本依次运行本项目 sync、upstream CLI unittest，再进入 submodule 做 `uv sync --frozen`、原始 CLI unittest 和 `CLI/run_cli.py --dry-run`。会安装官方运行时依赖，可能包含较大的 Torch/OCR 包；这不代表下载或启动模型权重。不能用当前单测的成功替代原始 dry-run。

镜像准备是独立显式步骤。先检查磁盘和资产是否已提供；没有镜像时，记录下载计划后按官方脚本取得，不依赖 runner 的自动下载默认值：

```bash
cd vendor/CADWORLD
uv run python scripts/python/download_vm_image.py
sha256sum vm_data/FreeCAD-Ubuntu.qcow2
cd ../..
bash scripts/preflight.sh
```

本机本次实测 qcow2 SHA256 为 `edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12`，28,310,503,424 bytes。远程仍须对实际文件独立计算并记录，不能只复制该值作为检查结果；源地址的 main 可以变化。不要把 qcow2 提交到 Git。CAM 官方评分还需要宿主 FreeCAD 1.1.x；前几道 sketch/part smoke 可以避开 CAM。

先核对两个计划任务 `freecad-sketch-061`、`freecad-part-076`，它们都是 creation，不是 preservation 编辑主实验。先实现或执行一次 **无模型的** `DesktopEnv.reset → observe → close` 环境探针，并记录代码与日志；使用 pinned 上游的 provider/controller，不读取隐藏规则给 agent。新增的 `scripts/probe_mac_vm.py` 只检查独立 Docker 基础设施，不能替代这个 DesktopEnv 闭环，实际结果见 Mac VM 报告。

查看模型 smoke 的确切计划命令，仍不请求模型：

```bash
bash scripts/run_baseline.sh --kind gui-connect --dry-run
bash scripts/run_baseline.sh --kind gui-25 --dry-run
bash scripts/run_baseline.sh --kind cli --dry-run
```

少量真实 smoke 已按 `docs/NEXT_BASELINE_RUN.md` 获得后续授权；补齐凭证/服务、环境和预算控制后启用实时命令。GUI-connect 是 2 题、每题最多 3 个 decision turns；CLI smoke 默认只取 sketch-061，最多 8 turns/terminal calls、600 秒、12000 completion tokens。CLI 本地 server 不会自动启动，必须先核对实际 served model ID 与 endpoint。自定义 provider/base URL 需要按 pinned 源码作最小参数适配并记录。

`baseline.py` 的受限执行入口调用原始 runner，并通过 `upstream_launch.py` 对 OpenAI/Gemini SDK 关闭重试、记录 usage 和限制预算；此前只做 HTTP mock 测试。原始 runner 的 prompt、parser、评测逻辑未改。当前 guard 的 call/output-token/wall gate 是 **整次启动共享**，不是每题独立，参数名与报告中不能误写为实际按题重置。600 秒 subprocess timeout 也共享。先测 3-step 连接，不直接开 25-step；25-step 还要求连接验收文件和超过默认 12 calls 的额外预算。

GUI P0 最低验收是至少 1 题完成 reset/action/evaluation/artifact collection，文件包括 `traj.jsonl`、`result.txt`、`evaluation.json`、截图/日志，允许 strict=0，但不能把 run_error 写作任务失败 0。记录 decision turns、atomic GUI actions、model calls、tokens 与 wall time。CLI 也保留原始轨迹、预算与失败原因。

## P1 → P2：原生执行与配对

P0 有真实证据后再做 P1。当前代码是待实测实现，下面是必须先验证/适配的接入点：

| 接入点 | 当前边界与下一步 |
| --- | --- |
| `cad_cf/guest_gui_bridge.py` | 需把固定项目模块部署到 guest，在 FreeCAD GUI 进程启动宏中启动；检查 PySide/Qt 兼容、主线程 ack 与 loopback 请求。不是仅调用 host Python 就会自动安装 |
| `cad_cf/native_backend.py` | `NativeSession` / `NativeWorker` 提供固定接口；检查实际 `FreeCADCmd` 路径、snap 环境、执行超时、保存与重开。禁止把任意 Python/shell 交给模型 |
| `capture_native_checkpoint` | 先 GUI 保存关闭、重开、收集当前 native 文件、摘要、截图和 UI；停机后再记录实际磁盘 SHA。冻结时的当前文档必须与 snapshot 来源一致 |
| `snapshot.create_overlay` / `live.run_plan` | qcow2 overlay 会记录 backing file 的宿主绝对路径，而上游容器只把传入镜像挂载到 `/System.qcow2`。必须验证 backing 路径在容器中可解析；必要时在本项目用独立完整 clone/flatten 或可审计的挂载适配。不要假定当前 overlay 可直接开机 |
| clone 的 GUI 状态 | 上游 Docker `save_state()` 不支持快照。停机磁盘的开机恢复不自动等于原来的 GUI 内存/窗口状态；启动宏/文档/工作台/相机/选中项/截图须实测一致，不满足就 invalid |
| `NativeBackend.close` / `live.run_plan` | 当前两个位置都会关闭 env，需检查上游 close 的重复调用行为和异常清理，确保不污染其他 run |
| artifact 与官方离线评分 | 分支输出在 `/home/user/current/artifact.FCStd`，官方任务通常要求 `/home/user/Unnamed.FCStd`。可信发布与独立 post-hoc 的完整闭环尚未验证；`posthoc.py` 只是可信函数入口，不能声称已有自动化独立评分进程 |
| `candidate_generator.py` / `live.py` | 当前支持冻结 proposal / reviewed live-plan；没有已验证的模型自动生成双路候选流水线。检查公开证据、同 intent、Name/TypeId 和真实 generation cost |
| `self_verifier.py` | 初版公开尺寸 grammar 保守；不覆盖的表达必须 unknown。确认 native validity、dependency preservation 和隔离扰动 probe 的测量，不为制造偏好去放松规则 |

P1 至少要证明一个真实原生 `.FCStd` 经 API 修改后可保存、重开、保留参数化结构，并在 GUI 中同步显示。之后再准备 P2 的两个完全隔离分支，比较同一 source hash、canonical digest、目标属性、截图与 UI 状态。不能在一台 VM 上执行 A、undo 后执行 B。

`python -m cad_cf.counterfactual --config configs/smoke.yaml --live-plan <plan.json> --output results/<new-run>` 是 live 入口。`plan.json` 结构目前由 `cad_cf/live.py` 定义：stage_evidence、checkpoint 字段、stopped_disk、powered_off_source、overlays.gui/api、intent、document、public_task、split、gui/api actions/context。远程应据真实准备结果生成 schema/example 与 plan，不要用占位 SHA 跳过校验。

stage evidence 必须是实际运行结果。`gui.context` / `api.context` 需记录模型、provider、seed/参数、calls、tokens、decision_turns 和 `generation_wall_s`；未知成本不能当作 0。JSONL、pair.json、public_contract、agent_view、state diff、verifier checks、失败分支与最终 native artifact 全部保留。

## P3 与后续门槛

先拿到至少 3 个合法真实 smoke pairs，并对非 tie 差异重测。默认 2 题/3 pairs 上限不等于已授权 24-pair pilot。24 valid pairs 目标需额外明确授权；invalid 与失败也报告分母与原因。没有差异或规则已等效时暂不训练。

公开选样共 140 个 part/sketch，32 个 edit 初筛候选；split=92/25/23，edit 初筛=19/7/6。按 family 与前置来源 SHA 并集分组，seed=20261015。sketch-edit 只有 1 题且在 train，val/test 该分层 N=0。当前真实可配对性仍未知，不能把 32 题直接算有效 pairs。

权重固定 validity=.25、target_progress=.35、preservation=.20、editability=.20，cost lambda=.05、epsilon=.05。只可在 val 调参并在 test 前冻结。训练数据用 `cad_cf.dataset.preference_rows` 拒绝 synthetic、invalid、tie、未知质量和 held-out。P4 predictor 接口存在，训练器未实现；P5 veRL 不在本轮范围。

## 报告、提交与可重复性

持续更新以下真实状态，不只追加成功案例：

- `reports/REPRO_STATUS.md`：命令、SHA、环境、model/provider、实际执行/未执行和 blocker。
- `reports/BASELINE_REPRO.md`：官方 GUI、官方 CLI、extended hybrid 分开。
- `reports/PILOT.md` 与对应 JSON：任务与 pair 分母、质量覆盖率、credit、成本、CI 和 route 指标；没有预测/样本则 null。
- `reports/FAILURE_CASES.md`：真实失败与 synthetic 明确分开；不足 5 个真实 case 就全部列出。
- `reports/DEVIATIONS.md`：每个最小适配的来源路径、差异、影响、验证证据。
- `reports/stages.json`：依据真实证据更新 gate，不直接改 PASS。

旧 `scripts/verify.py` 固定预期 CLI exit 1、preflight exit 2；这只适合历史 Mac 场景。Linux 依赖齐备后的成功退出码为 0，必须先做环境感知适配或分别执行命令；不要为迎合旧测试故意保留依赖故障。

Git 中保留小型脱敏证据与 manifest；大镜像、模型、原生工程批量产物使用约定的外部存储，并记录可取回位置与 SHA。仓库默认忽略 `.env`、results、qcow2、FCStd。禁止上传凭证与宿主无关个人资料；不要把本机私人 Wiki 上传到 GitHub。

远程会话最后需要明确回答：实际执行的命令/任务、真实 artifact 和 strict 状态、实际成本、有效/invalid pair 数、是否有大于 0 的真实可重测工具差异、当前 GO/NO-GO、下一步。任务完成后提交代码；有 GitHub push 权限时推送本次分支，否则交付 commit 与待推送状态。
