#!/usr/bin/env python3
"""Experimental CPU-only tracked mouth animation for a single moving 2D shot.

This produces an editable proof, not a quality or lip-sync certification. Use a
character-specific transparent PNG mouth set and review every rendered shot.
"""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / 'tools' / 'MuseTalk'
RHUBARB = ROOT / 'venvs' / 'rhubarb' / 'rhubarb.exe'
FPS = 25
SYMBOLS = set('ABCDEFGHX')


class AnimationError(Exception):
    pass


def command(args, **kwargs):
    try:
        return subprocess.run(args, check=True, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AnimationError(f'Command failed ({args[0]}): {exc}') from exc


def probe(path):
    result = command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                     capture_output=True, text=True, encoding='utf8', errors='replace')
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise AnimationError('ffprobe returned invalid JSON') from exc


def duration(value, description):
    try:
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError()
        return value
    except (TypeError, ValueError) as exc:
        raise AnimationError(f'Cannot verify {description} duration') from exc


def parse_crop(value):
    try:
        parts = tuple(int(x.strip()) for x in value.split(','))
    except ValueError as exc:
        raise argparse.ArgumentTypeError('crop must be x,y,width,height in pixels') from exc
    if len(parts) != 4 or parts[0] < 0 or parts[1] < 0 or parts[2] < 64 or parts[2] != parts[3]:
        raise argparse.ArgumentTypeError('crop must be a square of at least 64 pixels within the video')
    return parts


def validate_cues(data, seconds):
    """Reject unknown, missing, overlapping or gapped audio cues."""
    cues = data.get('mouthCues') if isinstance(data, dict) else None
    if not isinstance(cues, list) or not cues:
        raise AnimationError('Cue JSON must contain nonempty mouthCues')
    result = []
    previous = 0.0
    for i, item in enumerate(cues):
        try:
            start, end = float(item['start']), float(item['end'])
            symbol = item['value']
        except (KeyError, TypeError, ValueError) as exc:
            raise AnimationError(f'Invalid cue {i}') from exc
        if (not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start
                or not isinstance(symbol, str) or symbol not in SYMBOLS):
            raise AnimationError(f'Invalid cue {i}')
        # Rhubarb uses hundredths of a second. A 1 ms tolerance is only for
        # serialization error, not for leaving holes in the timeline.
        if abs(start - previous) > 0.001:
            raise AnimationError(f'Cue {i} has a gap or overlap at {previous:.3f}s')
        result.append((start, end, symbol))
        previous = end
    if abs(previous - seconds) > 0.015:
        raise AnimationError(f'Cue timeline {previous:.3f}s does not match speech {seconds:.3f}s')
    return result


def cue_at(cues, t):
    for start, end, symbol in cues:
        if start <= t < end:
            return symbol
    raise AnimationError(f'No cue covers video frame at {t:.3f}s')


def validate_landmarks(points, scores, previous, index, min_score=0.5):
    """Validate model landmarks in 512px crop space before any rendering."""
    points = np.asarray(points, dtype=float)
    scores = np.asarray(scores, dtype=float)
    if (points.shape != (68, 2) or scores.shape != (68,)
            or not np.isfinite(points).all() or not np.isfinite(scores).all()
            or scores.min() < min_score):
        raise AnimationError(f'Frame {index}: missing, malformed or low-confidence face landmarks')
    if np.any(points < 0) or np.any(points >= 512):
        raise AnimationError(f'Frame {index}: face landmarks fall outside the crop')
    face_size = np.ptp(points, axis=0)
    if face_size[0] < 60 or face_size[1] < 60:
        raise AnimationError(f'Frame {index}: face landmarks are too small or invalid')
    mouth = points[48:68]
    width = float(np.linalg.norm(mouth[6] - mouth[0]))
    if width < 8 or width > face_size[0] * 0.8:
        raise AnimationError(f'Frame {index}: mouth landmarks have implausible width')
    center = (mouth[0] + mouth[6]) / 2
    if center[1] < np.mean(points[36:48, 1]):
        raise AnimationError(f'Frame {index}: mouth is above the eyes')
    if previous is not None and np.linalg.norm(center - previous) > 18:
        raise AnimationError(f'Frame {index}: face tracking jumped unexpectedly')
    return mouth, center


def load_art(directory, cues, cv2):
    images = {}
    # X is the original resting mouth; A requires an explicit drawing.
    for symbol in sorted({c[2] for c in cues} - {'X'}):
        path = directory / f'{symbol}.png'
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if (image is None or image.ndim != 3 or image.shape[2] != 4 or min(image.shape[:2]) < 2
                or not np.any(image[:,:,3]) or not np.any(image[:,:,3] < 255)):
            raise AnimationError(f'{path} must be a nonempty transparent RGBA PNG for cue {symbol}')
        images[symbol] = image
    return images


def demo_art(cv2):
    """Simple vector marks for testing only, deliberately not finished artwork."""
    shapes = {'A':(1,1.0), 'B':(3,1.0), 'C':(8,1.0), 'D':(15,1.0),
              'E':(10,.75), 'F':(13,.50), 'G':(3,1.0), 'H':(7,.8)}
    images = {}
    for symbol, (height, span) in shapes.items():
        im = np.zeros((64,128,4), np.uint8)
        cv2.ellipse(im, (64,32), (int(51*span), height), 0, 0, 360, (51,38,59,255), -1, cv2.LINE_AA)
        images[symbol] = im
    return images


def overlay(frame, mouth, crop, symbol, art, cv2, width_scale):
    if symbol == 'X':
        return frame
    x,y,size,_ = crop
    pts = mouth * (size / 512.0) + np.array([x,y])
    left, right = pts[0], pts[6]
    center = (left + right) / 2
    width = np.linalg.norm(right-left)
    angle = math.degrees(math.atan2(right[1]-left[1], right[0]-left[0]))
    # This small inpaint region removes the original mouth stroke. It is not
    # robust to occlusion, wide turns, or a non-mouth object crossing the face.
    mask = np.zeros(frame.shape[:2], np.uint8)
    cv2.ellipse(mask, tuple(np.round(center).astype(int)), (max(2,int(width*.56)), max(3,int(width*.13))),
                angle, 0, 360, 255, -1)
    repaired = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
    feather = cv2.GaussianBlur(mask, (9,9), 2).astype(np.float32)[:,:,None] / 255
    frame = np.clip(repaired*feather + frame*(1-feather), 0, 255).astype(np.uint8)
    im = art[symbol]
    target_width = max(2, int(round(width * width_scale)))
    target_height = max(2, int(round(target_width * im.shape[0] / im.shape[1])))
    if target_width > frame.shape[1] or target_height > frame.shape[0]:
        raise AnimationError('Artwork size exceeds the video frame')
    im = cv2.resize(im, (target_width,target_height), interpolation=cv2.INTER_AREA)
    # Rotate in a padded canvas so the PNG is not clipped by rotation.
    side = int(math.ceil(math.hypot(target_width,target_height))) + 4
    canvas = np.zeros((side,side,4), np.uint8)
    ox, oy = (side-target_width)//2, (side-target_height)//2
    canvas[oy:oy+target_height,ox:ox+target_width] = im
    rotation = cv2.getRotationMatrix2D((side/2,side/2), -angle, 1.0)
    canvas = cv2.warpAffine(canvas, rotation, (side,side), flags=cv2.INTER_LINEAR)
    x0, y0 = int(round(center[0]-side/2)), int(round(center[1]-side/2))
    if x0 < 0 or y0 < 0 or x0+side > frame.shape[1] or y0+side > frame.shape[0]:
        raise AnimationError('Tracked mouth artwork extends outside the video frame')
    alpha = canvas[:,:,3:4].astype(np.float32)/255
    roi = frame[y0:y0+side,x0:x0+side].astype(np.float32)
    frame[y0:y0+side,x0:x0+side] = np.clip(canvas[:,:,:3]*alpha + roi*(1-alpha), 0, 255).astype(np.uint8)
    return frame


def track(video, crop, frames, cv2, return_face_landmarks=False):
    # Set before importing torch/mmpose: this command never initializes CUDA.
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['HF_HOME'] = str(ROOT / 'venvs' / 'hf-cache')
    os.environ['TRANSFORMERS_CACHE'] = str(ROOT / 'venvs' / 'hf-cache' / 'hub')
    import torch
    from mmpose.apis import inference_topdown, init_model
    from mmpose.structures import merge_data_samples
    torch.set_num_threads(min(6, os.cpu_count() or 1))
    config = ENGINE / 'musetalk/utils/dwpose/rtmpose-l_8xb32-270e_coco-ubody-wholebody-384x288.py'
    weights = ENGINE / 'models/dwpose/dw-ll_ucoco_384.pth'
    if not config.is_file() or not weights.is_file():
        raise AnimationError('MuseTalk DWPose config or weights are missing')
    model = init_model(str(config), str(weights), device='cpu')
    cap = cv2.VideoCapture(str(video))
    mouths, face_landmarks, previous, minimum = [], [], None, 1.0
    x,y,size,_ = crop
    try:
        for i in range(frames):
            ok, frame = cap.read()
            if not ok:
                raise AnimationError(f'Frame {i}: source decoding failed')
            sample = cv2.resize(frame[y:y+size,x:x+size], (512,512), interpolation=cv2.INTER_CUBIC)
            try:
                results = merge_data_samples(inference_topdown(model, sample)).pred_instances
            except Exception as exc:
                raise AnimationError(f'Frame {i}: face tracking failed: {exc}') from exc
            if len(results.keypoints) != 1:
                raise AnimationError(f'Frame {i}: could not obtain one face landmark set')
            pts = results.keypoints[0][23:91]
            scores = results.keypoint_scores[0][23:91]
            mouth, previous = validate_landmarks(pts, scores, previous, i)
            mouths.append(mouth)
            if return_face_landmarks:
                face_landmarks.append(np.asarray(pts, dtype=float).copy())
            minimum = min(minimum, float(np.min(scores)))
            if (i+1) % 25 == 0:
                print(f'Tracked {i+1}/{frames} frames on CPU', flush=True)
        if cap.read()[0]:
            raise AnimationError('Source has extra frames after normalization')
    finally:
        cap.release()
    print(f'Tracked all {frames} frames; minimum landmark score {minimum:.3f}', flush=True)
    return (mouths, face_landmarks) if return_face_landmarks else mouths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--face-crop', type=parse_crop, required=True, metavar='X,Y,SIZE,SIZE')
    timing = parser.add_mutually_exclusive_group(required=True)
    timing.add_argument('--transcript', type=Path, help='UTF-8 transcript for local Rhubarb')
    timing.add_argument('--cues', type=Path, help='Existing Rhubarb-format JSON cues')
    artwork = parser.add_mutually_exclusive_group(required=True)
    artwork.add_argument('--art-dir', type=Path, help='Character-specific transparent cue PNGs')
    artwork.add_argument('--demo-shapes', action='store_true', help='Use crude built-in marks for testing only')
    parser.add_argument('--rhubarb', type=Path, default=RHUBARB)
    parser.add_argument('--mouth-width-scale', type=float, default=1.15)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    try:
        import cv2
        visual, audio, output = args.video.resolve(), args.audio.resolve(), args.out.resolve()
        if not visual.is_file() or not audio.is_file():
            raise AnimationError('Video and audio must be existing files')
        if output.suffix.lower() != '.mp4' or output in (visual,audio):
            raise AnimationError('Output must be an MP4 distinct from the inputs')
        if args.transcript and output == args.transcript.resolve() or args.cues and output == args.cues.resolve():
            raise AnimationError('Output must be distinct from transcript and cues')
        if output.exists() and not args.overwrite:
            raise AnimationError('Output exists; use --overwrite to replace it')
        if not math.isfinite(args.mouth_width_scale) or not 0.5 <= args.mouth_width_scale <= 2:
            raise AnimationError('Mouth width scale must be between 0.5 and 2')
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            raise AnimationError('ffmpeg and ffprobe must be on PATH')
        if args.transcript and (not args.transcript.is_file() or not args.rhubarb.is_file()):
            raise AnimationError('Transcript or Rhubarb executable not found')
        if args.cues and not args.cues.is_file():
            raise AnimationError('Cue JSON not found')
        if args.art_dir and not args.art_dir.is_dir():
            raise AnimationError('Artwork directory not found')
        video_info, audio_info = probe(visual), probe(audio)
        video_stream = next((s for s in video_info.get('streams', []) if s.get('codec_type') == 'video'), None)
        if not video_stream or not any(s.get('codec_type') == 'audio' for s in audio_info.get('streams', [])):
            raise AnimationError('Inputs must contain video and audio streams')
        x,y,size,_ = args.face_crop
        width,height = int(video_stream['width']), int(video_stream['height'])
        if x+size > width or y+size > height:
            raise AnimationError('Face crop exceeds source video bounds')
        source_duration = duration(video_stream.get('duration'), 'source video stream')
        output.parent.mkdir(parents=True, exist_ok=True)
        jobs = ROOT / 'jobs'; jobs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='anime-lip-', dir=jobs) as tmp:
            work = Path(tmp); voice = work / 'voice.wav'; stage = work / 'video.mp4'
            command(['ffmpeg','-v','error','-nostdin','-y','-i',str(audio),'-vn','-c:a','pcm_s16le',str(voice)])
            expected = duration(probe(voice).get('format', {}).get('duration'), 'speech')
            if source_duration + 0.001 < expected:
                raise AnimationError('Source video is shorter than speech; looping is not allowed')
            frames = math.floor(expected*FPS)
            if frames < 1:
                raise AnimationError('Speech must be at least one video frame long')
            command(['ffmpeg','-v','error','-nostdin','-y','-i',str(visual),'-map','0:v:0','-an',
                     '-vf',f'fps={FPS}','-frames:v',str(frames),'-c:v','libx264','-crf','18',
                     '-pix_fmt','yuv420p',str(stage)])
            sv = next(s for s in probe(stage)['streams'] if s.get('codec_type') == 'video')
            if int(sv.get('nb_frames',0)) != frames:
                raise AnimationError('Decoded source has too few frames; looping is not allowed')
            cues_path = args.cues
            if args.transcript:
                cues_path = work / 'cues.json'
                command([str(args.rhubarb.resolve()),'--quiet','--dialogFile',str(args.transcript.resolve()),
                         '--exportFormat','json','--output',str(cues_path),str(voice)], capture_output=True)
            try:
                cues = validate_cues(json.loads(cues_path.read_text(encoding='utf8')), expected)
            except (OSError, ValueError) as exc:
                raise AnimationError(f'Cannot read cue JSON: {exc}') from exc
            art = demo_art(cv2) if args.demo_shapes else load_art(args.art_dir.resolve(),cues,cv2)
            print('Experimental animation: validate every face frame on CPU.',flush=True)
            mouths = track(stage, args.face_crop, frames, cv2)
            rendered = work / 'rendered.mp4'
            process = subprocess.Popen(['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','bgr24',
                '-s',f'{width}x{height}','-r',str(FPS),'-i','pipe:0','-i',str(voice),'-map','0:v:0','-map','1:a:0',
                '-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(rendered)],
                stdin=subprocess.PIPE)
            cap = cv2.VideoCapture(str(stage))
            try:
                for i,mouth in enumerate(mouths):
                    ok, frame = cap.read()
                    if not ok:
                        raise AnimationError(f'Frame {i}: source decoding failed during compositing')
                    symbol = cue_at(cues,(i+0.5)/FPS)
                    process.stdin.write(overlay(frame,mouth,args.face_crop,symbol,art,cv2,args.mouth_width_scale).tobytes())
            finally:
                cap.release()
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
                code = process.wait()
            if code:
                raise AnimationError(f'Video encoder exited with status {code}')
            info = probe(rendered)
            vs = next((s for s in info.get('streams',[]) if s.get('codec_type') == 'video'),None)
            aus = next((s for s in info.get('streams',[]) if s.get('codec_type') == 'audio'),None)
            if not vs or not aus or int(vs.get('nb_frames',0)) != frames or abs(duration(aus.get('duration'),'output audio')-expected) > .03:
                raise AnimationError('Output stream count or duration is incorrect')
            command(['ffmpeg','-v','error','-xerror','-i',str(rendered),'-map','0:v:0','-map','0:a:0','-f','null','-'])
            fd,name = tempfile.mkstemp(prefix='.anime-lip-',suffix='.mp4',dir=output.parent); os.close(fd)
            staged = Path(name)
            try:
                shutil.copyfile(rendered,staged)
                if output.exists() and not args.overwrite:
                    raise AnimationError('Output appeared during rendering')
                os.replace(staged,output)
            finally:
                staged.unlink(missing_ok=True)
        print(f'Experimental output: {output}. Review mouth shapes, synchronization, and tracking before use.')
        return 0
    except (AnimationError, OSError, ValueError, KeyError, IndexError, ImportError, RuntimeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
