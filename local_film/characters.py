"""Series registry loading and validation: characters, shows, episodes."""
import json,re
from pathlib import Path
from .pipeline import JobError,RUNTIME

def _load(path,what):
 if not path.is_file():raise JobError(f'{what} not found: {path}')
 try:return json.loads(path.read_text(encoding='utf8'))
 except ValueError as e:raise JobError(f'{what} is not valid JSON: {path}') from e

def _text(obj,key):
 value=obj.get(key)
 if not isinstance(value,str) or not value.strip():raise JobError(f'{key} is required')
 return value.strip()

def _relative(base,ref,what):
 p=Path(str(ref))
 if p.is_absolute():raise JobError(f'{what} must be a path inside the character folder: {ref}')
 path=(base/p).resolve()
 if not str(path).lower().startswith(str(base.resolve()).lower()+'\\')and not str(path).lower().startswith(str(base.resolve()).lower()+'/'):raise JobError(f'{what} escapes the character folder: {ref}')
 return path

def load_character(root,slug):
 base=Path(root)/'characters'/slug;c=_load(base/'character.json','Character definition')
 if c.get('id')!=slug:raise JobError(f"Character id {c.get('id')!r} must equal its folder slug {slug!r}")
 _text(c,'name')
 if len(_text(c,'description'))<20:raise JobError('Character description must be an identity sentence of at least 20 characters')
 _text(c,'appearance')
 voice_model=c.get('voice_model')
 if not isinstance(voice_model,str) or not voice_model or Path(voice_model).name!=voice_model:raise JobError('voice_model must be one file name inside local-runtime/models/')
 if not (RUNTIME/'models'/voice_model).is_file():raise JobError('Character voice model is missing from local-runtime/models/: '+voice_model)
 sample=_relative(base,c.get('voice_sample'),'voice_sample')
 if not sample.is_file():raise JobError('voice_sample does not exist: '+str(sample))
 portrait=_relative(base,c.get('portrait'),'portrait')
 if not portrait.is_file():raise JobError('portrait does not exist: '+str(portrait))
 refs=c.get('ref_images')
 if not isinstance(refs,list) or not 2<=len(refs)<=9:raise JobError('ref_images must list between 2 and 9 relative paths')
 if str(refs[0]).replace('\\','/')!=str(c['portrait']).replace('\\','/'):raise JobError('ref_images must include the master portrait first')
 for ref in refs:
  p=_relative(base,ref,'ref_images entry')
  if not p.is_file():raise JobError('ref_images entry does not exist: '+str(p))
 c['_dir']=str(base)
 return c

def load_show(root,show):
 base=Path(root)/show;s=_load(base/'show.json','Show definition')
 if s.get('id')!=show:raise JobError(f"Show id {s.get('id')!r} must equal its folder slug {show!r}")
 for key in ('title','logline','brief','style','arc_summary'):_text(s,key)
 width=int(s.get('width',1280));height=int(s.get('height',720));fps=int(s.get('fps',24))
 if width%2 or height%2:raise JobError('Show width and height must be even')
 if fps!=24:raise JobError('Show fps must be 24')
 cast=s.get('characters')
 if not isinstance(cast,list) or not cast:raise JobError('Show must name at least one character')
 for slug in cast:load_character(root,slug)
 s.update(width=width,height=height,fps=fps,characters=cast,_dir=str(base))
 return s

def load_episode(root,show,episode):
 s=load_show(root,show);episodes=Path(root)/show/'episodes'
 if isinstance(episode,int)or(isinstance(episode,str)and episode.isdigit()):
  dirs=[d for d in episodes.glob('*') if d.is_dir() and d.name.split('-',1)[0]==f'{int(episode):02d}']
  if len(dirs)!=1:raise JobError(f'No single episode directory matches episode number {episode} under {episodes}')
  base=dirs[0]
 else:
  base=episodes/str(episode)
  if not (base/'episode.json').is_file():
   for d in episodes.glob('*'):
    if d.is_dir() and _load(d/'episode.json','Episode definition').get('id')==str(episode):base=d;break
 e=_load(base/'episode.json','Episode definition')
 if e.get('id')!=base.name:raise JobError(f"Episode id {e.get('id')!r} must equal its folder name {base.name!r}")
 number=e.get('number')
 if type(number)is not int or number<1:raise JobError('Episode number must be an integer of at least 1')
 _text(e,'title')
 target=e.get('target_seconds')
 # 0 means "automatic from the narration minimum"; otherwise a fixed 30-300 s episode length.
 if type(target)not in(int,float)or(target!=0 and not 30<=target<=300):raise JobError('target_seconds must be 0 (automatic) or between 30 and 300')
 shots=e.get('shots')
 if not isinstance(shots,list) or not 1<=len(shots)<=12:raise JobError('Episode must contain 1 to 12 shots')
 ids=[]
 for shot in shots:
  if not isinstance(shot,dict):raise JobError('Each shot must be an object')
  if not re.fullmatch(r'shot-[0-9]{2}',str(shot.get('id'))):raise JobError('Shot ids must be shot-01 through shot-99')
  if shot['id'] in ids:raise JobError('Shot ids must be unique: '+shot['id'])
  ids.append(shot['id'])
  for key in('scene','action','continuation_action','prompt'):_text(shot,key)
  cast=shot.get('characters')
  if not isinstance(cast,list) or not cast:raise JobError(f"{shot['id']}: at least one character is required")
  if not set(cast)<=set(s['characters']):raise JobError(f"{shot['id']}: characters outside the show cast: {sorted(set(cast)-set(s['characters']))}")
  speakers=shot.get('speakers')
  if not isinstance(speakers,list) or not set(speakers)<=set(cast):raise JobError(f"{shot['id']}: speakers must be a subset of the shot characters")
  dialogue=shot.get('dialogue')
  if not isinstance(dialogue,list):raise JobError(f"{shot['id']}: dialogue must be a list")
  if not dialogue:dialogue=[{'character':s['characters'][0],'text':'<narration>'}]
  for line in dialogue:
   if not isinstance(line,dict) or line.get('character')not in cast or not isinstance(line.get('text'),str) or not line['text'].strip():raise JobError(f"{shot['id']}: each dialogue line needs a character from the shot and text")
  shot['dialogue']=dialogue
 e['_dir']=str(base);e['_show']=show
 return e

def load_cast(root,show):
 return {slug:load_character(root,slug)for slug in show['characters']}
