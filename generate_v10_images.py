"""Generate flat product illustrations for the extra v10 demo products.

Each product gets a main image, an angled variant and a close-up variant, matching
the layout produced by generate_sample_images.py and generate_demo_images_v8.py.

Run: python generate_v10_images.py
Requires Pillow (already in requirements.txt).
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path("sample_images")
OUT.mkdir(exist_ok=True)
SIZE = 600
BG = (250, 250, 252)


def canvas():
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    d.ellipse((90, 500, 510, 548), fill=(232, 234, 238))
    return img, d


def draw_icon(d, kind, c1, c2, c3):
    """Draw a simple, recognisable product silhouette with three accent colours."""
    if kind == "necklace":
        d.arc((170, 140, 430, 400), 10, 170, fill=c2, width=10)
        for x, y in ((300, 410), (300, 450)):
            d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=(245, 243, 238), outline=c2, width=4)
        for i in range(7):
            x = 192 + i * 36
            y = 300 - abs(3 - i) * 26
            d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=c1, outline=c3, width=3)
    elif kind == "bracelet":
        d.ellipse((175, 185, 425, 435), fill=BG, outline=c2, width=22)
        for x, y in ((175, 310), (425, 310), (300, 190), (300, 430)):
            c = c1 if x != 300 else c3
            d.ellipse((x - 22, y - 22, x + 22, y + 22), fill=c, outline=c2, width=4)
        d.ellipse((280, 280, 320, 320), fill=c3, outline=c2, width=4)
    elif kind == "backpack":
        d.rounded_rectangle((185, 180, 415, 470), radius=42, fill=c1, outline=c2, width=5)
        d.arc((225, 130, 375, 260), 180, 360, fill=c2, width=14)
        d.rounded_rectangle((215, 325, 385, 440), radius=18, fill=c3, outline=c2, width=4)
        d.rounded_rectangle((270, 360, 330, 390), radius=8, fill=c2)
        for x in (220, 380):
            d.rounded_rectangle((x - 14, 440, x + 14, 490), radius=8, fill=c2)
    elif kind == "tote":
        d.polygon([(190, 245), (410, 245), (440, 470), (160, 470)], fill=c1, outline=c2)
        d.arc((230, 155, 370, 300), 180, 360, fill=c2, width=14)
        d.rounded_rectangle((250, 325, 350, 375), radius=10, fill=c3, outline=c2, width=3)
    elif kind == "watercolor":
        d.rounded_rectangle((140, 255, 390, 455), radius=20, fill=(248, 246, 240), outline=c2, width=5)
        for x, y, col in ((195, 310, c1), (275, 295, c3), (345, 325, c2)):
            d.ellipse((x - 32, y - 26, x + 32, y + 26), fill=col, outline=(210, 210, 205), width=3)
        d.line((405, 180, 480, 430), fill=c2, width=18)
        d.polygon([(392, 155), (435, 175), (410, 205)], fill=c3)
    elif kind == "stick":
        d.rounded_rectangle((190, 265, 390, 360), radius=18, fill=c1, outline=c2, width=5)
        d.rectangle((390, 285, 470, 340), fill=c2)
        d.rectangle((430, 295, 480, 330), fill=(225, 228, 233))
        d.ellipse((225, 290, 265, 330), fill=c3)
    elif kind == "binoculars":
        d.rounded_rectangle((165, 220, 290, 445), radius=34, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((310, 220, 435, 445), radius=34, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((270, 275, 330, 335), radius=14, fill=c2)
        d.ellipse((185, 235, 275, 325), fill=c3, outline=c2, width=5)
        d.ellipse((325, 235, 415, 325), fill=c3, outline=c2, width=5)
        d.ellipse((215, 260, 245, 290), fill=(80, 90, 100))
        d.ellipse((355, 260, 385, 290), fill=(80, 90, 100))
    elif kind == "stove":
        d.rounded_rectangle((175, 275, 425, 405), radius=20, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((200, 225, 400, 285), radius=14, fill=c2)
        for x in (225, 300, 375):
            d.ellipse((x - 28, 225, x + 28, 277), fill=c3, outline=(60, 62, 66), width=4)
        d.rounded_rectangle((245, 405, 355, 485), radius=16, fill=c3, outline=c2, width=4)
        d.line((215, 420, 175, 485), fill=c2, width=10)
        d.line((385, 420, 425, 485), fill=c2, width=10)
    elif kind == "oils":
        for x, col in ((200, c1), (300, c3), (400, c2)):
            d.rounded_rectangle((x - 38, 260, x + 38, 465), radius=14, fill=col, outline=c2, width=4)
            d.rounded_rectangle((x - 20, 190, x + 20, 265), radius=8, fill=(70, 72, 78))
            d.rounded_rectangle((x - 28, 175, x + 28, 205), radius=8, fill=c2)
            d.rounded_rectangle((x - 26, 330, x + 26, 390), radius=6, fill=(248, 247, 242))
    elif kind == "aid":
        d.rounded_rectangle((160, 250, 440, 460), radius=24, fill=(248, 248, 246), outline=c2, width=5)
        d.rounded_rectangle((260, 210, 340, 255), radius=10, outline=c2, width=10)
        d.rectangle((275, 320, 325, 395), fill=c1)
        d.rectangle((250, 345, 350, 370), fill=c1)
        d.rounded_rectangle((180, 270, 225, 300), radius=6, fill=c3)
    elif kind == "carrier":
        d.rounded_rectangle((160, 260, 440, 465), radius=28, fill=c1, outline=c2, width=5)
        d.arc((250, 160, 350, 290), 180, 360, fill=c2, width=14)
        for x in (215, 275, 335, 395):
            d.rounded_rectangle((x - 12, 300, x + 12, 410), radius=6, fill=c3)
        d.rounded_rectangle((250, 465, 350, 485), radius=8, fill=c2)
    elif kind == "lights":
        pts = [(110 + i * 38, 220 + (35 if i % 2 else -35)) for i in range(11)]
        d.line(pts, fill=c2, width=6, joint="curve")
        for x, y in pts[1:-1]:
            d.line((x, y, x, y + 30), fill=c2, width=4)
            d.ellipse((x - 16, y + 25, x + 16, y + 65), fill=c1, outline=c3, width=4)
    elif kind == "brush":
        d.rounded_rectangle((200, 180, 400, 330), radius=40, fill=c1, outline=c2, width=5)
        for i in range(9):
            x = 225 + i * 19
            d.line((x, 320, x, 450), fill=c3, width=5)
        d.ellipse((270, 205, 330, 265), fill=c2)
    else:
        d.rounded_rectangle((190, 220, 410, 460), radius=24, fill=c1, outline=c2, width=5)


# stem -> (icon kind, primary, outline, accent)
PRODUCTS = {
    "pearl_necklace": ("necklace", (245, 243, 236), (180, 165, 120), (220, 205, 160)),
    "charm_bracelet": ("bracelet", (225, 190, 95), (145, 115, 45), (205, 165, 70)),
    "backpack": ("backpack", (70, 115, 165), (40, 70, 105), (230, 180, 90)),
    "tote_bag": ("tote", (215, 180, 140), (135, 105, 75), (245, 235, 215)),
    "watercolor_set": ("watercolor", (95, 145, 195), (55, 85, 115), (220, 120, 110)),
    "streaming_stick": ("stick", (60, 62, 68), (32, 34, 38), (85, 150, 205)),
    "binoculars": ("binoculars", (65, 70, 78), (35, 38, 44), (95, 170, 215)),
    "camping_stove": ("stove", (200, 125, 70), (115, 65, 35), (150, 155, 160)),
    "essential_oil_kit": ("oils", (190, 160, 205), (110, 85, 130), (220, 200, 150)),
    "first_aid_kit": ("aid", (215, 80, 85), (135, 45, 50), (110, 165, 205)),
    "pet_carrier": ("carrier", (120, 155, 130), (65, 95, 75), (215, 220, 225)),
    "string_lights": ("lights", (250, 220, 130), (90, 85, 95), (245, 180, 100)),
    "pet_brush": ("brush", (95, 150, 185), (55, 90, 115), (235, 225, 190)),
}


for stem, (kind, c1, c2, c3) in PRODUCTS.items():
    img, d = canvas()
    draw_icon(d, kind, c1, c2, c3)
    img.save(OUT / f"{stem}.png", "PNG")
    img.rotate(-6, fillcolor=BG).save(OUT / f"{stem}_angle.png", "PNG")
    img.crop((70, 70, 530, 530)).resize((SIZE, SIZE)).save(OUT / f"{stem}_closeup.png", "PNG")
    print(f"{stem}.png (+2 variants)")

print(f"Generated {len(PRODUCTS)} new product image sets in {OUT}/")
