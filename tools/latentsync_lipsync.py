#!/usr/bin/env python3
"""Experimental research-only LatentSync on a tracked moving character.

The default InsightFace buffalo_l detector weights are licensed for
non-commercial research only. The optional DWPose bridge is unvalidated.
All outputs require human visual and sync review and component license checks.
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
import time

import numpy as np
import anime_lipsync as tracker

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / 'tools' / 'LatentSync'
PYTHON = ROOT / 'venvs' / 'latentsync' / 'Scripts' / 'python.exe'
FPS = 25


class LatentSyncError(Exception):
    pass


def chunks(frames, chunk_frames):
    if frames < 1 or chunk_frames < 1:
        raise LatentSyncError('Frame and chunk counts must be positive')
    # Spread the remainder across all chunks to avoid a tiny final utterance.
    number = (frames + chunk_frames - 1) // chunk_frames
    base, extra = divmod(frames, number)
    spans = []
    start = 0
    for index in range(number):
        end = start + base + (index < extra)
        spans.append((start, end))
        start = end
    return spans


def blend(frame, generated, mouth, crop, cv2):
    x, y, size, _ = crop
    if generated.shape != (512, 512, 3):
        raise LatentSyncError('Generated crop must be 512x512')
    points = np.asarray(mouth, dtype=float)
    if points.shape != (20, 2) or not np.isfinite(points).all() or np.any(points < 0) or np.any(points >= 512):
        raise LatentSyncError('Invalid tracked mouth')
    center = points.mean(axis=0) * (size / 512.0)
    # Preserve the proof's 35x22 ellipse and 31px feather at its 448px crop.
    scale = size / 448.0
    axes = (max(1, round(35 * scale)), max(1, round(22 * scale)))
    kernel = max(3, round(31 * scale)) | 1
    if center[0] - axes[0] - kernel//2 < 0 or center[1] - axes[1] - kernel//2 < 0 or center[0] + axes[0] + kernel//2 >= size or center[1] + axes[1] + kernel//2 >= size:
        raise LatentSyncError('Tracked mouth and feather must remain inside the crop')
    patch = cv2.resize(generated, (size, size), interpolation=cv2.INTER_AREA)
    mask = np.zeros((size, size), dtype=np.float32)
    cv2.ellipse(mask, tuple(np.round(center).astype(int)), axes, 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (kernel, kernel), 8 * scale)[:, :, None]
    roi = frame[y:y+size, x:x+size].astype(np.float32)
    if roi.shape != patch.shape:
        raise LatentSyncError('Crop exceeds video frame')
    frame[y:y+size, x:x+size] = np.clip(patch.astype(np.float32) * mask + roi * (1 - mask), 0, 255).astype(np.uint8)
    return frame


def setup_engine(work, use_insightface=True):
    """Use a private cwd: upstream removes its cwd/temp on every run."""
    if not PYTHON.is_file() or not (ENGINE / 'checkpoints/latentsync_unet.pt').is_file() or not (ENGINE / 'checkpoints/whisper/tiny.pt').is_file():
        raise LatentSyncError('LatentSync environment or 1.5 weights are missing')
    shutil.copytree(ENGINE / 'configs', work / 'configs')
    mask = work / 'latentsync/utils/mask.png'
    mask.parent.mkdir(parents=True)
    shutil.copyfile(ENGINE / 'latentsync/utils/mask.png', mask)
    whisper = work / 'checkpoints/whisper/tiny.pt'
    whisper.parent.mkdir(parents=True)
    try:
        os.link(ENGINE / 'checkpoints/whisper/tiny.pt', whisper)
    except OSError:
        shutil.copyfile(ENGINE / 'checkpoints/whisper/tiny.pt', whisper)
    if use_insightface:
        pack = ENGINE / 'checkpoints/auxiliary/models/buffalo_l'
        if not (pack / 'det_10g.onnx').is_file() or not (pack / '2d106det.onnx').is_file():
            raise LatentSyncError('InsightFace buffalo_l detector models are missing')
        destination = work / 'checkpoints/auxiliary/models/buffalo_l'
        destination.mkdir(parents=True)
        for name in ('det_10g.onnx', '2d106det.onnx'):
            try:
                os.link(pack / name, destination / name)
            except OSError:
                shutil.copyfile(pack / name, destination / name)


def call(command, **kwargs):
    try:
        return subprocess.run(command, check=True, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LatentSyncError(f'Command failed: {command[0]}: {exc}') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--face-crop', required=True, type=tracker.parse_crop, metavar='X,Y,SIZE,SIZE')
    parser.add_argument('--chunk-seconds', type=int, default=6, help='Bound each GPU inference to 1–12 seconds (default: 6)')
    parser.add_argument('--detector', choices=('insightface','dwpose'), default='insightface', help='dwpose is an experimental, unvalidated alignment bridge')
    parser.add_argument('--profile-voiceover', action='store_true', help='Keep original video during chunks with invalid DWPose face alignment; narration becomes voiceover there')
    parser.add_argument('--research-only', action='store_true', help='Acknowledge InsightFace buffalo_l is non-commercial research only')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    try:
        import cv2
        if args.detector == 'insightface' and not args.research_only:
            raise LatentSyncError('InsightFace buffalo_l weights are non-commercial research only; pass --research-only to acknowledge')
        if args.profile_voiceover and args.detector != 'dwpose':
            raise LatentSyncError('--profile-voiceover requires --detector dwpose')
        video, audio, output = (p.resolve() for p in (args.video, args.audio, args.out))
        if not video.is_file() or not audio.is_file():
            raise LatentSyncError('Video and audio must be existing files')
        if output.suffix.lower() != '.mp4' or output in (video, audio):
            raise LatentSyncError('Output must be an MP4 distinct from the inputs')
        if output.exists() and not args.overwrite:
            raise LatentSyncError('Output already exists; use --overwrite to replace it')
        if not 1 <= args.chunk_seconds <= 12:
            raise LatentSyncError('Chunk duration must be between 1 and 12 seconds')
        if any(char in str(ROOT) for char in ' \t\r\n&()^%!"<>|'):
            raise LatentSyncError('Workspace path contains characters unsupported by upstream shell commands')
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            raise LatentSyncError('ffmpeg and ffprobe are required')
        vinfo, ainfo = tracker.probe(video), tracker.probe(audio)
        stream = next((s for s in vinfo.get('streams', []) if s.get('codec_type') == 'video'), None)
        if not stream or not any(s.get('codec_type') == 'audio' for s in ainfo.get('streams', [])):
            raise LatentSyncError('Inputs must contain video and audio streams')
        width, height = int(stream['width']), int(stream['height'])
        x, y, size, _ = args.face_crop
        if x + size > width or y + size > height:
            raise LatentSyncError('Face crop exceeds video bounds')
        source_duration = tracker.duration(stream.get('duration'), 'video')
        jobs, logs = ROOT / 'jobs', ROOT / 'logs'
        jobs.mkdir(exist_ok=True); logs.mkdir(exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        log = logs / f'latentsync-{time.time_ns()}.log'
        with tempfile.TemporaryDirectory(prefix='latent-', dir=jobs) as tmp:
            work = Path(tmp); setup_engine(work, use_insightface=args.detector == 'insightface')
            voice, stage, cropped = work/'voice.wav', work/'video.mp4', work/'crop.mp4'
            call(['ffmpeg','-v','error','-nostdin','-y','-i',str(audio),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(voice)])
            seconds = tracker.duration(tracker.probe(voice).get('format', {}).get('duration'), 'speech')
            if source_duration + .001 < seconds:
                raise LatentSyncError('Video is shorter than speech; looping is not allowed')
            # Keep a complete video frame covering the final speech sample;
            # the frame must come from the real source, never a frozen tail.
            count = math.ceil(seconds * FPS - 1e-9)
            if count < 1:
                raise LatentSyncError('Speech is shorter than one video frame')
            call(['ffmpeg','-v','error','-nostdin','-y','-i',str(video),'-map','0:v:0','-an','-vf',f'fps={FPS}', '-frames:v',str(count),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(stage)])
            vs = next(s for s in tracker.probe(stage)['streams'] if s.get('codec_type') == 'video')
            if int(vs.get('nb_frames', 0)) != count:
                raise LatentSyncError('Normalized source has too few frames; looping is not allowed')
            call(['ffmpeg','-v','error','-nostdin','-y','-i',str(stage),'-vf',f'crop={size}:{size}:{x}:{y},scale=512:512:flags=bicubic','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(cropped)])
            old_cuda = os.environ.get('CUDA_VISIBLE_DEVICES')
            try:
                if args.detector == 'dwpose':
                    mouths, face_landmarks = tracker.track(stage, args.face_crop, count, cv2, return_face_landmarks=True)
                else:
                    mouths = tracker.track(stage, args.face_crop, count, cv2)
            finally:
                if old_cuda is None: os.environ.pop('CUDA_VISIBLE_DEVICES', None)
                else: os.environ['CUDA_VISIBLE_DEVICES'] = old_cuda
            env = os.environ.copy()
            env.update({'HF_HOME':str(ROOT/'venvs/hf-cache'), 'HF_HUB_OFFLINE':'1', 'NO_ALBUMENTATIONS_UPDATE':'1', 'PYTHONUNBUFFERED':'1', 'PYTHONPATH':str(ENGINE)})
            env.pop('TRANSFORMERS_CACHE', None)
            generated = []
            voiceover_spans = []
            spans = chunks(count, args.chunk_seconds * FPS)
            for index, (start, end) in enumerate(spans):
                if args.profile_voiceover:
                    import latentsync_dwpose_bridge as bridge
                    try:
                        for points in face_landmarks[start:end]:
                            bridge.anchors(points)
                    except bridge.PoseAlignmentError:
                        print(f'Keeping original motion during profile chunk {index+1}/{len(spans)} ({start/FPS:.2f}–{end/FPS:.2f}s); narration is voiceover there', flush=True)
                        voiceover_spans.append([start/FPS, end/FPS])
                        generated.append((None, end-start))
                        continue
                cvideo, caudio, result = work/f'crop-{index}.mp4', work/f'voice-{index}.wav', work/f'synced-{index}.mp4'
                call(['ffmpeg','-v','error','-nostdin','-y','-i',str(cropped),'-vf',f'trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(cvideo)])
                call(['ffmpeg','-v','error','-nostdin','-y','-i',str(voice),'-af',f'atrim=start_sample={start*640}:end_sample={end*640},asetpts=PTS-STARTPTS','-c:a','pcm_s16le',str(caudio)])
                print(f'Generating chunk {index+1}/{len(spans)}; log: {log}', flush=True)
                if args.detector == 'dwpose':
                    pose_file = work/f'pose-{index}.json'
                    pose_file.write_text(json.dumps([p.tolist() for p in face_landmarks[start:end]]), encoding='utf8')
                    command = [str(PYTHON),str(ROOT/'tools/latentsync_dwpose_worker.py'),'--pose-frames',str(pose_file)]
                else:
                    command = [str(PYTHON),'-m','scripts.inference']
                command += ['--unet_config_path','configs/unet/stage2.yaml','--inference_ckpt_path',str(ENGINE/'checkpoints/latentsync_unet.pt'),'--video_path',str(cvideo),'--audio_path',str(caudio),'--video_out_path',str(result),'--temp_dir',str(work/f'output-{index}'),'--inference_steps','20','--guidance_scale','1.5','--seed','1247']
                try:
                    with log.open('ab') as handle:
                        call(command, cwd=work, env=env, stdout=handle, stderr=subprocess.STDOUT)
                except LatentSyncError as exc:
                    raise LatentSyncError(f'LatentSync chunk {index+1} failed; see {log}') from exc
                if not result.is_file():
                    raise LatentSyncError(f'Chunk {index+1} produced no video; see {log}')
                rs = next((s for s in tracker.probe(result)['streams'] if s.get('codec_type') == 'video'), None)
                actual = int(rs.get('nb_frames', 0)) if rs else 0
                if not rs or int(rs.get('width', 0)) != 512 or int(rs.get('height', 0)) != 512 or rs.get('avg_frame_rate') != '25/1':
                    raise LatentSyncError(f'Chunk {index+1} must be 512x512 at 25 fps')
                if not end-start <= actual <= end-start+3:
                    raise LatentSyncError(f'Unexpected generated frame count {actual}; expected {end-start} plus at most 3 tail frames')
                generated.append((result, end-start))
            rendered = work/'rendered.mp4'
            proc = subprocess.Popen(['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{width}x{height}','-r',str(FPS),'-i','pipe:0','-i',str(voice),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(count/FPS),str(rendered)], stdin=subprocess.PIPE)
            original = cv2.VideoCapture(str(stage)); frame_index = 0
            try:
                for path, chunk_count in generated:
                    cap = cv2.VideoCapture(str(path)) if path else None
                    try:
                        for _ in range(chunk_count):
                            ok_a, a = original.read()
                            ok_b, b = cap.read() if cap else (True, None)
                            if not ok_a or not ok_b:
                                raise LatentSyncError(f'Frame decoding failed at {frame_index}')
                            proc.stdin.write((blend(a,b,mouths[frame_index],args.face_crop,cv2) if cap else a).tobytes())
                            frame_index += 1
                    finally:
                        if cap: cap.release()
            finally:
                original.release(); proc.stdin.close(); code = proc.wait()
            if code or frame_index != count:
                raise LatentSyncError('Compositing failed')
            info = tracker.probe(rendered)
            outv = next((s for s in info['streams'] if s.get('codec_type') == 'video'), None)
            outa = next((s for s in info['streams'] if s.get('codec_type') == 'audio'), None)
            if not outv or not outa or int(outv.get('nb_frames', 0)) != count or abs(tracker.duration(outa.get('duration'),'output audio') - seconds) > .03:
                raise LatentSyncError('Output frame count or duration is incorrect')
            call(['ffmpeg','-v','error','-xerror','-i',str(rendered),'-map','0:v:0','-map','0:a:0','-f','null','-'])
            fd, staged_name = tempfile.mkstemp(prefix='.latent-',suffix='.mp4',dir=output.parent); os.close(fd)
            staged = Path(staged_name)
            try:
                shutil.copyfile(rendered, staged)
                if output.exists() and not args.overwrite:
                    raise LatentSyncError('Output appeared during rendering')
                os.replace(staged, output)
            finally:
                staged.unlink(missing_ok=True)
        if voiceover_spans:
            output.with_suffix('.voiceover.json').write_text(json.dumps({'voiceover_spans_seconds': voiceover_spans}, indent=2), encoding='utf8')
            print(f'Profile voiceover intervals: {voiceover_spans}', flush=True)
        print(f'Experimental output ({args.detector}): {output}; review licenses, visual quality, chunk boundaries, and lip synchronization.', flush=True)
        return 0
    except (LatentSyncError, tracker.AnimationError, OSError, ValueError, KeyError, ImportError, StopIteration) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
