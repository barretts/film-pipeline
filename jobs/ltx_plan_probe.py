"""Read-only Studio plan; no loading, downloads, or secret output."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tools'))
import studio_mcp
client=studio_mcp.Studio(studio_mcp.key_from_environment(),timeout=45)
arguments={'kind':'video','model':'unsloth/LTX-2.5-GGUF','variant':'Q4_K_M','memory_mode':'low_vram'}
response=client.rpc('tools/call',{'name':'plan_load','arguments':arguments})
payload=response.get('structuredContent',{})
print(json.dumps({k:payload.get(k) for k in ('model','download_bytes','est_gpu_bytes','would_evict','would_refuse')},indent=2))
