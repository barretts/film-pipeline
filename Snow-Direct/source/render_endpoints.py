from pathlib import Path
import runpy,time,concurrent.futures
from PIL import Image,ImageOps,ImageDraw
root=Path.cwd()
out=root/'Snow-Direct/keyframes/seven-shots'
lib=runpy.run_path(str(root/'TakeFive/output/openrouter/seedance-mini-480p-one-pass/run.py'))
router=lib['OpenRouter'](lib['KEYFILE'])
prompts=["Kate reads her log. At 1.2s her own warning comes through the radio. She stops writing, listens silently, then raises her eyes and chin toward James. James remains standing.","Kate looks up, glances toward James and says at 1.7s: That was my voice. Small hand gesture and gentle camera push.","Three distinct knocks from outside make the hanging 07 tag jump three times. Closed hatch, stationary lever, no people.","James says at 1.8s: Someone’s out there. He pivots and starts walking to the hatch, still moving at the cut. Camera follows.","Already walking, James reaches for the orange handle, hesitates, grips it, depresses it and pulls the hatch inward, stepping aside to reveal whiteout.","James has disappeared across the cut. Kate alone scans the open doorway and turns back to the desk. Snow blows outside.","Kate leans toward the microphone, presses the switch and warns: James. Don’t open the door. Hold close on Kate."]
assets={}
board=Image.new('RGB',(768,1680));draw=ImageDraw.Draw(board)
for i in range(7):
 for j,n in enumerate((120*i+1,120*i+120)):
  p=out/f'{n:04}.jpg';im=ImageOps.fit(Image.open(p.with_suffix('.png')).convert('RGB'),(1280,720));im.save(p,quality=95);assets[p.name]=p
  board.paste(im.resize((384,216)),(384*j,i*240+24));draw.text((384*j+5,i*240+5),f'Shot {i+1}   Frame {n}',fill='white')
board.save(out/'keyframes.jpg')
def render(i):
 f=out/f'shot{i+1:02}';f.mkdir(exist_ok=True);p=f/'job.json'
 if (f/'edit.mp4').exists():return
 names=[f'{120*i+1:04}.jpg',f'{120*i+120:04}.jpg']
 body=dict(model='alibaba/wan-3.0',duration=5,resolution='720p',aspect_ratio='16:9',prompt='One continuous cinematic live-action take. Match the endpoint photographs precisely, maintain faces, wardrobe, spatial continuity, natural momentum. '+prompts[i])
 lib['save'](f/'inputs.json',{**body,'frames':names})
 if not p.exists():
  body['frame_images']=[dict(type='image_url',frame_type=k,image_url={'url':origin+n}) for k,n in zip(('first_frame','last_frame'),names)]
  (f/'submitted').open('x').close()
  try:r=router.json('/videos',body)
  except lib['RouterError'] as e:
   if e.code in (400,401,402,422,429):(f/'submitted').unlink()
   raise
  lib['save'](p,lib['job_fields'](r))
 r=lib['read'](p);ep='/videos/'+r['id']
 while r['status'] not in ('completed','succeeded'):
  if r['status'] in ('failed','cancelled','expired'):raise RuntimeError(str(r))
  time.sleep(8);r.update(lib['job_fields'](lib['get_status'](router,ep)));lib['save'](p,r)
 router.download(ep+'/content?index=0',f/'original.mp4');lib['edit_to_timeline'](f/'original.mp4',f/'edit.mp4',5,lib['probe'](f/'original.mp4'));print('finished',i+1,flush=True)
with lib['serve_inputs'](assets) as origin:
 render(0)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(render,range(1,7)))
lst=out/'cuts.txt';lst.write_text(''.join(f"file 'shot{i:02}/edit.mp4'\n" for i in range(1,8)))
lib['ffmpeg']('-f','concat','-safe',0,'-i',lst,'-i',root/'Snow-Direct/assets/radio-drama.wav','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-t',35,'-movflags','+faststart',out/'Snow.mp4')
print(lib['probe'](out/'Snow.mp4')['format']['duration'])


