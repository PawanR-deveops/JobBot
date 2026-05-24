"""
Creates the bot logo and uploads it as the bot's profile photo via Telegram API.
Run once: python set_logo.py
Or trigger via GitHub Actions → set_logo workflow (workflow_dispatch).
"""

import io
import os
import requests
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ.get("TELEGRAM_TOKEN") or input("Enter bot token: ").strip()
API   = f"https://api.telegram.org/bot{TOKEN}"

SIZE    = 512
BG      = "#0f3460"
CIRCLE  = "#16213e"
ACCENT  = "#e94560"
WHITE   = "#ffffff"
GOLD    = "#f5a623"
GREY    = "#aaaaaa"

FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def create_logo() -> bytes:
    img  = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    # Outer filled circle
    draw.ellipse([30, 30, SIZE - 30, SIZE - 30], fill=CIRCLE)

    # Accent ring
    draw.ellipse([60, 60, SIZE - 60, SIZE - 60], outline=ACCENT, width=6)

    # "JH" monogram
    font_jh = _load_font(160)
    draw.text((SIZE // 2, 200), "JH", fill=WHITE, font=font_jh, anchor="mm")

    # Accent underline bar
    bw = 180
    draw.rounded_rectangle(
        [SIZE // 2 - bw // 2, 305, SIZE // 2 + bw // 2, 311],
        radius=3, fill=ACCENT,
    )

    # "JobHunt India" subtitle
    font_sub = _load_font(42)
    draw.text((SIZE // 2, 362), "JobHunt India", fill=GOLD, font=font_sub, anchor="mm")

    # Small tag line
    font_sm = _load_font(22)
    draw.text((SIZE // 2, 415), "LinkedIn Job Alert Bot", fill=GREY, font=font_sm, anchor="mm")

    # India tricolor strip at bottom
    strip_y = 455
    strip_h = 10
    total_w = 280
    seg_w   = total_w // 3
    x0      = SIZE // 2 - total_w // 2
    draw.rectangle([x0,              strip_y, x0 + seg_w,          strip_y + strip_h], fill="#FF9933")
    draw.rectangle([x0 + seg_w,      strip_y, x0 + seg_w * 2,      strip_y + strip_h], fill="#FFFFFF")
    draw.rectangle([x0 + seg_w * 2,  strip_y, x0 + total_w,        strip_y + strip_h], fill="#138808")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def set_bot_photo(image_bytes: bytes) -> bool:
    resp = requests.post(
        f"{API}/setMyPhoto",
        files={"photo": ("bot_logo.png", image_bytes, "image/png")},
        timeout=30,
    )
    data = resp.json()
    if data.get("ok"):
        print("Bot profile photo set successfully!")
        return True
    else:
        print(f"setMyPhoto failed: {data.get('description', data)}")
        return False


def main():
    print("Creating logo...")
    image_bytes = create_logo()

    # Save locally as well
    with open("bot_logo.png", "wb") as f:
        f.write(image_bytes)
    print("Logo saved: bot_logo.png")

    print("Uploading to Telegram...")
    if not set_bot_photo(image_bytes):
        print("\nManual fallback:")
        print("1. Open Telegram → @BotFather")
        print("2. Send /setuserpic")
        print("3. Select your bot")
        print("4. Send the file: bot_logo.png")


if __name__ == "__main__":
    main()
