# 基线复现

本轮复用 [CADWorld](https://github.com/Zdong104/CADWORLD) 的 pinned commit `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，不修改上游 tracked 文件。Mac ARM 原生 QEMU/TCG 已接入原 GUI/CLI runner；最新逐题结果、成本和命令见 [BASELINE_RUNTIME_SMOKE](BASELINE_RUNTIME_SMOKE.md)。这是限定轮数的真实连接 smoke，不能声称复现论文 full-200 或 17.5%。

## 协议与模型

| 协议 | 本批设置 | 与论文/扩展的关系 |
| --- | --- | --- |
| 官方 GUI-only 代码，TCG 探索环境 | sketch-061、part-076，各最多 3 turns / 每次 512 输出 tokens；保留原 `Use GUI,` instruction；不录视频，保存截图/轨迹 | 复用原 prompt、parser、action/evaluation/diagnostics；使用用户选择的 Qwen3.5，不是原论文同模型同硬件成绩 |
| 官方 CLI terminal-only 代码，TCG 探索环境 | sketch-061；同一 Qwen3.5；只用 terminal，不提供运行时桌面截图；本批最多剩 7 次生成/terminal calls | 原 CLI prompt/tools/parser 与 `/execute` closure；SDK 认证和一次派发由外层保护，单独报告 |
| CADWorld-Hybrid (extended protocol) | 9 个 synthetic case；真实 pair N=0 | 不计入官方 baseline 的任务或成功率，未运行真实扩展协议 |

模型为服务实际列出的 `qwen3.5-35b-a3b`，用户要求开源多模态 Qwen3。图片验证真实成功，返回 `FREECAD`，usage 可计量。GUI 复用 pinned Qwen3-6 adapter，thinking=false；CLI 使用原 `--send-chat-template-kwargs` 并关闭 thinking。服务返回别名不等于权重身份已验证。模型的输入和工具观察不同，不能假称 GUI/CLI observation budget 完全相同。

## 环境接入已验证的范围

原始 CLI 7 个单测重跑通过。CLI 原始 dry-run 在安装受限 baseline 依赖、延迟导入原 registry 后通过；旧缺 dotenv 的失败仍保留。16 个 baseline 直接版本来自 pinned lock，未执行全部 405 个官方包的完整 sync，也未下载模型或 OCR 权重。

真实 DesktopEnv 单实例空 GUI 的 reset/observe/action/observe/close 已通过。可信 GUI 宏可建立 Body/Sketch/Pad、参数修改并保存关闭重开两次；它没有模型任务 instruction，不能计为 baseline artifact 或成绩。正式 ACTC 的 TypedWorker、GUI 主线程桥与同 S0 双 VM 尚待验收。

所有模型请求都进入同一本整批账本，SDK 重试为 0。失败请求计次数；未知 usage 保留占用，不报成 0。GUI 的 `/execute` 和 CLI 原一次派发外层均持久化记录，不确定结果隔离停机。镜像缺失不会静默下载；每次独立 overlay，原 base SHA 单独核验。GUI 两题分开 launch，避免第二次冷启动占用前一 launch 的 600 秒模型 gate。

上游 GUI/CLI 在运行错误时可能写 fallback 0，离线 `cad_cf.baseline_results` 保留原分数，但对 error.json、API error 或 circuit 打开输出 strict=null + reason。有效评估的 strict=0 保留为真实任务未通过。没有原生文件就报告缺失，不补 fixture、reference 或可信探针文件；ZIP 完整性不等于 FreeCAD 可重开或参数化结构已验收。

逐次失败与分母、模型 token、保存状态和阶段 funnel 以本批归档为准。官方 expected/reference 只供 episode 后的原评分与 diagnostics，不输入 agent、router 或 self-verifier。真实 pair 继续为 0，P3/P4 为 NO-GO。

## 本批实测

| 协议 | 真实 episode / 不同任务 | strict | 保存的模型文件 | 失败原因 |
| --- | --- | --- | --- | --- |
| GUI-only / TCG / Qwen3.5 | 2 / 2 | 0、0 | 0 | 连续点击错误位置，欢迎页未关闭；`no_output_file` |
| CLI-only / TCG / Qwen3.5 | 1 / 1 | 0 | 0 | 7 次终端脚本返回已知 API 用法错误，turn_limit；`no_output_file` |
| CADWorld-Hybrid | 0 / 0 | null | 0 | 未运行真实 pair |

共有 3 个有效评估 episode、2 个不同任务；不是 3 个独立任务，不能把 CLI 7 个工具错误当成 7 个 episode。15 次生成上限已用完，已知输出 1369 tokens，另有初次 GPT 500 的未知 usage 和 128-token 保守占用。正式任务 artifact 为 0；可信圆柱文件只证明基础设施。

结论：受限 baseline 运行链路已跑通，模型任务成功尚未跑通，论文成绩未复现。先修坐标合同与 CLI FreeCAD 保存/对象用法，再做新的受限实验；当前首批不再发出生成请求。详细成本、时长、错误和 GO/NO-GO 见本批运行记录。
