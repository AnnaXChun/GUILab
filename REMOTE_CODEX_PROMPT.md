请接手 GUILab，继续少量真实 CADWorld baseline smoke。

最新事实：首批已完成 3 个真实 episode（2 GUI + 1 CLI，2 个不同任务），strict 均为 0，无模型文件；15/15 次生成额度已用完。先修离线坐标合同和 FreeCAD 对象/保存接口，再向用户给出下一批的具体预算；未获新批授权前不得发出新的生成请求。不能新建空账本重开首批。

先读 AGENTS.md、reports/BASELINE_RUNTIME_SMOKE.md、docs/RUN_TCG_BASELINE.md、HANDOFF.md 和 SPEC.md。上游固定 commit e5d0ebab8bd28da6e98c68c61db05747d1647f7b，不重新调研论文、不替换 benchmark。

用户要求开源多模态 Qwen3 系列；当前选择服务实际列出的 qwen3.5-35b-a3b。图片验证已成功，返回 FREECAD，completion_tokens=3。运行 GUI 和 CLI 使用同一 model ID，并加 --qwen-no-thinking：GUI 复用 pinned Qwen3-6 adapter，CLI 使用上游 send-chat-template-kwargs。这不证明服务端权重身份，不下载模型。

用户无法提供 KVM，不再索取 KVM，不安装 VMware。Mac ARM 原生 QEMU/TCG 已接入 pinned DesktopEnv 与 GUI/CLI runner；单实例空 GUI 的 reset/observe/action/close 已通过。可信 GUI 建模、保存关闭重开、参数修改已通过。旧超时失败与单实例验收中间失败均保留。TCG 是独立探索环境，不与参考 Linux/KVM 硬件效率混报；正式 TypedWorker 与 ACTC 双分支同步尚未验收。

endpoint/key 接入、SDK 零重试、GUI 和 CLI 一次派发、共享 SQLite 批次预算已实现。先检查本环境的 secret 与配置，只收集缺项；本机 .env 不随 Git 上传，不能假定远程已有凭证。不要把 key 写进 Git、argv、日志或报告，也不要上传完整模型服务目录。

首批真实 smoke 已授权：2 个不同任务，GUI sketch-061、part-076 各最多 3 turns，CLI sketch-061 最多 8 turns；整批最多 15 次生成请求、16000 输出 tokens。当前批次已包含早期 GPT HTTP 500 和后续 Qwen 图片验证，实际剩余额度与任务结果以最新报告和原共享账本为准；若 GUI 各用满 3 次，CLI 最多剩 7 次。不能在远程新建账本重新获得一批预算，先恢复既有账本或可信汇总并保持累计占用。未知 usage 不当作零成本。

默认 ENABLE_PAID_RUNS=0 是无人配置保护；环境、参数与该批剩余额度就绪后，单次命令设置 1 继续，不重复询问同范围许可。API 错误不自动重试；显式用户更正配置后才可记录 correction 恢复账本，历史失败与未知 token 预留不可删除。此授权不包含 25-step 追加、24-pair pilot、full-200、自动下载大模型、训练或 veRL。

先完成 P0 的真实 baseline 闭环，报告 strict=0 与 run_error 的区别，官方 GUI-only、CLI、extended hybrid 分开。3-turn smoke 不是论文成功率复现。P1 原生 worker、GUI/API 同步、同 S0 隔离尚待实测，不能直接开始 ACTC pairs。stages.json 必须依据证据更新，参考环境 gate 不手改 PASS。

完成后保留全部成功与失败，更新 reports/{REPRO_STATUS,BASELINE_REPRO,PILOT,FAILURE_CASES,DEVIATIONS}.md、机器可读汇总与脱敏 trace。提交代码并报告实际命令、任务 ID、artifact、评分、调用/token/wall 成本、阻塞及 GO/NO-GO。有既有 GitHub 推送授权时直接推送；没有凭证就交付 commit 与待推送状态。
