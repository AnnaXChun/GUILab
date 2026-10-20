# GUILab 交接

更新：2026-10-20。仓库：[AnnaXChun/GUILab](https://github.com/AnnaXChun/GUILab)，根目录就是项目。先读本文件、[GUI控件验收](reports/GUI_CONTROLS.md)、[GUI模型复测](reports/GUI_VALIDATION_20261020.md)与SPEC.md；历史CLI成功见[此前续跑](reports/BASELINE_SUCCESS_SMOKE.md)，机器记录见handoff.json。历史失败不可被后续成功覆盖。

GUI控制闭环已通过：controls007在新官方base overlay中用12次单次派发操作创建Body/XY空Sketch、保存关闭重开，7071-byte文件字节不变，151项单测通过。已处理的具体问题为GNOME外部未响应弹窗、探针对话框移动后的旧坐标、30秒观察截止早于90秒阶段等待；不将这些统称为历史唯一根因。六次失败与一次PASS均已归档。

模型复测使用代码提交77d10d0和新VM，Qwen3.5-122B GUI sketch-061官方strict=0、no_output_file；25次生成、88918输入/2328输出tokens、无API错误。第15–25轮未命中Choose Orientation的OK按钮，不能把可信探针成功写成模型成功。GUI模型仍无文件，无原生文件可审计；CLI历史的官方与122B原生成功不变。

累计226次生成、11个attempt、9个有效评估episode，已知输入791185/输出25713 tokens；初次HTTP500未知usage与128-token占用保留，美元总费null。全部本项目VM已停，base/固件SHA前后不变。新25次账本和旧5本账本均保留，本轮不再追加。最新[坐标协议核对](reports/GUI_COORDINATE_AUDIT.md)确认官方Qwen使用原图像素，本项目normalized1000为额外协议；新增两路离线对照通过，最新154项项目单测、4项官方Qwen测试通过。下一步优先模型坐标定位校准，正式worker/Qt bridge同步和same-S0双clone后移，按[验收计划](docs/NEXT_ACTC_VALIDATION.md)推进。真实pairs=0，P3/P4继续NO-GO。

下方详细段落保留2026-10-19的历史，不把其中201次、122 tests或“先做控件诊断”等旧状态当作当前待办。

## 已验证的结果

最新`qwen3.5-122b-a10b` CLI的`success_cli_qwen122_001`在sketch-061官方strict=1.0，8次生成/terminal、1869输出tokens，termination=turn_limit。原文件2924 bytes，SHA为`ebc2e5cbcee52bc49f0b081d67d5d3979a6e10f7205795d6945771403f47d673`；独立无模型VM原生审计PASS，重算/重开、类型树和一次性内存参数编辑通过，模型文件未改。它是原生Sketch，未完全约束，不声称agent主动finish。

Qwen3.6 CLI在`freecad-sketch-061`获得官方strict=1.0，14次生成、13次terminal、5823输出tokens；模型自行保存并重开。原CLI prompt、tools、parser、评分器与diagnostics均复用pinned源码，没有提供答案脚本或人工修复。

独立原生审计发现原文件的Sketch.State包含Invalid，Document.xml记录attachment错误。因此官方成功保留，工程质量判为FAIL，不进入有效训练数据。审计器曾有stdout未捕获、movePoint不可用、漏Invalid三次问题；保留原记录，以audit_review.json纠正旧PASS，不改模型文件。

GUI25进入绘图和保存阶段但未存盘，strict=0；预热GUI100在50次真实生成后仍停在欢迎页，主动阻断，随后WAIT均为原adapter fallback。该次strict=null，保留raw score=0，不能作为完整100步测试。撤掉预热的恢复run在第6轮因混合单位history触发越界拒绝，6次/464输出tokens保留；v2将在线history统一为normalized单位，实际pixel执行和JSONL不变。新run沿用同一本账本的剩余44次。最终消耗与终态见本轮报告。

35B/v2的44轮GUI与122B/v2的35轮GUI都strict=0、无文件，卡在Select attachment平面选择；控件展开状态与事件循环仍需独立检查。累计10个attempt、8个有效评估episode、2个运行/诊断错误，涉及2个任务；含探针201次生成，已知输入702267/输出23385 tokens，价格和初次HTTP500 usage未知。所有模型与审计VM已停止，最新122 tests、上游CLI 7 tests和原CLI适配dry-run通过。该题用于调试与选模型，不能作独立held-out成绩。

Qwen3.5首批的2 GUI + 1 CLI均为strict=0，无文件；15次请求、已知输出1369与早期HTTP500未知usage完整保留在[首批历史](reports/BASELINE_RUNTIME_SMOKE.md)。不同模型、预算与坐标合同不合并统计成功率。真实ACTC pairs仍为0。

## 环境与启动

用户无法提供KVM，不再索取，不安装VMware。Mac ARM原生QEMU/TCG已接入官方qcow2、DesktopEnv和GUI/CLI runner。单实例空GUI的reset/observe/action/observe/close、可信GUI参数化保存重开已通过；它们不是模型任务。参考Linux/KVM gate、正式TypedWorker、GUI bridge和same-S0双VM恢复尚未验收。

```bash
git clone --recurse-submodules https://github.com/AnnaXChun/GUILab.git
cd GUILab
bash scripts/bootstrap.sh --baseline
ENABLE_PAID_RUNS=0 bash scripts/test.sh
git -C vendor/CADWORLD rev-parse HEAD
git -C vendor/CADWORLD status --porcelain --untracked-files=no
```

upstream固定`e5d0ebab8bd28da6e98c68c61db05747d1647f7b`，tracked文件不得修改。16个baseline直接依赖来自pinned lock，原CLI dry-run与7个上游测试通过；未安装完整405包或下载模型权重。

VM、固件、.env和SQLite不随Git上传。已有官方qcow2为28,310,503,424 bytes，SHA256为`edbeb3a08d2d75ac4154441d774a0baf92ad8f64a53180ff347960f436ca2f12`；远程必须核验自己的资产，不能直接使用本机路径。按`configs/native_tcg.example.json`填写路径与SHA，重新运行`probe_baseline_env.py`取得本机验收。具体步骤见[TCG指南](docs/RUN_TCG_BASELINE.md)。

下一阶段无模型检查无需API key。未来模型实验只收集缺项：`CADWORLD_API_BASE_URL`、`CADWORLD_API_KEY`和准确model ID；本轮使用过qwen3.6-35b-a3b和qwen3.5-122b-a10b，均thinking=false。服务别名不证明权重哈希。密钥通过secret、环境变量或ignored `.env`提供，不进Git、argv或报告，不假定GitHub secret自动进入远程环境。

## 授权和预算

用户已要求少量真实实验，并追加“继续跑，直到模型任务能够成功，查看官方sh是否可复用”。默认`ENABLE_PAID_RUNS=0`保留为无配置保护，已授权命令单次设为1，无需重复请求同一范围许可。已完成的批次不能在远程重开。

5本账本请求数为15、50、50、50、36，合计201。success账本先用42次，最后CLI122用剩余8次；gui100在50次后blocked，recovery为6+44，122B专用账本为图片1+GUI35。未知usage保留128-token reservation，总token和美元费用null，不报0。不得把未消耗的blocked额度当作新实验授权。

SDK重试为0，/execute非幂等变更单次派发；timeout或不确定写入停止并隔离clone。不得清空账本、删失败或修改上限恢复额度。不启动24-pair pilot、full-200、模型下载、训练或veRL。

## 下一步和有效性边界

先做无模型GUI控件/事件循环诊断，通过后再定义单题GUI模型复测；当前不新增推理。官方sh可以复用原Python入口；GUI sh引用缺失test_rest.json且不透传参数，vLLM sh固定GPU3，CLI wave sh启动四个模型和50题，不能原样启动。

P1必须部署正式guest_gui_bridge，验收Qt主线程ack、TypedWorker保存关闭重开和当前GUI刷新。之后P2才验证同一公开intent、同一S0、两个独立VM/磁盘/workdir；不能用同一base SHA或同任务ID代替S0证明，不能A后undo再B。真实pair、差异重测和训练GO门槛见stages.json，单路成功不自动放行P1–P4。

agent/router/verifier仅接公开白名单字段与当前状态。官方expected/reference/evaluation只在episode后离线评分，不回流在线模型。原论文GUI-only、CLI、显式坐标适配GUI、CADWorld-Hybrid分别报告；不把verifier或局部修复当novelty。

## 证据与提交

本轮脱敏归档位于`reports/evidence/baseline_success_20261019/`，INDEX记录原始与公开副本SHA。完整JSONL保留，截图抽样，其余本地图像哈希列入清单；执行SQLite公开导出仅含payload SHA/state，避免以base64上传原生文件。FCStd、qcow2、固件、凭证、完整模型目录和MCP诊断不提交。

继续更新reports/{REPRO_STATUS,BASELINE_REPRO,PILOT,FAILURE_CASES,DEVIATIONS}.md、机器状态和实际命令。完成适当测试、secret检查后直接提交并推送已授权仓库。scripts/verify.py固定早期Mac失败预期，不能作为通用远程验收。
