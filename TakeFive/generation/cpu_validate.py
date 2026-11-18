"""Ask ComfyUI to validate real graphs in CPU mode. No prompt is submitted for execution."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

def main():
    engine, job, models, scratch = map(lambda p: Path(p).resolve(), sys.argv[1:])
    os.environ.update(CUDA_VISIBLE_DEVICES="-1", HIP_VISIBLE_DEVICES="-1", ROCR_VISIBLE_DEVICES="-1",
                      HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    (scratch/"input").mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(engine))
    sys.argv = [str(engine/"main.py"),"--cpu","--offline","--disable-xformers","--disable-dynamic-vram",
                "--disable-all-custom-nodes","--base-directory",str(scratch)]
    import comfy.options
    comfy.options.enable_args_parsing()
    import folder_paths, nodes, execution, torch
    from comfy import model_management
    from comfy import model_detection
    from comfy.text_encoders.flux import KleinTokenizer
    from comfy.text_encoders.lt import LTXAVGemmaTokenizer
    from safetensors import safe_open
    from workflows import CKPT,GEMMA
    validation_inputs=scratch/"input"
    for src in (job/"input").iterdir():
        dest=validation_inputs/src.name
        if not dest.is_file():
            shutil.copyfile(src,dest)
    folder_paths.set_input_directory(str(validation_inputs))
    for child in models.iterdir():
        if child.is_dir():
            folder_paths.add_model_folder_path(child.name,str(child),is_default=True)
    assert model_management.get_torch_device().type == "cpu" and not torch.cuda.is_initialized()
    # Inspect shapes on the meta device. Only the small SentencePiece vocabulary is read into RAM.
    with safe_open(str(models/"checkpoints"/CKPT),framework="pt",device="cpu") as weights:
        prefix="model.diffusion_model."
        shapes={k:torch.empty(weights.get_slice(k).get_shape(),device="meta") for k in weights.keys() if k.startswith(prefix)}
        detected=model_detection.detect_unet_config(shapes,prefix,metadata=weights.metadata())
    if not detected or detected["image_model"]!="ltxav":
        raise ValueError("This ComfyUI version did not recognize the LTX audio-video checkpoint.")
    with safe_open(str(models/"text_encoders"/GEMMA),framework="pt",device="cpu") as weights:
        gemma=LTXAVGemmaTokenizer(tokenizer_data={"spiece_model":weights.get_tensor("spiece_model")})
    klein=KleinTokenizer()
    words={}
    for label,tokenizer in (("ltx",gemma),("flux",klein)):
        test=tokenizer.tokenize_with_weights("The manager listens, then gives the employee her answer.")
        ids={i[0] for stream in test.values() for group in stream for i in group}
        if len(ids)<5:
            raise ValueError(f"The offline {label} tokenizer could not encode the sample dialogue direction.")
        words[label]=len(ids)
    async def validate():
        from app.assets.manager import default_asset_manager
        from server import PromptServer
        # Register stock nodes with their real application context, without opening a port.
        PromptServer(asyncio.get_running_loop(), default_asset_manager())
        await nodes.init_extra_nodes(init_custom_nodes=False,init_api_nodes=False)
        from comfy_extras.nodes_audio import LoadAudio
        from workflows import build_graph
        plan=json.loads((job/"plan.json").read_text(encoding="utf-8"))
        stems = {}
        for name, shot in plan["shots"].items():
            audio = LoadAudio.execute(f"voice-{name}.wav")[0]
            waveform, rate = audio["waveform"], audio["sample_rate"]
            samples = shot["guide_frames"] * plan["rate"] // plan["fps"]
            if rate != plan["rate"] or tuple(waveform.shape) != (1, 2, samples):
                raise ValueError(f"ComfyUI decoded the wrong audio length or channel count for {name}.")
            onset = shot["voice_onset_seconds"]
            quiet_samples = samples if onset is None else round(onset * rate)
            if waveform[..., :quiet_samples].count_nonzero() or (onset is not None and not waveform.count_nonzero()):
                raise ValueError(f"The isolated {name} dialogue does not match its planned silence.")
            stems[name] = {"rate": rate, "channels": 2, "samples": samples, "leading_silence_checked": quiet_samples}
        # Only the downstream file-loader branch needs a stand-in. These copies stay
        # in validation/input and cannot become generated stills or accepted takes.
        for shot in plan["shots"]:
            shutil.copyfile(job/"input"/f"layout-{shot}.png",validation_inputs/f"look-{shot}.png")
        validated = {}
        for graph_file in sorted((job/"graphs").glob("*.json")):
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            name=graph_file.stem
            look,_=build_graph(plan,name,only_look=True)
            video,_=build_graph(plan,name,plan["shots"])
            validated[name]={}
            for branch,nodeset in (("combined",graph),("look",look),("video_with_saved_look",video)):
                ok,error,outputs,node_errors=await execution.validate_prompt("offline-check",nodeset,None)
                if not ok or node_errors:
                    raise ValueError(f"{name}/{branch}: {error} {node_errors}")
                validated[name][branch]={"nodes":len(nodeset),"outputs":sorted(outputs)}
        return validated, stems
    try:
        graphs, stems=asyncio.run(validate())
    finally:
        for fixture in validation_inputs.glob("look-*.png"):
            fixture.unlink()
    report = {"graphs":graphs,"device":"cpu","cuda_initialized":torch.cuda.is_initialized(),
              "decoded_stems":stems,
              "model_detected":detected["image_model"],"tokenizer_distinct_ids":words,
              "saved_look_loader_test_input":"staged stills in validation/input only",
              "inference_jobs_submitted":0}
    assert not report["cuda_initialized"]
    (scratch/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
if __name__=="__main__":
    main()
