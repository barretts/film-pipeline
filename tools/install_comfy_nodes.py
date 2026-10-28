"""Install the exact tested custom-node revisions, refusing to replace existing work."""
import hashlib,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;DEST=ROOT/'comfy-local'/'custom_nodes'
NODES=[('ComfyUI_LC_AV_nodes','https://github.com/lonecatone23/ComfyUI_LC_AV_nodes.git','032d77c7ced1873a28bbc4869c5ba81c42172f90'),('ComfyUI-KJNodes','https://github.com/kijai/ComfyUI-KJNodes.git','2371136d2fa6fd0914e514cd99b36dabe5db9adf'),('ComfyUI-Ref2VA-VSA','https://github.com/Kablex/ComfyUI-Ref2VA-VSA.git','323a0a5f7c636cc70f95464145732f81f04a72e9'),('Comfyui-Memory_Cleanup','https://github.com/LAOGOU-666/Comfyui-Memory_Cleanup.git','58de13a6090e04408e343501ff8902c034d9f518'),('ComfyUI-VideoHelperSuite','https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git','4d907bee61e92c2e65af3bd6383a4e4d356126d1')]
def main():
 DEST.mkdir(parents=True,exist_ok=True)
 for name,url,revision in NODES:
  target=DEST/name
  if not target.exists():
   subprocess.run(['git','clone','--no-checkout',url,str(target)],check=True)
   subprocess.run(['git','-C',str(target),'checkout','--detach',revision],check=True)
  if not (target/'.git').exists():raise RuntimeError(f'{target} exists and is not a Git checkout; stop and inspect it')
  current=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
  dirty=subprocess.check_output(['git','-C',str(target),'status','--porcelain'],text=True).strip()
  if current!=revision or dirty:raise RuntimeError(f'{target} differs from the tested revision or has local edits; stop and inspect it')
  print('Verified',name,revision)
 archive=ROOT/'comfy-local'/'downloads'/'MiniMax_H3_Semantic_Bridge_v1.0.zip';target=DEST/'MiniMax_H3_Semantic_Bridge';expected='c4866a0cc554237046814c9cb827a5960caecbd2214d5a5a04b0e43716b437bb'
 if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise RuntimeError('Semantic Bridge archive missing or hash mismatch')
 with zipfile.ZipFile(archive) as z:
  entries=[i for i in z.infolist() if not i.is_dir()]
  for item in entries:
   dest=(DEST/item.filename).resolve()
   if not dest.is_relative_to(DEST.resolve()):raise RuntimeError('Unsafe archive path')
   if dest.exists() and dest.read_bytes()!=z.read(item):raise RuntimeError(f'{dest} differs from archive; stop and inspect it')
  if not target.exists():z.extractall(DEST)
  for item in entries:
   if not (DEST/item.filename).is_file():raise RuntimeError(f'Incomplete existing Semantic Bridge at {target}; stop and inspect it')
 print('Verified Semantic Bridge v1.0 archive and node')
if __name__=='__main__':main()
