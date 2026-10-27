"""Load only the inspected H3 audio-sync node from the workspace-local LC pack."""
import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parent.parent / 'ComfyUI_LC_AV_nodes' / 'lc_h3_audio_sync.py'
spec = importlib.util.spec_from_file_location('film_h3_audio_sync_impl', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NODE_CLASS_MAPPINGS = module.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = module.NODE_DISPLAY_NAME_MAPPINGS
