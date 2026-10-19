# GUILab 交接

更新：2026-10-19。仓库为 [AnnaXChun/GUILab](https://github.com/AnnaXChun/GUILab)，根目录即原 cad-cf-hybrid。按 AGENTS.md、[本批实际结果](reports/BASELINE_RUNTIME_SMOKE.md)、[复现状态](reports/REPRO_STATUS.md)、[TCG 运行指南](docs/RUN_TCG_BASELINE.md)、SPEC.md 接手。机器可读状态见 handoff.json；远程首条消息可使用 REMOTE_CODEX_PROMPT.md。

本批最终为 3 个真实 episode（2 GUI + 1 CLI，2 个不同任务），strict 均为 0，无模型输出文件。15 次生成调用已用完，已知输出 1369 tokens，另有早期失败的未知 usage。下一批先修坐标合同与 CLI FreeCAD API 用法，不得在远程重置账本继续首批。

## 现在已验证到哪里

pinned upstream 为 `e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，submodule tracked 文件未改。Mac ARM 原生 QEMU/TCG 已接入原 DesktopEnv 和 GUI/CLI runner，独立 overlay、SHA、controller、关闭清理都有记录。空 FreeCAD 单实例的 reset/observe/action/observe/close 已通过；可信 GUI 宏完成参数化建模、参数修改、保存关闭重开。这些探针不计模型成绩，正式 TypedWorker 和 ACTC 的 GUI/API 主线程同步尚未验收。

用户不能提供 KVM，不再索取 KVM，不安装 VMware。Linux 容器能够运行 FreeCAD；容器是否具备 Docker、QEMU、桌面与足够资源需要实测。当前 TCG 结果独立于参考 Linux x86_64/KVM 协议，不能以手改 stages.json 为 PASS 替代验证。

本轮已安装 16 个来自 pinned lock 的 baseline 直接依赖版本，以延迟 registry 方式加载原 metric/getter 函数，原始 CLI dry-run 已通过，7 个 upstream CLI 单测重跑通过。没有安装全部 405 个 upstream 包，没有下载大模型、Torch/OCR 权重。旧 dotenv 失败和 GUI 宏失败仍保留在历史证据中。

用户指定开源多模态 Qwen3，当前选择服务列出的 `qwen3.5-35b-a3b`。图片验证返回 `FREECAD`，输入 2077、输出 3 tokens；GUI 和 CLI 使用同一 model ID、thinking=false，实际 episode 结果以本批报告为准。模型别名不等于后端权重身份已核验。CLI 保持 terminal-only，不追加运行时截图。

## 启动与配置

```bash
git clone --recurse-submodules https://github.com/AnnaXChun/GUILab.git
cd GUILab
bash scripts/bootstrap.sh --baseline
ENABLE_PAID_RUNS=0 bash scripts/test.sh
git -C vendor/CADWORLD rev-parse HEAD
git -C vendor/CADWORLD status --porcelain --untracked-files=no
```

远程只收集缺项。`.env` 使用 `CADWORLD_API_BASE_URL`、`CADWORLD_MODEL_NAME`、`CADWORLD_API_KEY`，不随 Git 上传。不要假定 GitHub secret 会自动进入远程 Codex。key 只放所选 secret/环境变量或 ignored 配置，不进 argv、Git、报告；完整服务模型目录和真实服务地址也不上传。

VM 和固件不随 clone 取得。先检查本机/远程已有资产，不静默重下；用 `configs/native_tcg.example.json` 填实际路径和实际 SHA，按 RUN_TCG_BASELINE 做无模型验收。历史 Mac 路径只供 provenance，不能直接执行。本机官方 qcow2 为 28,310,503,424 bytes，SHA256 `edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12`，远程仍要独立 hash。

## 剩余预算与运行边界

用户已授权本机或远程执行同一首批真实 smoke，默认 `ENABLE_PAID_RUNS=0` 仍保留。条件就绪后单次命令设置 1，不重复询问相同范围许可。两地共用一批，不能各开第二批。

整批最多 15 次生成 / 16000 输出 tokens；GUI sketch-061、part-076 各最多 3 turns / 512 输出，CLI sketch-061 原上限 8 turns。早期 GPT 图片验证 HTTP 500 已占 1 次，unknown usage 保留 128-token 占用；用户更正模型后记录 correction，再做 Qwen 图片验证 1 次。因此两道 GUI 各用满 3 次后，CLI 最多剩 7 次。最终实际消耗与剩余额度见报告和共享账本。

共享账本为 ignored `results/first_baseline_batch.sqlite`。移机前恢复该账本或按可信汇总保守迁移，不能用新空账本重置额度。SQLite 本身没有 key，不默认上传公共仓库；公开预算快照供审计。SDK 无自动重试；API 错误/未知 usage 关闭 circuit。只有明确的用户配置更正后才记录 correction 恢复，历史失败不删。非幂等 `/execute` 不重发，终态不确定就停止并隔离 VM。

不授权 25-step 追加、24-pair pilot、full-200、自动下载模型、训练或 veRL。模型 wall gate 从首请求起计 600 秒，单请求最多 110 秒；OS/GUI 冷启动另有限时，整进程最多 1800 秒。截图/轨迹保留，视频关闭，TCG 时延不与参考硬件混报。

## 接下来的验收

先检查本批 GUI/CLI 的实际结果与失败原因。GUI `result.txt=0` 可能是上游异常 fallback，必须结合 error.json、usage circuit 和 diagnostics；`cad_cf.baseline_results` 保留 upstream_raw_score，对运行故障输出 strict=null + reason。有效 episode 的 strict=0 是任务未通过，不能改成服务故障，也不能因 runner 退出 0 宣称任务成功。

P0 baseline 闭环后，P1 仍需部署 `cad_cf/guest_gui_bridge.py`，验收 Qt 主线程 ack、正式 TypedWorker 保存重开、GUI 当前文档刷新。不能用可信圆柱探针替代正式 worker。随后才做同 intent、同 S0、两个独立 VM/磁盘/workdir 的 pair；不能 A 后 undo 再 B。保存关闭重开、相机/工作台/选中项、截图与原生 digest 均须核对，不一致就 invalid。

当前 live plan 接口、native backend、公开契约 verifier、router、split 和 mock 已实现，正式双路流水线尚未实测。官方 expected/reference/evaluation 只能留在可信离线评分端，不能回流 agent/router/verifier。配对数和训练 GO 门槛见 stages.json；9 个 synthetic case 不计真实 pair，P3/P4 不因本批 baseline 自动通过。

## 产物与交付

`reports/evidence/baseline_runtime_20261019/INDEX.json` 包含逐次失败、source snapshot、脱敏 JSONL、截图和哈希。`.env`、完整服务目录、SQLite、qcow2、固件、FCStd 不进 Git；原始本机 results 不代表远程可用产物。原生文件若产生，只按实际做过的 ZIP/FreeCAD 重开/参数化检查报告，不用 fixture 或可信探针补齐模型输出。

继续更新 reports/{REPRO_STATUS,BASELINE_REPRO,PILOT,FAILURE_CASES,DEVIATIONS}.md、机器可读状态和必要证据。完成后提交并推送已授权仓库，报告确切命令、任务 ID、artifact、strict、调用/token/wall 成本、阻塞与 GO/NO-GO。`scripts/verify.py` 固定早期 Mac 失败预期，不作为通用远程验收；使用实际适配后的测试与运行命令。
