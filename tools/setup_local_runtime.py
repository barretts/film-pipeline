from pathlib import Path
import hashlib,zipfile,httpx
r=Path(__file__).resolve().parent.parent/'local-runtime';r.mkdir(exist_ok=True)
urls=[('llama.zip','https://github.com/ggml-org/llama.cpp/releases/download/b11941/llama-b11941-bin-win-cpu-x64.zip','67549a639ceca9ac971333b7d5c0a93d080579e1a345b4427deff309c605d864','llama'),('piper.zip','https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip','f3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea','piper'),('ffmpeg.zip','https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/ffmpeg-8.0.1-essentials_build.zip','e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673','ffmpeg')]
with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as c:
 for filename,url,digest,folder in urls:
  f=r/filename
  if not f.exists():
   print('Downloading',filename,flush=True)
   with c.stream('GET',url) as resp:
    resp.raise_for_status()
    with f.open('wb') as o:
     for b in resp.iter_bytes(1024*1024):o.write(b)
  h=hashlib.sha256(f.read_bytes()).hexdigest();print(filename,'sha256',h,flush=True)
  if digest and digest!=h:raise RuntimeError('digest mismatch')
  with zipfile.ZipFile(f) as z:
   for info in z.infolist():
    dest=(r/folder/info.filename).resolve()
    if not dest.is_relative_to((r/folder).resolve()):raise ValueError('invalid archive path')
    if not info.is_dir() and dest.exists() and dest.read_bytes()!=z.read(info):raise RuntimeError(f'Existing file differs; stop and inspect: {dest}')
   for info in z.infolist():
    dest=(r/folder/info.filename).resolve()
    if not dest.exists():z.extract(info,r/folder)
  print('READY',folder,flush=True)
