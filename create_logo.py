"""
Generates a professional bot logo (512x512 PNG).
Run once: python create_logo.py
Then upload bot_logo.png to BotFather via /setuserpic
"""

from PIL import Image, ImageDraw, ImageFont
import os

SIZE   = 512
BG     = "#0f3460"       # dark navy
CIRCLE = "#16213e"       # slightly lighter navy
ACCENT = "#e94560"       # red-pink accent
WHITE  = "#ffffff"
GOLD   = "#f5a623"


def create_logo():
    img  = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    # Outer circle
    pad = 30
    draw.ellipse([pad, pad, SIZE - pad, SIZE - pad], fill=CIRCLE)

    # Inner accent ring
    draw.ellipse([60, 60, SIZE - 60, SIZE - 60], outline=ACCENT, width=6)

    # Try to load bold font, fallback to default
    font_jh   = None
    font_sub  = None
    font_dots = None

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font_jh   = ImageFont.truetype(path, 160)
                font_sub  = ImageFont.truetype(path, 42)
                font_dots = ImageFont.truetype(path, 22)
                break
            except Exception:
                continue

    if not font_jh:
        font_jh  = ImageFont.load_default()
        font_sub = font_jh

    # Main "JH" letters
    draw.text((SIZE // 2, 205), "JH", fill=WHITE, font=font_jh, anchor="mm")

    # Accent underline bar
    bar_w, bar_h = 180, 6
    draw.rounded_rectangle(
        [(SIZE // 2 - bar_w // 2), 305, (SIZE // 2 + bar_w // 2), 305 + bar_h],
        radius=3, fill=ACCENT,
    )

    # Subtitle text
    draw.text((SIZE // 2, 360), "JobHunt India", fill=GOLD,  font=font_sub, anchor="mm")
    draw.text((SIZE // 2, 415), "LinkedIn Job Alert Bot",    fill="#aaaaaa", font=font_dots or font_sub, anchor="mm")

    out = "bot_logo.png"
    img.save(out)
    print(f"Logo saved: {out}")
    return out


if __name__ == "__main__":
    create_logo()
