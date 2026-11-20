"""
Build the in-game Ferry sprites (assets/ferry/ferry_<plate>_<mood>.png, 276x360)
from Yui's full-size drawings in assets/source.

The drawings share one body; only the plate contents and the face differ.
For every plate state we take the drawing that shows that plate, and paste the
face region (eyes, blush, tears, sparkles) from a drawing with the wanted mood.

Run:  python tools/build_sprites.py
Needs Pillow (pip install pillow).
"""
import os
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "source")
OUT = os.path.join(HERE, "..", "assets", "ferry")

# Crop window in the 1545x2000 drawings and the sprite size the game expects.
CROP = (392, 255, 392 + 1066, 1646)
SIZE = (276, 360)
# Region of the drawing that holds everything that changes with the mood.
FACE = (540, 440, 1000, 920)
FEATHER = 14

PLATES = ["empty", "bread", "salad", "ham", "cheese", "cucumber", "tomato", "breadontop"]
MOODS = ["neutral", "happy", "confused"]

# Which drawing shows each plate state (any mood works - the face gets replaced).
BODY = {
    "empty": "ferry_empty_neutral",
    "bread": "ferry_bread_neutral",
    "salad": "ferry_salad_happy",
    "ham": "ferry_ham_happy",
    "cheese": "ferry_cheese_happy",
    "cucumber": "ferry_cucumber_happy",
    "tomato": "ferry_tomato_happy",
    "breadontop": "ferry_breadontop_happy",
}
# Which drawing supplies the face for each mood.
FACE_SRC = {
    "neutral": "ferry_empty_neutral",
    "happy": "ferry_salad_happy",
    "confused": "ferry_salad_confused",
}


def load(name):
    return Image.open(os.path.join(SRC, name + ".png")).convert("RGBA")


def face_mask():
    """Rectangle over FACE with soft edges so the paste never shows a seam."""
    w, h = FACE[2] - FACE[0], FACE[3] - FACE[1]
    m = Image.new("L", (w, h), 0)
    m.paste(255, (FEATHER, FEATHER, w - FEATHER, h - FEATHER))
    return m.filter(ImageFilter.GaussianBlur(FEATHER / 2))


def build(out_dir=OUT):
    os.makedirs(out_dir, exist_ok=True)
    faces = {m: load(FACE_SRC[m]).crop(FACE) for m in MOODS}
    mask = face_mask()
    for plate in PLATES:
        body = load(BODY[plate])
        for mood in MOODS:
            im = body.copy()
            im.paste(faces[mood], FACE[:2], mask)
            sprite = im.crop(CROP).resize(SIZE, Image.LANCZOS)
            path = os.path.join(out_dir, f"ferry_{plate}_{mood}.png")
            sprite.save(path, optimize=True)
            print("wrote", os.path.relpath(path))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else OUT)
