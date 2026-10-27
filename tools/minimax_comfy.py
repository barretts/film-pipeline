"""Submit or inspect a local MiniMax H3 image-to-video test in ComfyUI."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'comfy-local'
STATE = BASE / 'minimax-test.json'
SOURCE = ROOT / 'stills' / 'reels' / 'full-motion' / '01.png'
OPENER = build_opener(ProxyHandler({}))
ADDRESS = 'http://127.0.0.1:8191'


def api(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(ADDRESS + path, data=body, headers={'Content-Type': 'application/json'})
    with OPENER.open(request, timeout=60) as response:
        return json.load(response)


def graph(quality=False, ident='01', continuation=False):
    prompts = {
        '01': 'The adult woman gently turns the pocket watch in her hands, looks down at its face, then slowly lifts her eyes toward the camera. Her fingers, wrist, shoulders and head move naturally; her hair sways softly. The warm bedside lamp flickers subtly. Hand-drawn anime style, consistent original character and clothing, static camera.',
        '02': 'An adult woman in a hand-drawn animated story gently raises her lantern and turns toward the old wooden door. Her arm, shoulders, head and hair move naturally; she glances back toward the camera with a curious expression. Keep her face, hands, lantern and green coat consistent. Warm cinematic lighting, static camera.',
        '03': 'An adult woman in expressive stylized 3D animation approaches the mirror, raises her hand toward her reflection, then turns to the camera with a curious expression. Her hand, arm, shoulders and head move naturally, and her curly hair sways subtly. Keep her face, hands and purple jacket consistent. Cinematic lighting, static camera.',
    }
    prompt = prompts[ident]
    if continuation:
        prompt = {
            '01': 'The adult anime woman gently lifts the pocket watch, turns it in her fingers and looks toward the camera. She shifts her shoulders, gestures naturally with her free hand and breathes softly. Keep the same face, clothing, room and watch, steady camera, hand-drawn anime style.',
            '02': 'The adult woman in hand-drawn animation gently opens the wooden door while holding the lantern, turns her head and looks back toward the camera. Her shoulders, arm and hair move naturally. Keep her face, green coat and lantern consistent, static camera.',
            '03': 'The adult woman in stylized 3D animation gently lowers her hand from the mirror and turns toward the camera. She gestures expressively, moving her shoulders and head, her curly hair swaying softly. Keep her face, purple jacket and the mirror consistent, static camera.',
        }[ident]
    def node(kind, **inputs):
        return {'class_type': kind, 'inputs': inputs}
    return {
        '1': node('UNETLoader', unet_name='minimax_h3_fl2va_pruned_fp8_scaled.safetensors', weight_dtype='default'),
        '2': node('CLIPLoader', clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors', type='minimax', device='default'),
        '3': node('VAELoader', vae_name='minimax_h3_video_vae_fp16.safetensors'),
        '4': node('VAELoader', vae_name='minimax_h3_audio_vae_fp32.safetensors'),
        '5': node('LoadImage', image=(f'minimax-continuation-{ident}.png' if continuation else (f'minimax-character-{ident}.png' if ident != '01' else 'minimax-test-anime.png'))),
        '6': node('MiniMaxH3ImageToVideo', clip=['2', 0], vae=['3', 0], first_frame=['5', 0],
                  prompt=prompt, width=704 if quality else 512, height=1280 if quality else 896,
                  length=124 if quality else 73),
        '7': node('LoraLoaderModelOnly', model=['1', 0],
                  lora_name='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', strength_model=1.0),
        '8': node('MiniMaxH3SigmaShift', model=['7', 0], shift_video=12.0, shift_audio=3.0),
        '9': node('BasicScheduler', model=['8', 0], scheduler='simple', steps=8, denoise=1.0),
        '10': node('BasicGuider', model=['8', 0], conditioning=['6', 0]),
        '11': node('KSamplerSelect', sampler_name='res_multistep'),
        '12': node('RandomNoise', noise_seed=2801),
        '13': node('SamplerCustomAdvanced', noise=['12', 0], guider=['10', 0], sampler=['11', 0],
                   sigmas=['9', 0], latent_image=['6', 1]),
        '14': node('VAEDecode', samples=['13', 0], vae=['3', 0]),
        '15': node('VAEDecodeAudio', samples=['13', 0], vae=['4', 0]),
        '16': node('CreateVideo', images=['14', 0], audio=['15', 0], fps=24.0),
        '17': node('SaveVideo', video=['16', 0], filename_prefix=(f'minimax-production/{ident}-continuation' if continuation else (f'minimax-production/{ident}-shot' if ident != '01' else ('minimax-comparison/anime-hd' if quality else 'minimax-comparison/anime'))), format='auto', codec='auto'),
    }


def speech_graph():
    """Animate the existing anime character using the actual narration as conditioning."""
    result = graph(quality=True, ident='01')
    result['6']['inputs']['prompt'] += (
        ' She speaks the supplied voice recording naturally with precise lip movements, '
        'while keeping her gestures and the hand-drawn anime character consistent.'
    )
    result['18'] = {'class_type': 'LoadAudio', 'inputs': {'audio': 'minimax-01-narration.wav'}}
    result['19'] = {'class_type': 'LCH3AudioSync', 'inputs': {
        'latent': ['6', 1], 'positive': ['6', 0], 'audio_vae': ['4', 0],
        'audio': ['18', 0], 'start_seconds': 0.0, 'when_short': 'silence',
    }}
    result['10']['inputs']['conditioning'] = ['19', 3]
    result['13']['inputs']['latent_image'] = ['19', 0]
    result['16']['inputs']['audio'] = ['19', 1]
    result['17']['inputs']['filename_prefix'] = 'minimax-audio-test/anime-01'
    result.pop('15')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('submit', 'status', 'submit-hd', 'status-hd', 'submit-02', 'status-02', 'submit-03', 'status-03', 'submit-cont-01', 'status-cont-01', 'submit-cont-02', 'status-cont-02', 'submit-cont-03', 'status-cont-03', 'submit-audio-01', 'status-audio-01'))
    args = parser.parse_args()
    continuation = '-cont-' in args.action
    speech = '-audio-' in args.action
    ident = args.action.rsplit('-', 1)[-1] if args.action.endswith(('-01', '-02', '-03')) else '01'
    quality = args.action.endswith('-hd') or ident != '01' or continuation or speech
    state_file = BASE / ('minimax-01-audio-test.json' if speech else (f'minimax-{ident}-continuation.json' if continuation else (f'minimax-{ident}-production.json' if ident != '01' else ('minimax-hd-test.json' if quality else 'minimax-test.json'))))
    if args.action.startswith('submit'):
        if state_file.exists():
            raise RuntimeError(f'Existing state {state_file}; inspect it rather than resubmitting')
        (BASE / 'input').mkdir(parents=True, exist_ok=True)
        if continuation:
            source = BASE / 'output' / ('minimax-comparison/anime-hd_00001_.mp4' if ident == '01' else f'minimax-production/{ident}-shot_00001_.mp4')
            if not source.is_file():
                raise FileNotFoundError(f'Previous motion shot missing: {source}')
            target = BASE / 'input' / f'minimax-continuation-{ident}.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(source), '-vf', r'select=eq(n\,123)',
                            '-vsync', '0', '-frames:v', '1', '-n', str(target)], check=True)
            if not target.is_file():
                raise RuntimeError('Could not extract frame 123 from the first shot')
        else:
            source = SOURCE if ident == '01' else ROOT / 'stills' / 'reels' / 'full-motion' / f'{ident}.png'
            shutil.copyfile(source, BASE / 'input' / (f'minimax-character-{ident}.png' if ident != '01' else 'minimax-test-anime.png'))
        if speech:
            shutil.copyfile(ROOT / 'audio' / 'reels' / '01-paced.wav', BASE / 'input' / 'minimax-01-narration.wav')
        # Write intent first: an interrupted or ambiguous submit must not be retried blindly.
        state = {'phase': 'submitting', 'created': time.time(), 'graph': speech_graph() if speech else graph(quality, ident, continuation)}
        state_file.write_text(json.dumps(state, indent=2), encoding='utf8')
        result = api('/prompt', {'prompt': state['graph'], 'client_id': 'film-pipeline-minimax-test'})
        state.update(phase='submitted', prompt_id=result['prompt_id'], response=result)
        state_file.write_text(json.dumps(state, indent=2), encoding='utf8')
        print(json.dumps(result))
    else:
        state = json.loads(state_file.read_text(encoding='utf8'))
        if not state.get('prompt_id'):
            raise RuntimeError('Submission outcome unknown; inspect ComfyUI queue before retrying')
        result = api('/history/' + state['prompt_id'])
        print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, HTTPError, subprocess.CalledProcessError) as exc:
        print(f'MiniMax test error: {exc}', file=sys.stderr)
        sys.exit(1)
