"""Series mode: episode requests, per-character voices, H3 prompts, cards, continuity."""
import hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
from .pipeline import(JobError,ROOT,RUNTIME,BASE,FPS,FRAMES,atomic,load,duration,run_cmd,segment_schedule,check_cancel,extract_tail,log,save)
from . import characters as registry
from . import writer

SERIES=ROOT/'series'
GAP_SECONDS=0.35

def slugify(value):return re.sub(r'-{2,}','-',re.sub(r'[^a-z0-9]+','-',str(value).lower())).strip('-')

def _load_show(root,show):return registry.load_show(root,show) if isinstance(show,str) else show
def _load_episode(root,show,episode):return registry.load_episode(root,show['id'] if isinstance(show,dict) else show,episode) if isinstance(episode,(int,str)) else episode

def create_episode(series_root,show,episode,overrides=None):
 root=Path(series_root);s=_load_show(root,show);e=_load_episode(root,s,episode)
 for k in (overrides or {}):
  if k not in ('seed','seed_mode','duration_seconds','segment_frames','continuation_overlap_frames','speech_before_seconds','speech_after_seconds'):raise JobError('Unsupported series override: '+k)
 req={'kind':'series','show':s['id'],'episode':e['id'],'series_root':str(root.resolve()),'show_path':str(Path(s['_dir']).resolve()),'episode_path':str(Path(e['_dir']).resolve()),
  'style':s['style'],'width':s['width'],'height':s['height'],'fps':s['fps'],'duration_seconds':e['target_seconds'],
  'aspect':'landscape' if s['width']>s['height'] else 'portrait','seed_mode':'random','segment_frames':FRAMES,'references':[],
  'brief':f"{s['title']} - {e['title']}: {e.get('synopsis','')}".strip()[:4000]}
 req.update(overrides or {})
 from .pipeline import create
 return create(req)

def _and(items):return items[0] if len(items)==1 else ', '.join(items[:-1])+' and '+items[-1]

def _dialogue(shot,characters):
 order=[]
 for line in shot['dialogue']:
  if line['character'] not in order:order.append(line['character'])
 out=[]
 for line in shot['dialogue']:
  name=characters[line['character']].get('name',line['character'])
  out.append(f"{name} (S{order.index(line['character'])+1}) says <d>[English] {line['text'].strip()} </d>")
 return out

def _six_sections(show,characters,slugs,detailed):
 defs='\n'.join(f"<Subject {i+1}> is the {characters[slug].get('name',slug)} whose appearance comes from <Picture {i+1}>: {characters[slug]['description']} {characters[slug]['appearance']}" for i,slug in enumerate(slugs))
 kept='\n'.join(f"<Subject {i+1}> (<Picture {i+1}>): fully_preserved - the face, hair and clothing of <Subject {i+1}> are retained ({characters[slug]['description']}). Only the person comes from <Picture {i+1}>; not the background." for i,slug in enumerate(slugs))
 subjects=_and([f'<Subject {i+1}>' for i in range(len(slugs))])
 tail='\n\noverall_soundscape: '+str(show.get('soundscape','minimal room tone.'))+'\n\nnon_diegetic_music: '+str(show.get('music','restrained strings bed'))
 return ('subject_definitions:\n'+defs+'\n\nsummary: [reference generation] The target video follows '+subjects+'.'
  +'\n\nretention_analysis:\n'+kept+'\n\ndetailed_description: '+detailed.strip()+tail)

def build_prompts(plan,show,characters,continuity=None):
 for shot in plan['shots']:
  slugs=[slug for slug in show['characters'] if slug in shot['characters']]
  if not slugs:raise JobError(f"{shot['id']}: no cast member present")
  spoken=_dialogue(shot,characters)
  first=f"[Shot 1] {shot['scene']}. {shot['action']} "+' '.join(spoken)
  keep=f"Keep {_and([f'<Subject {i+1}>' for i in range(len(slugs))])} in the same place, same clothing and identical appearance."
  continuation=f"Continue seamlessly from the previous final frame. {shot['continuation_action']} {keep} "+' '.join(spoken)
  shot['series_prompt']=_six_sections(show,characters,slugs,show['style']+'\n\n'+first)+' The characters speak the supplied recordings naturally with precise lip movement.'
  shot['series_continuation']=_six_sections(show,characters,slugs,show['style']+'\n\n'+continuation)+' The characters speak the supplied recordings naturally with precise lip movement.'
  shot['series_refs']=[str(Path(characters[slug]['_dir'])/characters[slug]['portrait']) for slug in slugs[:9]]
 return plan

def _piper_line(exe,model,text,target):
 temp=target.with_name(target.stem+'.partial.wav')
 result=subprocess.run([str(exe),'--model',str(model),'--output_file',str(temp)],input=text+'\n',text=True,encoding='utf8',capture_output=True,timeout=300)
 if result.returncode or not temp.is_file():raise JobError('Piper failed: '+result.stderr[-1000:])
 if duration(temp)<=0.2:raise JobError('Piper produced empty audio')
 os.replace(temp,target);return target

def voice_tracks(plan,characters,job,before=0.0,after=0.0,state=None):
 job=Path(job);exe=RUNTIME/'piper'/'piper'/'piper.exe'
 if not exe.is_file():raise JobError('Piper executable missing; see installation guide')
 owns=state is None
 if owns:state=load(job/'state.json')
 for shot in plan['shots']:
  lines=shot['dialogue']
  for line in lines:
   voice_model=RUNTIME/'models'/characters[line['character']]['voice_model']
   if not voice_model.is_file():raise JobError('Voice model missing for '+line['character']+': '+str(voice_model))
  target=job/'voices'/f"{shot['id']}.wav";target.parent.mkdir(exist_ok=True)
  payload=[[line['character'],line['text']]for line in lines]
  hash_input=json.dumps(payload,ensure_ascii=False) if not before and not after else json.dumps([payload,before,after],ensure_ascii=False)
  text_hash=hashlib.sha256(hash_input.encode('utf8')).hexdigest();known=state.setdefault('voice_text_hashes',{}).get(shot['id'])
  if target.exists() and known!=text_hash:raise JobError('Existing voice does not match current dialogue; create a new job or inspect the interruption')
  if not target.exists():
   start=time.time();parts=[]
   try:
    for index,line in enumerate(lines):
     parts.append(_piper_line(exe,RUNTIME/'models'/characters[line['character']]['voice_model'],line['text'],job/'voices'/f"{shot['id']}-{index:02}.line.wav"))
    merged=target.with_name(target.stem+'.merged.partial.wav')
    if len(parts)==1:shutil.copyfile(parts[0],merged)
    else:
     args=['ffmpeg','-y','-v','error']
     for part in parts:args+=['-i',str(part)]
     graph=''.join(f'[{index}:a]aformat=sample_rates=22050:channel_layouts=mono[a{index}];'for index in range(len(parts)))
     graph+=''.join(f'anullsrc=r=22050:cl=mono:d={GAP_SECONDS:g}[g{index}];'for index in range(len(parts)-1))
     graph+=''.join(f'[a{index}]{f"[g{index}]" if index<len(parts)-1 else ""}'for index in range(len(parts)))+f'concat=n={2*len(parts)-1}:v=0:a=1[cat]'
     args+=['-filter_complex',graph,'-map','[cat]','-c:a','pcm_s16le',str(merged)]
     run_cmd(args)
    if duration(merged)<=0.2:raise JobError('Piper produced empty audio')
    if before or after:
     padded=target.with_name(target.stem+'.padded.partial.wav')
     run_cmd(['ffmpeg','-y','-v','error','-i',merged,'-af',f'adelay={round(before*1000)}:all=1,apad=pad_dur={after}','-c:a','pcm_s16le',padded])
     if duration(padded)+0.03<duration(merged)+before+after:raise JobError('Padded speech is truncated')
     os.replace(padded,target);merged.unlink()
    else:os.replace(merged,target)
   finally:
    for part in parts:part.unlink(missing_ok=True)
   state['voice_text_hashes'][shot['id']]=text_hash;log(state,'voice_ready',shot=shot['id'],seconds=round(time.time()-start,2))
   if owns:atomic(job/'state.json',state);save(job,state)
  shot['voice']=str(target);shot['voice_seconds']=duration(target)
 req=load(job/'request.json');minimum=sum(s['voice_seconds']+0.25 for s in plan['shots']);target=float(req.get('duration_seconds') or 0) or minimum
 if target+0.05<minimum:raise JobError(f'Requested duration {target:.2f}s is shorter than narration ({minimum:.2f}s); increase duration')
 extra=target-minimum
 for s in plan['shots']:
  s['duration_seconds']=s['voice_seconds']+0.25+extra*(s['voice_seconds']+0.25)/minimum
  s['continuation_boundaries_seconds']=[round(part['timeline_start'],3) for part in segment_schedule(s['duration_seconds'],req)[1:]]
 atomic(job/'plan.json',plan)
 if owns:atomic(job/'state.json',state)
 return plan

def _font(size):
 from PIL import ImageFont
 for name in ('arial.ttf','arialbd.ttf','segoeui.ttf'):
  path=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/name
  if path.is_file():return ImageFont.truetype(str(path),size)
 from PIL import ImageFont as F
 return F.load_default(size)

def _card_text(draw,text,width,font,fill):
 words=text.split();lines=[];current=''
 for word in words:
  trial=(current+' '+word).strip()
  if draw.textlength(trial,font=font)<=width or not current:current=trial
  else:lines.append(current);current=word
 if current:lines.append(current)
 return lines

def build_card(job,name,text,background,width,height):
 from PIL import Image,ImageDraw,Image
 card=Path(job)/'cards';card.mkdir(parents=True,exist_ok=True);png=card/f'{name}.png';mp4=card/f'{name}.mp4'
 if mp4.exists():return mp4
 image=None
 if background and Path(background).is_file():
  try:
   image=Image.open(background).convert('RGB')
   scale=max(width/image.width,height/image.height);scaled=image.resize((max(width,round(image.width*scale)),max(height,round(image.height*scale))))
   left=(scaled.width-width)//2;top=(scaled.height-height)//2;image=scaled.crop((left,top,left+width,top+height))
  except Exception:image=None
 if image is None:image=Image.new('RGB',(width,height),(24,32,46))
 draw=ImageDraw.Draw(image);font=_font(max(24,width//18));lines=_card_text(draw,text,width,font,None)
 ascent,descent=font.getmetrics();line_height=ascent+descent+6;block=len(lines)*line_height
 stroke=max(2,width//240)
 for index,line in enumerate(lines):
  y=max(4,(height-block)//2+index*line_height)
  draw.text(((width-draw.textlength(line,font=font))//2,y),line,font=font,fill=(245,247,250),stroke_width=stroke,stroke_fill=(8,12,20))
 image.save(png)
 run_cmd(['ffmpeg','-y','-v','error','-loop','1','-framerate',str(FPS),'-i',png,'-f','lavfi','-t','2','-i','anullsrc=channel_layout=stereo:sample_rate=48000','-c:v','libx264','-pix_fmt','yuv420p','-r',str(FPS),'-c:a','aac','-b:a','192k','-shortest',mp4.with_name(name+'.partial.mp4')])
 os.replace(mp4.with_name(name+'.partial.mp4'),mp4);return mp4

def card_segments(plan,job,req,show,characters,segments):
 job=Path(job);show_dir=Path(show.get('_dir') or (Path(req['series_root'])/req['show']))
 card_one=build_card(job,'title-card',f"{show['title']} — {plan.get('title','')}",show_dir/'cards'/'title-bg.png',req['width'],req['height'])
 hook=str(plan.get('next_hook') or '').strip().split('\n')[0]
 final=Path(plan.get('final_frame') or '')
 background=final if final.is_file() else show_dir/'cards'/'end-bg.png'
 card_two=build_card(job,'end-card',('Next time: '+hook) if hook else f"{show['title']} — end",background if Path(background).is_file() else show_dir/'cards'/'title-bg.png',req['width'],req['height'])
 return [(card_one,2.0)]+list(segments)+[(card_two,2.0)]

def save_continuity(job,episode_path,show_path,ending_state):
 episode_dir=Path(episode_path);show_dir=Path(show_path);episode=load(episode_dir/'episode.json')
 final=episode_dir/'final-frame.png';extract_tail(Path(job)/'review'/'assembled.mp4',final)
 cast=[]
 for shot in episode['shots']:
  for slug in shot['characters']:
   if slug not in cast:cast.append(slug)
 root=show_dir.parent
 cast_refs={slug:str((Path(registry.load_character(root,slug)['_dir'])/registry.load_character(root,slug)['portrait']).resolve()) for slug in cast}
 atomic(episode_dir/'continuity.json',{'number':episode['number'],'ending_state':ending_state,'next_hook':episode.get('next_hook',''),'final_frame':str(final),'cast_refs':cast_refs})
 return episode_dir/'continuity.json'

def last_continuity(series_root,show,number):
 root=Path(series_root);episodes=root/show/'episodes'
 best=None
 for directory in sorted(episodes.glob('*')):
  path=directory/'continuity.json'
  if not path.is_file():continue
  data=load(path)
  if isinstance(data.get('number'),int) and data['number']<number and (best is None or data['number']>best['number']):best=data
 return best or {}
