#!/usr/bin/env python3
"""Print the current handoff evidence without launching a VM or a model."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.dry_run:
        print('只读handoff.json、最新命令清单与reports/stages.json，不启动VM或模型。')
        return
    handoff = json.loads((root / 'handoff.json').read_text())
    stages = json.loads((root / 'reports/stages.json').read_text())
    command_file = root / handoff.get('latest_commands_report', 'reports/commands.json')
    commands = json.loads(command_file.read_text())
    rows = commands.get('commands', []) if isinstance(commands, dict) else commands
    print('直接执行：')
    for row in rows:
        command = row['command']
        if isinstance(command, list):
            command = ' '.join(command)
        print(f"exit={row['exit_code']}  {command}")
    totals = handoff.get('latest_totals', {})
    gui = handoff.get(handoff.get('latest_run', ''), {})
    controls = handoff.get(handoff.get('latest_gui_controls', ''), {})
    replay = handoff.get('offline_gui_protocol_replay', {})
    print(f"GUI控件={controls.get('status', 'NOT_RECORDED')}；离线协议复放={replay.get('status', 'NOT_RECORDED')}。")
    print(f"模型任务={gui.get('task_id')}；状态={gui.get('status')}；strict={gui.get('strict')}；文件={gui.get('artifact_count')}。")
    print(f"本轮生成={gui.get('model_calls')}，input/output tokens={gui.get('input_tokens')}/{gui.get('output_tokens')}；剩余调用={gui.get('remaining_generation_calls')}。")
    print(f"累计生成={totals.get('generation_calls')}；有效评估episode={totals.get('evaluated_episodes')}；不同任务={totals.get('unique_tasks')}；真实pairs={totals.get('real_pairs')}。")
    print(f"项目单测={totals.get('project_tests')}；全部项目VM已停={totals.get('all_project_vms_stopped')}；美元总费={json.dumps(totals.get('total_cost_usd'))}。")
    print(f"参考P0={stages['P0']['live_status']}；正式TypedWorker/GUI同步与same-S0仍未验收；本轮模型未命中方向对话框按钮。")
    print('深度交互：GUI控制与原生保存重开通过，模型GUI任务仍未成功。下一步验收正式同步与隔离；真实pairs=0，P3/P4 NO-GO，不重开耗尽账本，不再索取KVM。')


if __name__ == '__main__':
    main()
