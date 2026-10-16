请接手 GUILab，在远程环境中推进少量真实 CADWorld baseline smoke。

先读 AGENTS.md、docs/NEXT_BASELINE_RUN.md、HANDOFF.md、SPEC.md。上游固定为 e5d0ebab8bd28da6e98c68c61db05747d1647f7b，不重新调研论文、不替换 benchmark。

用户已经明确要求真正运行几个小实验，而不只是继续 mock。你接手后先检查已有配置，再向用户一次性收集缺失的 BASE_URL、准确 MODEL_ID、接口类型以及 API key 的 secret/环境变量配置。GUI 需要图片输入能力，CLI 的接口兼容要按 pinned 代码核对。不要向这个已结束的本地交接会话索取密钥；真实实验由你所在的远程环境执行。

同时检查 Linux x86_64、可访问 /dev/kvm、Docker daemon、QEMU、磁盘和官方 VM，完成原始 CLI unittest/dry-run 与无模型 VM reset/observe。普通远程容器不保证有 KVM。缺环境就报告具体解除条件，不伪造运行结果。

当前 baseline.py 写死了 GUI Gemini 与 CLI localhost endpoint，CLI 默认 key 是 EMPTY；仅设置通用 OPENAI_API_KEY 不保证生效。按 docs/NEXT_BASELINE_RUN.md 先在本项目做最小 endpoint/key 接入与 HTTP mock 验证，保留原始 runner、prompt、parser、评分器以及零重试/usage/budget guard。

少量真实 smoke 已获授权：首批最多 2 个任务，GUI sketch-061 与 part-076 各 3 turns，CLI sketch-061 最多 8 turns，另有 1 次小型 endpoint 生成验证；整批最多 15 次生成请求、16000 输出 tokens，细项和时限见 NEXT_BASELINE_RUN。默认 ENABLE_PAID_RUNS=0 保留；参数、环境、计量预算就绪后为该批设置 1，直接运行并完成结果收集，不再重复申请同一小批的启用许可。此授权不包含 25-step 追加、24-pair pilot、full-200、自动下载大模型、训练或 veRL。

不要把 key 写入 Git、argv、日志或报告。API 错误不自动重试；失败请求计入额度。请求与成本按整批累计，不因 GUI/CLI 分别启动而重置。凭证缺失、接口不兼容、环境不可用或需要扩展预算时，给出具体缺项再继续。

目前只有历史 70 个项目测试、7 个上游 CLI 单测和 9 个 synthetic case，真实任务与 pairs 为 0。真实任务 strict=0 与 run_error 分开，官方 GUI-only、官方 CLI、extended hybrid 分开。先打通 P0；再验证 P1 原生保存重开与 GUI/API 同步，后续 pairs 不越级。

完成这批后保留全部成功/失败样本，更新 reports/{REPRO_STATUS,BASELINE_REPRO,PILOT,FAILURE_CASES,DEVIATIONS}.md、stages.json 与脱敏证据，提交代码并报告真实命令、任务 ID、artifact、评分、调用/token/wall 成本、阻塞和 GO/NO-GO。不要以新一轮泛泛计划结束可执行的工作。
