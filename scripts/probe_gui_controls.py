"""Run the trusted, model-free GUI control acceptance."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.gui_control_probe import main
if __name__=='__main__':raise SystemExit(main())
