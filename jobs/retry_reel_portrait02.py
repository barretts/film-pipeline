"""Create a centered second alternate of the original cel-animation portrait."""
import reel_style_variants as generator

generator.NEGATIVE = (
    "child, teenager, minor, male, profile, side view, looking away, open mouth, teeth, "
    "hand over face, cropped face, cropped head, close-up, extreme close-up, off-center, out of frame, "
    "extra faces, multiple people, photograph, photorealistic, live action, 3d render, cgi, realistic skin, "
    "skin pores, wax skin, existing character, distorted anatomy, text, words, letters, watermark, logo"
)
generator.JOBS = [
    ("characters/02-retry2.png", 768, 768, 3622,
     "Traditional 2D hand-drawn cel animation, centered medium shot of an original adult woman from the chest up, "
     "frontal symmetrical pose, her whole head, hair and both shoulders visible, generous space around her head "
     "and below her chin, face occupies only one third of image, no cropping, her straight face looking into the camera, "
     "adult woman with shoulder-length auburn hair and green eyes, fully visible eyes nose and closed relaxed mouth, "
     "friendly serious expression, sophisticated Disney-inspired hand-painted animation feature, visible ink outlines, "
     "flat painted colors and matte 2D cel shadows, warm ivory skin, deep green clothing and subtle rust tones, "
     "plain dark green background, clearly an original adult character, no words.")
]

if __name__ == "__main__":
    generator.main()
