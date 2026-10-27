"""Create alternate cel-animation and stylized CG portraits without overwriting originals."""
import reel_style_variants as generator

generator.NEGATIVE = (
    "child, teenager, minor, baby, boy, man, male, profile, side view, looking away, "
    "open mouth, teeth, hand over face, cropped face, extra faces, multiple people, "
    "photograph, photorealistic, live action, realistic skin, skin pores, wax skin, "
    "existing character, copyrighted character, distorted anatomy, text, words, letters, watermark, logo"
)
generator.JOBS = [
    ("characters/02-retry.png", 768, 768, 3612,
     "Traditional hand-drawn 2D cel animation, an original adult woman with auburn shoulder-length hair and green eyes, "
     "straight-on bust portrait, visible full shoulders and upper chest, face moderate size and centered in upper half, "
     "ample empty space below chin, direct gaze, adult facial proportions, fully visible eyes nose and gently closed mouth, "
     "clear confident adult face. Delicate expressive black ink outlines, flat painted skin colors, matte watercolor "
     "background, warm ivory and muted deep green, richly drawn Disney-inspired hand-painted feature-animation look, "
     "clearly hand-inked outlines, 2D painted cel, no CGI, original character, no words."),
    ("characters/03-retry.png", 768, 768, 3613,
     "Stylized 3D animated feature character render, an original adult woman with dark shoulder-length curly hair "
     "and hazel eyes, straight-on chest-up portrait with visible shoulders, face medium size, direct gaze, "
     "fully visible eyes nose and relaxed closed mouth, expressive larger eyes and intentionally caricatured stylized "
     "adult facial features, polished rounded 3D sculpt, visibly CGI rather than a real photograph, sophisticated "
     "DreamWorks-inspired 3D animation look, cinematic soft lighting, dark ink blue and muted warm ivory, "
     "original adult female character, no words."),
]

if __name__ == "__main__":
    generator.main()
