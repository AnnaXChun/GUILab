#!/usr/bin/env python3
"""Bounded visible VM for trusted GUI diagnosis; no model or task inputs."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.qemu_runtime import NativeQemuProvider


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=1200)
    args=parser.parse_args()
    if not 1<=args.seconds<=1800:parser.error('bounded duration required')
    config=json.loads(args.config.read_text())
    runtime=NativeQemuProvider(**config)
    try:
        runtime.start_emulator(str(runtime.base))
        (runtime.output/'session.json').write_text(json.dumps({'endpoint':runtime.endpoint,'ready':True,'visible':runtime.visible,'deadline_seconds_after_boot':args.seconds},indent=2)+'\n')
        print('Visible VM ready at '+runtime.endpoint,flush=True)
        started=time.monotonic()
        while time.monotonic()-started<args.seconds:
            if (runtime.output/'STOP').exists() or runtime.process.poll() is not None:break
            time.sleep(1)
    finally:
        runtime.stop_emulator()
    return 0


if __name__=='__main__':raise SystemExit(main())
