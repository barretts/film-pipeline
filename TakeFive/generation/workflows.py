"""Local ComfyUI API graphs for recurring cast stills and guided, audio-conditioned LTX takes."""
CKPT = "ltx-2.3-22b-distilled-fp8.safetensors"
GEMMA = "gemma_3_12B_it_fp8_scaled.safetensors"
UNION = "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
LOOK_ORDER = ("employee", "manager", "arrival", "departure", "street")
REFERENCES = {"employee": (), "manager": (), "arrival": ("employee", "manager"),
              "departure": ("employee", "manager", "arrival"), "street": ("employee", "arrival")}


class Graph:
    def __init__(self):
        self.nodes = {}

    def add(self, kind, **inputs):
        ident = str(len(self.nodes) + 1)
        self.nodes[ident] = {"class_type": kind, "inputs": inputs}
        return [ident, 0]


def slot(node, index):
    return [node[0], index]


def flux_still(g, model, clip, vae, views, instructions, seed, width, height):
    pos = g.add("CLIPTextEncode", text=instructions, clip=clip)
    neg = g.add("ConditioningZeroOut", conditioning=pos)
    for view in views:
        latent = g.add("VAEEncode", pixels=view, vae=vae)
        pos = g.add("ReferenceLatent", conditioning=pos, latent=latent)
        neg = g.add("ReferenceLatent", conditioning=neg, latent=latent)
    noise = g.add("RandomNoise", noise_seed=seed)
    sampler = g.add("KSamplerSelect", sampler_name="euler")
    sigmas = g.add("Flux2Scheduler", steps=4, width=width, height=height)
    blank = g.add("EmptyFlux2LatentImage", width=width, height=height, batch_size=1)
    guider = g.add("CFGGuider", model=model, positive=pos, negative=neg, cfg=1.)
    sample = g.add("SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=blank)
    return g.add("VAEDecode", samples=sample, vae=vae)


def build_graph(job, name, saved_looks=(), only_look=False):
    g = Graph()
    cfg = job["direction"]
    cast = job["cast"]
    results, references, flux = {}, {}, {}
    def look(shot):
        if shot in references:
            return references[shot]
        if shot in saved_looks:
            out = g.add("LoadImage", image=f"look-{shot}.png")
        else:
            if not flux:
                flux["model"] = g.add("UNETLoader", unet_name="flux-2-klein-4b-fp8.safetensors", weight_dtype="default")
                flux["clip"] = g.add("CLIPLoader", clip_name="qwen_3_4b.safetensors", type="flux2", device="default")
                flux["vae"] = g.add("VAELoader", vae_name="flux2-vae.safetensors")
            w, h = cfg["look_width"], cfg["look_width"] * 9 // 16
            opening = cfg.get("opening_frames", {}).get(shot, {})
            views = [g.add("LoadImage", image=f"layout-{shot}.png")]
            for ref in opening.get("references", REFERENCES[shot]):
                if ref not in LOOK_ORDER[:LOOK_ORDER.index(shot)]:
                    raise ValueError(f"The reference for {shot} must be an earlier cast or location image: {ref}")
                view = look(ref)
                if opening and ref in cfg.get("reference_crops", {}):
                    x, y, width, height = cfg["reference_crops"][ref]
                    if not (0 <= x < x+width <= 1 and 0 <= y < y+height <= 1):
                        raise ValueError(f"The reference crop is outside the {ref} image.")
                    view = g.add("ImageCrop", image=view, x=round(x*w), y=round(y*h),
                                 width=round(width*w), height=round(height*h))
                views.append(view)
            people = ("employee","manager") if shot in ("arrival","departure") else (("employee",) if shot=="street" else (shot,))
            people_text = " ".join(f"{cfg[p]} The {p}'s outer garment is {cast[p]['coat']}." for p in people)
            instructions = (f"{cfg['style']} {cfg['setting']} The street door is {job['door']}. {people_text} "
                            "Recreate the first reference as a live-action photograph. Match its camera angle, "
                            "positions, gaze, doorway and wardrobe colors. Give figures realistic human faces, "
                            "hands and body proportions. Additional references establish the cast and the location. "
                            "Match their features, clothes and materials exactly.")
            if opening:
                instructions = (f"{opening['description']} {cfg['style']} {people_text} "
                                "Use image one as the entire camera frame. Preserve its framing, eyelines, "
                                "door position and subject sizes. The small detail references "
                                "identify people and materials already in this scene.")
            out = flux_still(g, flux["model"], flux["clip"], flux["vae"], views, instructions,
                             cfg["seed"] + LOOK_ORDER.index(shot), w, h)
            saved = g.add("SaveImage", images=out, filename_prefix="looks/"+shot)
            results[saved[0]] = ("look", shot)
        references[shot] = out
        return out

    first = look(name)
    if only_look:
        return g.nodes, results
    target = job["shots"][name]
    positive = f"{cfg['style']} {cfg['shots'][name]} {target['performance']}"
    saved = motion_graph(g, positive, "Cartoon rendering, plastic skin, rubber limbs, broken glasses or drifting faces.",
                         cfg["camera_width"], cfg["camera_height"], job["fps"], target["guide_frames"],
                         f"edges-{name}.mp4", cfg["guide_strength"], f"voice-{name}.wav",
                         cfg["seed"]+100+list(job["shots"]).index(name), cfg["steps"], "takes/"+name, opening=first)
    results[saved[0]] = ("picture", name)
    return g.nodes, results


def motion_graph(g, positive, negative, width, height, fps, length, guide_file, strength, audio_file,
                 seed, steps, prefix, *, opening=None, keyframes=()):
    """Condition one uninterrupted latent take on a movie and optional (frame, PNG, weight) guides."""
    ckpt = g.add("CheckpointLoaderSimple", ckpt_name=CKPT)
    vae = slot(ckpt, 2)
    clip = g.add("LTXAVTextEncoderLoader", text_encoder=GEMMA, ckpt_name=CKPT, device="default")
    model = g.add("LoraLoaderModelOnly", model=ckpt, lora_name=UNION, strength_model=1.)
    params = g.add("GetICLoRAParameters", iclora_model=model)
    pos = g.add("CLIPTextEncode", text=positive, clip=clip)
    neg = g.add("CLIPTextEncode", text=negative, clip=clip)
    cond = g.add("LTXVConditioning", positive=pos, negative=neg, frame_rate=fps)
    latent = g.add("EmptyLTXVLatentVideo", width=width, height=height, length=length, batch_size=1)
    if opening is not None:
        latent = g.add("LTXVImgToVideoInplace", vae=vae, image=opening, latent=latent, strength=1., bypass=False)
    video = g.add("LoadVideo", file=guide_file)
    frames = g.add("GetVideoComponents", video=video)
    guide = g.add("LTXVAddGuide", positive=cond, negative=slot(cond,1), vae=vae, latent=latent,
                  image=frames, frame_idx=0, strength=strength, iclora_parameters=params)
    for frame, filename, weight in keyframes:
        still = g.add("LoadImage", image=filename)
        guide = g.add("LTXVAddGuide", positive=guide, negative=slot(guide,1), vae=vae, latent=slot(guide,2),
                      image=still, frame_idx=frame, strength=weight)
    sound = g.add("LoadAudio", audio=audio_file)
    audio_vae = g.add("LTXVAudioVAELoader", ckpt_name=CKPT)
    encoded = g.add("LTXVAudioVAEEncode", audio=sound, audio_vae=audio_vae)
    silence_mask = g.add("SolidMask", value=0., width=64, height=64)
    frozen = g.add("SetLatentNoiseMask", samples=encoded, mask=silence_mask)
    joint = g.add("LTXVConcatAVLatent", video_latent=slot(guide,2), audio_latent=frozen)
    sample = g.add("KSampler", model=model, seed=seed, steps=steps,
                   cfg=1., sampler_name="euler_ancestral", scheduler="linear_quadratic", positive=guide,
                   negative=slot(guide,1), latent_image=joint, denoise=1.)
    separate = g.add("LTXVSeparateAVLatent", av_latent=sample)
    cleaned = g.add("LTXVCropGuides", positive=guide, negative=slot(guide,1), latent=separate)
    image = g.add("VAEDecodeTiled", samples=slot(cleaned,2), vae=vae, tile_size=384, overlap=64,
                  temporal_size=32, temporal_overlap=8)
    film = g.add("CreateVideo", images=image, fps=fps)
    return g.add("SaveVideo", video=film, filename_prefix=prefix, format="mp4", **{"format.codec":"auto"})
