"""Read-only machine discovery for the local film pipeline."""
import ctypes,json,os,platform,shutil,socket,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
class MEMORYSTATUSEX(ctypes.Structure):
 _fields_=[('dwLength',ctypes.c_ulong),('dwMemoryLoad',ctypes.c_ulong),('ullTotalPhys',ctypes.c_ulonglong),('ullAvailPhys',ctypes.c_ulonglong),('ullTotalPageFile',ctypes.c_ulonglong),('ullAvailPageFile',ctypes.c_ulonglong),('ullTotalVirtual',ctypes.c_ulonglong),('ullAvailVirtual',ctypes.c_ulonglong),('sullAvailExtendedVirtual',ctypes.c_ulonglong)]
def port_busy(port):
 with socket.socket() as s:
  s.settimeout(1);return s.connect_ex(('127.0.0.1',port))==0
def main():
 mem=MEMORYSTATUSEX();mem.dwLength=ctypes.sizeof(mem);memory={}
 if os.name=='nt' and ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):memory={'total_gib':round(mem.ullTotalPhys/2**30,2),'available_gib':round(mem.ullAvailPhys/2**30,2)}
 gpu=[]
 try:
  r=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=15)
  for line in r.stdout.splitlines():
   name,driver,total,free=[x.strip() for x in line.rsplit(',',3)];gpu.append({'name':name,'driver':driver,'vram_total_mib':int(total),'vram_free_mib':int(free)})
 except Exception as e:gpu={'error':str(e)}
 disk=shutil.disk_usage(ROOT);executables={x:shutil.which(x) for x in ['git','python','ffmpeg','ffprobe','nvidia-smi']}
 result={'os':platform.platform(),'python':sys.version,'cpu':platform.processor(),'memory':memory,'disk':{'path':str(ROOT),'free_gib':round(disk.free/2**30,2)},'gpu':gpu,'executables':executables,'ports':{'8191_in_use':port_busy(8191),'8765_in_use':port_busy(8765)},'existing_local_comfy':str(ROOT/'local-runtime'/'ComfyUI') if (ROOT/'local-runtime'/'ComfyUI'/'main.py').is_file() else None,'tested_profile':'Windows 11, RTX 4060 Ti 16 GiB, 128 GiB RAM, NVIDIA 591.86, PyTorch 2.11.0+cu130; other profiles unverified'}
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
