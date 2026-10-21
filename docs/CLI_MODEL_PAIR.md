# 捕获S0的模型配对

本轮在模型请求前保存并重开原生圆环，再让模型独立生成两个测量代码块。配置为`configs/cli_model_pair_20261021.json`，授权来自用户在上一轮“下一步捕获S0并生成模型候选”的交接后继续要求推进。批次最多2次生成、4096输出tokens、3次原生派发，完成即停。

## 目标与来源

使用已用于开发的`freecad-measure-003`公开instruction，圆环半径为5mm和2mm。该任务不构成独立测试集。模型仍为已有托管服务的`qwen3.5-122b-a10b`，temperature=0.7、thinking=false；服务别名不证明权重哈希。API/key沿用ignored配置，不写入代码、argv或证据。

任务工程状态由可信seed代码创建`Part::Torus`及远离它的`Guard`。共同语义子目标是写入`Torus.SurfaceArea_mm2`，使其在半径变化、原生重算及保存重开后保持正确。保存后的参数响应是工程扩展目标，与官方baseline成绩分别报告；本轮不运行官方评分。

## 请求和执行顺序

准备worker保存`.FCStd`，关闭、重开并重算，记录seed字节SHA、canonical state SHA和实际对象/参数/几何。该记录返回后，host先落盘`captured_s0.json`，再调用模型，两次请求的messages与prompt SHA完全相同。第二次不提供第一次候选或任何质量反馈。模型输入只有公开instruction、语义子目标、当前原生状态与固定输出接口。

候选只能通过JSON返回一个代码字符串。保留原response、usage和代码SHA；静态检查只允许查找Torus、添加规定Float测量属性及设置它的值/表达式。几何、半径、placement、Label及Guard都不能修改。不合规候选保留拒绝原因，不自动修复，不执行单边pair。该限制是本实验的代码块接口，与官方terminal自由脚本协议单列。

两候选都通过接口检查后冻结pair。各分支独立FreeCAD进程、文档、工作目录，从同一seed字节复制，候选前核对canonical state；每候选只执行一次。固定续执行`doc.recompute()`，共同保存关闭重开。两个半径分别±20%，加零扰动和Guard负控制；每个探针从保存artifact副本开始，只重算FreeCAD，不重放模型代码。

隔离范围是document/process/workdir，共用一台VM，不声称强OS sandbox或原GUI/API双VM ACTC验收。本轮只执行受接口约束的模型测量代码块，不传递endpoint/密钥给guest。

## 对照与限额

复用相同两条模型样本和原生观测，离线比较首样本A、初始数值检查、参数响应终局检查、Best-of-2和相减credit选择。tie固定选择A。credit只表示同一S0和固定续执行下的Q差值，当前终局响应检查和credit选择相同；单pair不能估计训练或总体收益。打乱对应只作离线sanity check。

SDK重试0，模型请求timeout60秒，模型窗口180秒；未知usage/请求错误停止后续模型调用，原reservation保留。Native worker110秒，VM/派发总窗口1200秒，`/execute`单次派发、不确定执行停机隔离。旧账本全部核对SHA，额度不恢复。默认`ENABLE_PAID_RUNS=0`，仅已授权小批命令单次设1。

60秒首请求超时后，失败批次和2048未知tokens预留保留。服务适配配置`cli_model_pair_service_fix_20261021.json`使用新的S0、输出目录与账本，单请求110秒、模型窗口300秒，仍限2请求；两批实际请求总上限为3。该适配完成即停，后续不自动追加第三批或修改旧额度。它是新配置下的新独立采样，不是对超时请求的transport重试。

服务适配已返回两条代码，其中B用`hasProperty('SurfaceArea_mm2')`的只读查询，初始白名单遗漏导致拒绝。原拒绝记录保留后，仅放行固定测量属性查询，不改变response文本。无模型执行脚本`execute_saved_cli_model_pair.py`把已停止捕获磁盘作为只读backing，在新overlay中核对原seed与canonical state再执行已有候选。因此没有重新生成S0、没有新增模型请求；新执行worker的接口适配单独记录。

```bash
ENABLE_PAID_RUNS=0 .venv/bin/python -m pytest tests/test_cli_model_pair.py -q
ENABLE_PAID_RUNS=0 .venv/bin/python scripts/run_cli_model_pair.py \
  --dry-run --output results/<fresh-mock>
ENABLE_PAID_RUNS=1 .venv/bin/python scripts/run_cli_model_pair.py \
  --runtime-config results/<verified-native-runtime>.json \
  --output results/<fresh-model-pair>
```

每个输出目录拒绝复用。缺凭证/VM配置记具体blocker。失败、候选拒绝、unknown、tie与完整JSONL保留；本轮训练eligibility恒false，不新增官方baseline episode，不训练、不下载权重、不跑full-200或veRL。后续是否扩展任务由实际结果与独立分组/对照设计决定。
