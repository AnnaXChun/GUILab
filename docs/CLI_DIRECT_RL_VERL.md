# 直接 RL：接入远程已有 veRL 环境

2026-10-23 用户决定跳过 SFT，直接做 RL，并说明远程已有 veRL Docker 和之前的训练代码。复用该环境、权重及训练实现，先验证 RL 能达到什么结果。此前“不接 veRL”“先做 SFT”“等待局部信用非 tie 再训练”的安排不再约束首轮普通 RL。GUI 停止、固定 CADWorld upstream、评测规则隔离、原生文件检查与单次派发要求继续生效。

当前交付是接入契约和顺序，adapter 尚未实现。远程代码路径、启动脚本、veRL 版本、现有模型和 GPU 配置尚未读取；用户提供的远程环境存在与本项目接入验收分别记录。没有在本 Mac 安装训练依赖、下载权重或启动训练。

## 需要适配的接口

| 接口 | 复用内容 | 本项目需要补的部分 |
| --- | --- | --- |
| RL 任务数据 | `manifests/public_tasks.json`、公开字段过滤、供应文件 SHA | 导出旧 veRL reader 实际需要的 prompt/任务字段，按任务家族和供应文件来源分组；成功示范不是 RL 输入的必要条件 |
| 多轮 rollout | pinned `CLI/prompts.py`、`terminal`/`finish` schema、JSON 解析与脚本策略 | 接旧 veRL 的 agent loop/tool callback；模型生成来自当前训练 policy 的 rollout engine，返回 assistant tokens、logprobs、policy version 与 loss mask |
| FreeCAD 环境 | CLI 任务路径、一次派发账本、原生 observer | 新增 Linux CPU 容器 worker 的 reset/step/finalize/close；每个 rollout 独立进程、文档和目录，跨轮保留自己的文件 |
| 训练奖励 | `cad_cf.cli_data.public_goal`、原生保存重开/重算/编辑审计 | 从离线审计结果适配为在线 reward service；返回已知 scalar reward 或 invalid，而不是把所有未知转成 0 |
| checkpoint 评测 | pinned CLI runner、官方离线 evaluator、全量结果汇总 | 在同一学生模型、任务、工具、预算和执行后端上比较 step 0 与训练后 checkpoint，报告成本、覆盖率与失败；官方规则不进入训练容器 |

规划的新代码集中在 `cad_cf/rl/`：任务数据、FreeCAD 环境、奖励和版本适配的 veRL agent loop；评测由单独脚本调用已有 runner。以远程旧代码的真实接口决定最终文件与类名，不先猜 veRL 版本专属的 import 或配置键。优化器、并行策略、checkpoint 和现有训练日志优先复用远程代码。

## 执行后端与工具

GPU 容器承担 policy 更新和 rollout 模型推理；CPU FreeCAD worker 承担终端执行、原生建模和奖励观察。FreeCAD 使用与已验证环境对应的 1.1.0 运行时，须核对构建身份、Python ABI、Part/Sketcher 模块、单位和表达式行为。两个环境分开配置依赖，避免改变现有 veRL 的 torch/CUDA/vLLM 组合。

pinned CLI prompt 已明确支持 FreeCADCmd、Python API 和宏，本轮不需要 KVM。先实测 Linux 容器中的 FreeCADCmd；涉及 FreeCADGui 的公开任务功能需额外核验 offscreen 支持。Mac TCG 和已有官方 VM 作为参考执行环境，训练 rollout 改为容器后必须单列执行协议。核验原生文件、对象类型、参数响应和重置行为后才能报告该后端可用。

环境接口固定为：

- `reset(task_ref, rollout_id, group_id)`：复制公开供应文件，记录来源与初始原生状态 SHA，建立独立工作目录。GRPO 同任务组的所有成员从同一 S0 开始。
- `step(execution_id, terminal_script)`：执行一次，返回 stdout/stderr、退出码和执行状态。已知脚本失败进入模型轨迹，允许模型在下一轮自己修正。
- `finalize()`：收集 `/home/user/Unnamed.FCStd`，独立保存重开、重算与公开目标检查，记录 artifact SHA。
- `close()`：结束该环境，保存完整 trace。非幂等调用不自动重试；执行结果不确定时隔离 rollout。

训练 task worker 只能看到自己的公开输入和输出；不挂载官方 evaluator、reference、其他任务结果或模型服务密钥。终局审计由可信 worker 执行。候选 Pocket 小批的 AST 范围检查只适用于它的局部实验，不能替代完整 terminal RL 的工具合同。

模型的所有 assistant 生成片段进入正确的 loss mask；user 输入、tool 返回、原生审计文本与奖励结果不参与 policy token loss。工具解析、截断、finish 和上下文裁剪都保留在轨迹。保留 token IDs、logprobs、policy/checkpoint 身份、工具调用 ID 与对应结果，避免把托管 Qwen API 的轨迹当作当前 policy 的 on-policy rollout。

## 首轮奖励

首轮先做普通 episode-level RL。它从任务开始实时采样并得到终局奖励，不依赖 3 条 SFT 示范或非 tie preference。局部信用 RL 是后续方法对照，当前不会把 synthetic 控制或 tie 导入训练。

先采用明确的二值奖励：公开完整任务目标通过，且 `.FCStd` 原生重开、重算和所需结构检查通过，记 1；有充分观察证明未达到要求，记 0。编辑响应只在公开任务语义或明确冻结的工程扩展要求适用时计入；不能因通用探针不适用将任务判为失败。文件存在本身不等于成功。

当前 `public_goal` 只支持明确的直线、圆和圆环测量语法。首先编译覆盖表，选入有完整公开任务检查器的任务；不对 200 题统一套“保存文件即奖励”。Pad/Pocket 的现有局部 checker 使用特定 S0/可信前缀和工程扩展，不能直接当作所有完整任务的 reward，需任务级适配后单列验证。

未知与模型失败分开处理：

| 观察 | RL 处理 |
| --- | --- |
| 输出格式/工具参数错误、已知任务未完成、原生文件确定无效 | 记已知失败，保留轨迹，可给 0 |
| 一次 terminal 脚本报错，后续模型完成任务 | 保留错误与修正；按最终可信检查给奖励 |
| 奖励语义不支持、审计证据缺失 | 标为 invalid，不伪造 scalar |
| 环境启动失败、非幂等执行不确定 | 标为环境 invalid，隔离；不当作模型能力的 0 |
| GRPO 一个同任务组有 invalid 成员 | 首轮丢弃整个组并报告原因，保持冻结的 group size；不自动补采或重放 |

若已知 GRPO 组的奖励全相同，组内优势为 0。记录有奖励差异的组比例、全零组、invalid 组、工具错误、KL、熵与每次更新成本。全零奖励持续存在时先检查环境、工具协议、奖励覆盖和任务难度，不能由 loss 有数值声称模型改善。首轮不增加未经校准的多项 shaping 奖励。

## 远程接入与首轮实验

先读取旧代码和现有启动脚本，确认 Docker 镜像 digest、veRL commit、Python/torch/CUDA/rollout backend 版本、学生权重/processor 路径、GPU 数量与显存。只收集版本和必要配置，不输出密钥、完整环境变量或下载新的大模型。既有算法可运行时先沿用；已有 GRPO 支持时优先使用，避免同时迁移框架和算法。

按以下顺序验收：

1. 无模型环境 smoke：完整公开任务 reset、一次 terminal、原生保存重开、已知失败、unknown 隔离、两个 rollout 的同 S0 与文件隔离。
2. 使用现有学生模型采一个同任务组，验证 assistant loss mask、logprobs、policy version、工具结果对应、reward 和一次 backward/checkpoint。
3. 新 run 冻结小批上限，建议首轮最多 20 次更新、每任务 4 条 rollout、最多 20 轮与 16384 输出 tokens；实际 batch/并发按已有脚本和显存确定。checkpoint 评测节点为 0、5、10、20。任务集合与总生成/执行预算在启动前固定。
4. 用相同学生模型的 step 0 做基准，按同预算比较训练后 checkpoint。先报告训练任务与预留验证任务，之后再按新冻结评测预算扩展覆盖。

学生模型若缺多模态能力，则只在不依赖图像的明确任务子集上做实验，并单列范围；不静默删除图像后报告原协议全量成绩。预留任务不能按训练后表现挑选，供应文件来源相同的任务不能跨分组泄漏。此前全量 200 题已经被测试，新的结果不声称这些题从未被观察。

结果表应包含 checkpoint、模型身份、完整任务分母、可评估覆盖、公开目标奖励、官方离线通过率、原生有效率、参数响应、invalid、生成 tokens、CPU 执行时间和 GPU 时间。此前 Qwen3.5-122B 的 7.00% 是托管模型/TCG/特定预算的历史值；若学生或后端不同，不能直接将差值归因于 RL。

## 当前接手信息

待用户提供可访问的远程旧代码仓库或目录及现有训练启动脚本后，先匹配真实 veRL 接口再实现适配。首轮普通 RL 不等待 Pocket 非 tie，也不做 SFT；已有原响应、失败、账本与基线保留。默认不自动下载权重或启动没有冻结预算的长训练。
