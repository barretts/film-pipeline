"""Generate appearance frames from the staged cameras and recurring cast in local ComfyUI."""
from io import BytesIO
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid
from PIL import Image
from .finishing import checksum
from .script import digest, dump

ORDER=("employee","manager","arrival","departure","street")


def graph(refs,prompt,seed,width,models):
    nodes={}
    def node(kind,**inputs):
        key=str(len(nodes)+1)
        nodes[key]={"class_type":kind,"inputs":inputs}
        return [key,0]
    model=node("UNETLoader",unet_name=models[0],weight_dtype="default")
    clip=node("CLIPLoader",clip_name=models[1],type="flux2",device="default")
    vae=node("VAELoader",vae_name=models[2])
    positive=node("CLIPTextEncode",text=prompt,clip=clip)
    negative=node("ConditioningZeroOut",conditioning=positive)
    for ref in refs:
        image=node("LoadImage",image=ref)
        latent=node("VAEEncode",pixels=image,vae=vae)
        positive=node("ReferenceLatent",conditioning=positive,latent=latent)
        negative=node("ReferenceLatent",conditioning=negative,latent=latent)
    h=width*9//16
    noise=node("RandomNoise",noise_seed=seed)
    sampler=node("KSamplerSelect",sampler_name="euler")
    sigmas=node("Flux2Scheduler",steps=4,width=width,height=h)
    latent=node("EmptyFlux2LatentImage",width=width,height=h,batch_size=1)
    guider=node("CFGGuider",model=model,positive=positive,negative=negative,cfg=1.0)
    samples=node("SamplerCustomAdvanced",noise=noise,guider=guider,sampler=sampler,sigmas=sigmas,latent_image=latent)
    image=node("VAEDecode",samples=samples,vae=vae)
    save=node("SaveImage",images=image,filename_prefix="TakeFive/look")
    return nodes,save[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def looks(bundle,out,port,width,style,models,seed):
    if width<256 or width>1536 or width%256:
        raise ValueError("Choose a look-frame width divisible by 256, between 256 and 1536.")
    if not 1<=port<=65535:
        raise ValueError("Invalid local ComfyUI port.")
    api=f"http://127.0.0.1:{port}"
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def request(route,payload=None,mime="application/json"):
        if isinstance(payload,dict):
            payload=json.dumps(payload).encode()
        req=urllib.request.Request(api+route,data=payload,headers={"Content-Type":mime} if payload else {})
        with opener.open(req,timeout=60) as response:
            return response.read()
    # Verify these files are actually selectable by this server before queuing a GPU job.
    for kind,field,filename in zip(("UNETLoader","CLIPLoader","VAELoader"),("unet_name","clip_name","vae_name"),models):
        meta=json.loads(request("/object_info/"+kind))
        option=meta[kind]["input"]["required"][field]
        options=option[0] if isinstance(option[0],list) else option[1].get("options",[])
        if filename not in options:
            raise ValueError(f"Local ComfyUI does not list {filename} for {kind}.")
    client=uuid.uuid4().hex
    def upload(path):
        with Image.open(path) as source:
            im=source.convert("RGB").resize((width,width*9//16),Image.Resampling.LANCZOS)
            data=BytesIO()
            im.save(data,format="PNG")
        boundary=uuid.uuid4().hex
        filename=client+"-"+path.name
        head=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
              'Content-Type: image/png\r\n\r\n').encode()
        res=json.loads(request("/upload/image",head+data.getvalue()+f"\r\n--{boundary}--\r\n".encode(),
                               "multipart/form-data; boundary="+boundary))
        return "/".join(s for s in (res.get("subfolder",""),res["name"]) if s)
    scene=json.loads((bundle/"scene.json").read_text(encoding="utf-8"))
    cast=scene["cast"]
    out.mkdir(parents=True,exist_ok=True)
    for i,shot in enumerate(ORDER):
        first=bundle/"stills"/(shot+"-start.png")
        paths=[first]
        if shot not in ("employee","manager"):
            paths.append(out/"employee.png")
            if shot!="street":
                paths.append(out/"manager.png")
        prompt=(style+" Restyle image one, preserving its camera, silhouettes, gaze and the blueprints of the room. "
                f"The employee wears {cast['employee']['coat']}. The manager wears {cast['manager']['coat']}. "
                "Additional images are cast references. Keep their identities and clothing.")
        signature=digest("flux-klein-layout-v1",models,prompt,seed+i,width,[checksum(path) for path in paths])
        still=out/(shot+".png")
        record=out/(shot+".json")
        if still.is_file() and record.is_file():
            previous=json.loads(record.read_text(encoding="utf-8"))
            if previous.get("inputs")==signature and previous.get("image")==checksum(still):
                continue
        nodes,last=graph([upload(p) for p in paths],prompt,seed+i,width,models)
        answer=json.loads(request("/prompt",{"prompt":nodes,"client_id":client}))
        job=answer["prompt_id"]
        deadline=time.monotonic()+7200
        while time.monotonic()<deadline:
            history=json.loads(request("/history/"+job)).get(job)
            if history:
                status=history.get("status",{})
                if status.get("status_str")=="error":
                    raise RuntimeError(f"Local ComfyUI job {job} failed: {status.get('messages',[])[-1:]}")
                images=history.get("outputs",{}).get(last,{}).get("images",[])
                if images:
                    item=images[0]
                    image=request("/view?"+urllib.parse.urlencode({k:item[k] for k in ("filename","subfolder","type")}))
                    with Image.open(BytesIO(image)) as check:
                        check.verify()
                    temp=out/("."+uuid.uuid4().hex+".png")
                    temp.write_bytes(image)
                    os.replace(temp,still)
                    info=out/("."+uuid.uuid4().hex+".json")
                    dump(info,{"inputs":signature,"image":checksum(still)})
                    os.replace(info,record)
                    print("Saved look frame "+shot,flush=True)
                    break
            time.sleep(1)
        else:
            raise TimeoutError(f"Local ComfyUI job {job} is still pending after two hours.")
    (out/"look.json").write_text(json.dumps({"style":style,"seed":seed,"models":models,"width":width},indent=2))
