"""Bounded, readable tails of local process logs; source files stay untouched."""
import re

ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')
PROGRESS=re.compile(r'^\d{1,3}%\|.*\|\s*\d+/\d+')

def log_tail(path,limit=48000):
 if not path.is_file():return []
 with path.open('rb') as stream:
  stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-limit));data=stream.read(limit)
 text=data.decode('utf8',errors='replace')
 if size>limit:text=text.split('\n',1)[-1] if '\n' in text else ''
 text=ANSI.sub('',text).replace('\r','\n')
 lines=[]
 for raw in text.splitlines():
  line=raw.strip()
  if not line:continue
  if lines and PROGRESS.match(line) and PROGRESS.match(lines[-1]):lines[-1]=line
  elif not lines or line!=lines[-1]:lines.append(line)
 return lines[-200:]
