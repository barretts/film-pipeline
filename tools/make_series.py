#!/usr/bin/env python3
"""Series entry points: new-show (writer arc/cast), new-episode (writer draft), run."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
for p in (str(ROOT),str(ROOT/'tools')):sys.path.insert(0,p) if p not in sys.path else None
from local_film import pipeline as P,series as S,characters as REG,writer as W
from local_film.pipeline import JobError
SERIES=S.SERIES

def new_show(a):
 slug=S.slugify(a.id or a.title)
 root=SERIES/slug
 if root.exists():raise JobError('Show already exists: '+str(root))
 root.mkdir(parents=True)
 show={'id':slug,'title':a.title,'logline':a.logline,'brief':a.brief,'style':a.style,'arc_summary':'Not yet planned; writer is about to draft the arc.','width':1280,'height':720,'fps':24,'characters':[]}
 P.atomic(root/'show.json',show)
 log=root/'writer.jsonl'
 try:
  cast=W.draft_cast(show,a.brief,a.episodes,log)
  arc=W.draft_arc(show,{},a.brief,a.episodes,log)
 except JobError as e:
  raise JobError(f"{e}\nThe show skeleton is kept at {root}; draft arc.md and cast.md by hand or rerun after fixing the writer model.")
 (root/'arc.md').write_text('# Story arc\n\n'+'\n'.join(f"Episode {x['number']}: {x['brief']}\nEnds: {x['ending_note']}"for x in arc['episodes'])+'\n',encoding='utf8')
 (root/'cast.md').write_text('# Cast\n\nRecurring:\n'+'\n'.join(f"- {x['slug']} - {x['name']}: {x['role']}"for x in cast['recurring'])+'\n\nPer episode:\n'+'\n'.join(f"- Episode {x['number']}: {x['name']} - {x['role']}"for x in cast['episode'])+'\n',encoding='utf8')
 show['arc_summary']=' | '.join(f"Ep {x['number']}: {x['ending_note']}"for x in arc['episodes'])
 P.atomic(root/'show.json',show)
 bg=root/'cards'/'title-bg.png'
 try:
  bg.parent.mkdir(exist_ok=True)
  from studio_mcp import Studio,key_from_environment,record_call
  import urllib.parse,urllib.request
  key=key_from_environment();studio=Studio(key,timeout=300)
  def call(name,arguments):
   start=time.time()
   try:
    response=studio.rpc('tools/call',{'name':name,'arguments':arguments});ok=not response.get('isError',False)
   except Exception as exc:
    response,ok={'error':str(exc).replace(key,'<redacted>')},False
   record_call(name,arguments,response,start,time.time(),key,ok)
   if not ok:raise JobError(f'Studio {name} failed; see tools/mcp-log.jsonl')
   return response.get('structuredContent',{})
  try:
   call('load_model',{'kind':'image','model':'unsloth/FLUX.2-klein-4B','memory_mode':'low_vram','transformer_quant':'auto','wait_s':50})
   response=call('generate_image',{'prompt':f"Wide establishing vista, empty {a.style.split(',')[0].lower()} landscape at blue hour, cinematic, no people, no text, no watermark. Visual style: {a.style}.",'width':1280,'height':720,'steps':4,'guidance':1.0,'seed':9301,'return_media':'link'})
   images=response.get('images') or []
   if len(images)!=1:raise JobError('Expected one image from Studio')
   url=images[0].get('url') or images[0].get('download_url')
   parsed=urllib.parse.urlsplit(url or '')
   if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port!=8888:raise JobError('Unexpected Studio image URL; refusing nonlocal transfer')
   request=urllib.request.Request(url,headers={'Authorization':'Bearer '+key})
   with studio.opener.open(request,timeout=120) as server:content=server.read()
   tmp=root/'cards'/'.title-bg.partial.png';tmp.write_bytes(content)
   from PIL import Image
   with Image.open(tmp) as image:image.verify()
   tmp.rename(bg);print('title background:',bg)
  finally:
   try:call('unload_model',{'kind':'image'})
   except Exception:pass
 except Exception as e:
  print('WARNING: title background not generated ('+str(e).replace(key,'<redacted>') if "key" in dir() else 'WARNING: title background not generated ('+str(e)+'); title cards fall back to a solid background.')
 print(f"Show '{slug}' created at {root}")
 print('Next: create the named cast (tools/create_character.py --create ... --add-to-show '+slug+'), then tools/make_series.py new-episode --show '+slug+' --number 1 --brief "<episode 1 brief from arc.md>".')

def new_episode(a):
 show=REG.load_show(SERIES,a.show);cast=REG.load_cast(SERIES,show)
 root=SERIES/a.show;log=root/'writer.jsonl'
 if (SERIES/a.show/'episodes').is_dir():
  for d in (SERIES/a.show/'episodes').glob('*'):
   if d.is_dir() and d.name.split('-',1)[0]==f'{a.number:02d}':raise JobError(f'Episode {a.number} already exists: {d}')
 previous=S.last_continuity(SERIES,a.show,a.number)
 if a.number>1 and not Path(previous.get('final_frame') or '').is_file():
  raise JobError(f"Episode {a.number} needs continuity.json with a final frame from episode {a.number-1}; render episode {a.number-1} first.")
 duration=a.duration or 90
 arc_md=(root/'arc.md').read_text(encoding='utf8') if (root/'arc.md').is_file() else ''
 script=W.draft_script(show,cast,arc_md,previous,a.brief,duration,log)
 episode=W.storyboard(show,cast,script,log,number=a.number,target_seconds=duration)
 episode['id']=f"{a.number:02d}-{S.slugify(episode['title'])}"
 for shot in episode['shots']:
  shot['narration']=' '.join(l['text'] for l in shot['dialogue'])
  shot['character']=' and '.join(cast[slug].get('name',slug) for slug in shot['characters'])
  shot.setdefault('continuation_boundaries_seconds',[])
 directory=SERIES/a.show/'episodes'/episode['id']
 if directory.exists():raise JobError('Episode directory exists: '+str(directory))
 directory.mkdir(parents=True)
 P.atomic(directory/'episode.json',episode)
 REG.load_episode(SERIES,a.show,episode['id'])
 print(f"Episode draft written: {directory/'episode.json'}")
 print('Ends:',episode['ending_state'])
 print('Hook:',episode['next_hook'])
 print('Owner: review and edit episode.json freely before the first render; it is revalidated on every resume.')

def run(a):
 job=S.create_episode(SERIES,a.show,a.episode,{'seed':a.seed} if a.seed is not None else {})
 if a.queue:
  from local_film.queue import FilmQueue
  FilmQueue().enqueue(job,'run')
  print('Queued job:',job,'- a running server picks it up.')
 else:
  print('Rendering job:',job)
  P.run(job)

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 sub=ap.add_subparsers(dest='command',required=True)
 n=sub.add_parser('new-show');n.add_argument('--id');n.add_argument('--title',required=True);n.add_argument('--logline',required=True);n.add_argument('--brief',required=True);n.add_argument('--style',required=True);n.add_argument('--episodes',type=int,default=3)
 e=sub.add_parser('new-episode');e.add_argument('--show',required=True);e.add_argument('--number',type=int,required=True);e.add_argument('--brief',required=True);e.add_argument('--duration',type=float)
 r=sub.add_parser('run');r.add_argument('--show',required=True);r.add_argument('--episode',required=True);r.add_argument('--seed',type=int);r.add_argument('--queue',action='store_true')
 a=ap.parse_args()
 try:
  {'new-show':new_show,'new-episode':new_episode,'run':run}[a.command](a)
 except JobError as x:
  print('ERROR:',x,file=sys.stderr);sys.exit(1)

if __name__=='__main__':main()
