# GUI 定位校准

2026-10-20，用户同意[六次定位校准方案](GUI_COORDINATE_AUDIT.md)。本轮已完成6次真实生成，Qwen3.5-122B服务在官方像素要求下返回的数值，更符合0..1000归一化坐标。**坐标约定不一致已有实测证据，直接按像素执行会点击到目标左侧。** 显式归一化要求仍有小范围定位误差，尚未达到稳定操作GUI的验收条件。

## 固定设置

模型服务别名为`qwen3.5-122b-a10b`，thinking=false，temperature=0。同一张1920×1080失败截图中的OK、Cancel、XY-plane各预测两次，分别采用官方pixels与已有normalized1000后缀，每次新建单轮agent、空history。接口、截图字节、目标指令和输出上限相同；顺序为OK的pixels/normalized、Cancel的normalized/pixels、XY的pixels/normalized。

代码、6次上限配置和离线标注在首次请求前提交为`6caebeb`。完整版本与源码SHA见[manifest.json](evidence/gui_grounding_20261020/manifest.json)。每次最多256输出tokens，整轮1536；SDK自动重试0。运行15.18秒，用量14825输入/473输出tokens，无接口错误或未知usage，本轮剩余调用0。此前6本账本SHA均保持不变，累计真实生成从226增至232。

模型只收到原始截图及目标名称，未收到标注、Qt控件坐标、历史错误轨迹或任务评分。离线标注只来自事前目视检查，单独保存在`configs/gui_grounding_annotations_20261020.json`；模型收集函数没有标注输入。原图SHA为`bcfb20058d2fcb44c72f5bd6f3c40fdc442264c81651ebad50773ee7fe6159bd`。6份实际请求均只有一张该原图，wire hash、完整文本与完整模型响应见[trajectory.jsonl](evidence/gui_grounding_20261020/trajectory.jsonl)。

本轮没有启动VM、派发点击、创建CAD文件、运行CADWorld episode或ACTC pair。表中命中只表示点落入事前标注的可见控件区域，未证明操作系统实际接受该点击。

## 原定两组结果

| 目标 | 坐标要求 | 原始返回 | 换算后像素点（未执行） | 标注范围内 |
| --- | --- | --- | --- | --- |
| OK | 官方pixels | `(483,607)` | `(483,607)` | 否 |
| OK | normalized1000 | `(486,599)` | `(933,647)` | 是，位于上边界 |
| Cancel | normalized1000 | `(546,597)` | `(1048,645)` | 否，比上边界高2像素 |
| Cancel | 官方pixels | `(547,609)` | `(547,609)` | 否 |
| XY-plane | 官方pixels | `(470,473)` | `(470,473)` | 否 |
| XY-plane | normalized1000 | `(475,469)` | `(912,507)` | 是，靠近上边界 |

原定pixels组为0/3，normalized1000组为2/3。完整判定与偏移见[analysis.json](evidence/gui_grounding_20261020/analysis.json)。样本只有同一截图的3个目标、每种要求各一次预测；不据此估计跨截图定位准确率或CADWorld任务成功率。归一化组的两个命中都接近边界，也不宣称已稳定点中控件中心。

## 像素组呈现归一化坐标特征

得到两组响应后，额外做了一次无模型、无点击的单位解释检查：将官方pixel要求下的三个原始返回值按已有公式`round(x*width/1000)`、`round(y*height/1000)`换算。没有移动标注或修正模型数字。

| 目标 | 官方pixel要求下的返回 | 按1000换算后的像素点 | 原标注区域 |
| --- | --- | --- | --- |
| OK | `(483,607)` | `(927,656)` | `[884,647,990,672)`，落入 |
| Cancel | `(547,609)` | `(1050,658)` | `[996,647,1102,672)`，落入 |
| XY-plane | `(470,473)` | `(902,511)` | `[893,505,974,523)`，落入 |

三个点全部落入原标注范围，支持当前模型服务在pixel文字要求下仍输出归一化位置。该检查在看到结果后提出，单列为[事后单位假设](evidence/gui_grounding_20261020/posthoc_unit_hypothesis.json)，不把原定pixels组改判3/3，也不把它当成第三组真实实验。

这也修正了上一轮仅凭旧响应无法判断单位的状态：当前已获得新的同图、同目标响应，显示明确的单位不一致。服务端图像预处理和模型自身坐标习惯仍未单独取证；本结果也不能解释此前长任务中每一次定位失败。

## 下一步配置判断

**原样使用官方Qwen pixel adapter继续跑当前服务，为NO-GO。** 其输出在本轮全部不符合原图像素约定。后续实验须显式声明当前服务的输出坐标单位，按原图宽、高各换算一次，并将历史动作保持在模型输出单位，记录原始值与最终像素值。

已有normalized1000方案在这一张截图上达到2/3，仍有边界误差。下一项应在预先冻结的新截图和目标上确认坐标配置，再做限步GUI单题复测。事后发现的“保留官方prompt、按归一化解释”只作为待验证候选，不能直接宣称修复成功或把同图重解释计成新的独立验证。不通过固定偏移、Qt坐标反馈或人工代点消除误差。

本轮6次预算已用完，没有继续调用模型或重开旧25次批次。正式TypedWorker同步和same-S0恢复继续后移，真实pairs=0，P3/P4 NO-GO。官方GUI-only、显式坐标适配GUI、CLI和Hybrid继续分开报告。

## 实际命令与检查

```bash
ENABLE_PAID_RUNS=0 bash scripts/probe_gui_grounding.sh --dry-run
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q tests/test_gui_grounding.py tests/test_qwen_coordinates.py tests/test_provider_budget.py tests/test_batch_budget.py
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest -q
ENABLE_PAID_RUNS=1 bash scripts/probe_gui_grounding.sh
ENABLE_PAID_RUNS=0 bash scripts/probe_gui_grounding.sh \
  --analyze results/gui_grounding_qwen122_20261020_001/summary.json \
  --annotations configs/gui_grounding_annotations_20261020.json
```

dry-run、26项相关测试和159项全量测试通过，真实收集状态为COLLECTED。原始输出目录为`results/gui_grounding_qwen122_20261020_001`，存在则拒绝启动；分析文件也拒绝覆盖。SDK mock测试验证接口500与未知usage只产生一次请求并停止，正常请求不读取标注、不携带历史截图，6次用完后无法在同目录追加。

第一次离线测试为1 failed/25 passed：测试把normalized后缀中说明history单位的文本误当成实际历史。改为检查历史截图标记后通过，未改变模型prompt或协议，也未产生真实请求。新模块只复用现有APIGate、BatchBudget和pinned agent，未改upstream tracked源码、评分器或已有执行适配。

用量见[provider_usage.jsonl](evidence/gui_grounding_20261020/provider_usage.jsonl)，最终预算及全部6条结果见[summary.json](evidence/gui_grounding_20261020/summary.json)。美元费用保持null，价格未知；本轮用量完整。旧的首次HTTP500未知usage与128-token占用继续保留在累计记录中。

原始SDK响应中的`executed_action`是pinned agent生成的字段名，本诊断没有执行该动作；每条结果的`actions_executed=false`和全局`gui_action_dispatches=0`明确记录了这一点。公开归档原样保留该字段，以免改写原始证据。7份JSON/JSONL逐字复制，SHA清单见[INDEX.json](evidence/gui_grounding_20261020/INDEX.json)；SQLite和本地凭证未发布。

交付复核：29个候选发布文件均未命中本地密钥、endpoint或密钥模式；12个JSON/JSONL解析通过，Markdown本地链接缺失0。13份Markdown的新增中文已按“好好说话”技能机械扫描，半角标点、破折号、编号标题、元话语和对比句式命中均为0，代码与URL按规则排除。复读确认命中边界、预算和实验归属不变，原定结果与事后假设分别保留。终端摘要smoke通过，正确分开本轮6次定位与此前GUI任务；MCP索引已刷新，scripts/docs被索引配置排除的部分由完整源码读取、Git diff和实际运行补验。
