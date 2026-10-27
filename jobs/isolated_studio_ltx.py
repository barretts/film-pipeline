"""Start a GPU-enabled local Studio with all writable paths in this workspace."""
from pathlib import Path

source = Path(__file__).with_name("isolated_studio_probe.py").read_text(encoding="utf-8")
source = source.replace("'CUDA_VISIBLE_DEVICES':'',", "")
source = source.replace("'HF_HUB_OFFLINE':'1',", "'HF_HUB_OFFLINE':'0',")
source = source.replace("CPU-only isolation probe", "Local LTX comparison")
exec(compile(source, __file__, "exec"))
