# 原生文件与失败分析

| 类别 | 保存任务 | 保存文件 | 已审计 | 原生重开 | 状态有效 | 编辑探针通过 | 探针失败 | 探针不适用 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| part | 55 | 55 | 55 | 55 | 37 | 13 | 17 | 25 |
| sketch | 52 | 52 | 52 | 51 | 37 | 22 | 14 | 15 |
| assemble | 3 | 3 | 3 | 3 | 2 | 0 | 1 | 2 |
| cam | 6 | 6 | 6 | 6 | 6 | 0 | 3 | 3 |
| mesh | 2 | 2 | 2 | 2 | 1 | 0 | 1 | 1 |
| macro | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 |
| appearance | 3 | 3 | 3 | 3 | 3 | 1 | 0 | 2 |
| fem | 2 | 2 | 2 | 2 | 2 | 2 | 0 | 0 |
| cloudpoint | 2 | 2 | 2 | 2 | 2 | 0 | 0 | 2 |
| techdraw | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| measure | 3 | 3 | 3 | 3 | 3 | 2 | 0 | 1 |
| 总计 | 129 | 129 | 129 | 128 | 93 | 40 | 37 | 51 |

原生重开、对象状态和编辑探针分别统计。探针失败只说明本次通用探针未通过，不能据此断言整个文件不可编辑。
审计使用独立临时副本，不修改原文件、不读取官方任务规则、不增加模型请求。

| 结果类型 | 题数 |
| --- | ---: |
| construction_process_wrong | 11 |
| wrong_document_structure | 89 |
| no_output_file | 56 |
| EXECUTION_UNCERTAIN | 13 |
| OFFICIAL_PASS | 14 |
| STARTUP_BEFORE_MODEL | 2 |
| precondition_not_used | 2 |
| shape_correct_process_wrong | 5 |
| diagnostics_unavailable | 8 |
