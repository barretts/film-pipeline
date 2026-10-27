"""Read public Hugging Face metadata; never loads weights or sends a token."""
import json
import urllib.request
for repo in ('unsloth/LTX-2.5-GGUF','unsloth/LTX-2.5-FP8','Lightricks/LTX-2.5'):
    try:
        with urllib.request.urlopen('https://huggingface.co/api/models/'+repo,timeout=20) as response:
            data=json.load(response)
        print(repo, 'gated:', data.get('gated'), 'private:', data.get('private'), 'files:',len(data.get('siblings',[])),flush=True)
        if repo=='unsloth/LTX-2.5-GGUF':
            names={x['rfilename'] for x in data.get('siblings',[])}
            for name in ('text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors','vae/ltx-2.5-video-vae-conv-bf16.safetensors','vae/ltx-2.5-audio-vae-bf16.safetensors','latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors'):
                print('  companion',name,'listed:',name in names,flush=True)
    except Exception as exc:
        print(repo,type(exc).__name__,str(exc),flush=True)
