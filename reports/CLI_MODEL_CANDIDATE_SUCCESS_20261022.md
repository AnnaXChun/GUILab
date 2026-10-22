# 模型候选已通过原生验证

part-014 的两个独立模型响应已从同一原捕获 S0 各执行一次，原生 Pad→Pocket、保存关闭重开与每个分支六个参数/控制探针均通过，Q=1/1、credit=0。代码字符串未人工修改，原生 XML 和实际派发 payload 的独立审计 PASS。两条代码字符串相同，响应和请求记录分别保留；这是一个有效 tie。

| 任务 | 候选 | 接口检查 | 实际原生执行 | 原生 Q |
| --- | --- | --- | --- | --- |
| part-001 | A | 拒绝：BaseFeature=body 超出冻结范围 | 0 | unknown |
| part-001 | B | READY | 0，另一分支拒绝，整对跳过 | unknown |
| part-014 | A | READY | 1，保存重开与六探针通过 | 1 |
| part-014 | B | READY | 1，保存重开与六探针通过 | 1 |

本批实际 4 次模型请求，11976 输入/1975 输出 tokens，其中 reasoning 1705；接口接受 3/4，实际执行 2/4，执行的两个候选均通过。第二候选不接触第一候选或 verifier。两个控制 pair 在模型前均 Q=1/1、credit=0。有效自然 pair=1、训练样本新增=0。该开发小批不估计总体成功率，未给 part-001 的拒绝代码设几何 Q=0。

通用 API 说明先在独立圆形文档中验证，16 项检查通过。确认 Profile 为 App::PropertyLinkSub、BaseFeature 为 App::PropertyLink，Pad 没有 Base/Mode 字段，数值/单位字符串/Quantity 赋值有效。Quantity 的字面量构造最小放行，历史四条原拒绝理由经回归验证保持不变。

保留两次前置失败：API 预检 001 将重开的 tuple Profile 当直接对象读取；guided native 001 的 part-014 A 控制在 110 秒内部 worker 上限退出，B 通过，模型请求为 0。修正 tuple 读取后 API 预检 002 PASS；将新可信 worker 上限设为 180 秒、对应 HTTP 等待设为 200 秒后，guided native 002 的控制与模型成功。默认传输上限 120 秒保留；失败请求不在旧 clone 重发。

本轮前置与候选共四次 VM 生命周期、1410.861 秒，四台均停止。共 14 次 /execute：14 次有完成传输记录，包含两次已知 worker 失败，uncertain=0；其中模型候选执行 2 次。旧模型账本 SHA 未变，本批四次额度已经结束。全量 CLI 为另一个已授权实验，不能混入本批计数。

实际命令为 `probe_pad_api.py` 的 001/002、`run_cli_causal_credit.py` 的 guided native 001/002、`audit_cli_causal_credit.py --run results/cli_causal_pad_guided_native_20261022_002`。后续交付验证为 281 项项目测试与 7 项上游 CLI 测试通过；独立原生协议审计为 `PASS_NATIVE_MODEL_PROTOCOL_AUDIT`。

当前 GO：模型代码块原生执行、固定后续代码和参数响应。方法增益与训练仍 NO-GO。全量 200 题 CLI 已按 `docs/MODEL_CANDIDATE_AND_FULL_CLI_20261022.md` 启动，结果由独立表格统计；本报告不增加官方 baseline episode。
