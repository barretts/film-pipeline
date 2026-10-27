"""Experimental 68-point DWPose-to-LatentSync alignment bridge.

The mapping is an approximation, not a validated equivalent of InsightFace.
It is deliberately not enabled by the existing production research runner.
"""
import numpy as np


class PoseAlignmentError(ValueError):
    pass


def anchors(points):
    """Map validated COCO-WholeBody 68-point face landmarks to three anchors.

    Input is in the same 512x512 pixel space as LatentSync's crop. Brow points
    are 17:22 and 22:27; nose points are 27:36. Order is left-to-right in the
    image to match LatentSync's affine template, not the subject's left/right.
    """
    points = np.asarray(points, dtype=np.float64)
    if points.shape != (68, 2) or not np.isfinite(points).all() or np.any(points < 0) or np.any(points >= 512):
        raise PoseAlignmentError('Expected 68 finite face landmarks inside the 512-pixel crop')
    brow_a, brow_b = points[17:22].mean(axis=0), points[22:27].mean(axis=0)
    left, right = sorted((brow_a, brow_b), key=lambda p: p[0])
    nose = points[27:36].mean(axis=0)
    if np.linalg.norm(right-left) < 20 or nose[1] <= max(left[1],right[1]):
        raise PoseAlignmentError('Invalid eyebrow/nose anchor geometry')
    return np.round(np.stack([left, right, nose])).astype(np.float32)


def install(pose_frames):
    """Install an isolated-process bridge without loading InsightFace weights.

    This overrides the imported ImageProcessor only inside the child process.
    The caller must pass one 68x2 array per video frame and call assert_complete.
    """
    import cv2
    import torch
    from einops import rearrange
    import latentsync.utils.image_processor as upstream

    all_anchors = [anchors(frame) for frame in pose_frames]
    if not all_anchors:
        raise PoseAlignmentError('No pose frames')
    state = {'next': 0, 'total': len(all_anchors)}
    # ImageProcessor.__init__ asks FaceDetector(...) for a detector. The patched
    # affine method below consumes tracked anchors, never this sentinel.
    upstream.FaceDetector = lambda device='cuda': object()

    def affine_transform(processor, image):
        index = state['next']
        if index >= state['total']:
            raise PoseAlignmentError(f'Unexpected extra video frame {index}')
        if image.shape != (512, 512, 3):
            raise PoseAlignmentError(f'Frame {index} must be 512x512 RGB')
        face, matrix = processor.restorer.align_warp_face(image.copy(), landmarks3=all_anchors[index], smooth=True)
        state['next'] += 1
        box = [0, 0, face.shape[1], face.shape[0]]
        face = cv2.resize(face, (processor.resolution, processor.resolution), interpolation=cv2.INTER_LANCZOS4)
        face = rearrange(torch.from_numpy(face), 'h w c -> c h w')
        return face, box, matrix

    upstream.ImageProcessor.affine_transform = affine_transform
    return state


def assert_complete(state):
    if state['next'] != state['total']:
        raise PoseAlignmentError(f"Consumed {state['next']} of {state['total']} pose frames")
