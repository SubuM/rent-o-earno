"""Generate extra flat product illustrations for the v8 demo dataset.

Complements generate_sample_images.py (24 product types) with 20 more types.
Each product gets a main image, an angled variant and a close-up variant.

Run: python generate_demo_images_v8.py
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
    if kind == "camera":
        d.rounded_rectangle((160, 230, 440, 420), radius=24, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((180, 200, 265, 238), radius=8, fill=c2)
        d.ellipse((235, 260, 385, 410), fill=c3, outline=c2, width=6)
        d.ellipse((275, 300, 345, 370), fill=(60, 66, 74))
        d.ellipse((300, 285, 320, 305), fill=(235, 240, 248))
    elif kind == "tent":
        d.polygon([(300, 155), (125, 470), (475, 470)], fill=c1, outline=c2)
        d.polygon([(300, 155), (300, 470), (205, 470)], fill=c2)
        d.polygon([(300, 305), (300, 470), (360, 470)], fill=c3)
        d.line((300, 155, 300, 470), fill=c2, width=4)
    elif kind == "guitar":
        d.ellipse((195, 260, 405, 475), fill=c1, outline=c2, width=5)
        d.ellipse((205, 270, 290, 355), fill=c1, outline=c2, width=5)
        d.ellipse((295, 340, 335, 380), fill=c2)
        d.rounded_rectangle((285, 150, 325, 340), radius=8, fill=c2)
        d.rounded_rectangle((280, 130, 330, 165), radius=6, fill=c3)
        for y in (175, 200, 225):
            d.line((270, y, 285, y), fill=c3, width=4)
            d.line((325, y, 340, y), fill=c3, width=4)
    elif kind == "keyboard":
        d.rounded_rectangle((120, 265, 480, 435), radius=14, fill=c1, outline=c2, width=5)
        for i in range(14):
            x = 140 + i * 24
            d.rectangle((x, 285, x + 19, 385), fill=(250, 250, 248), outline=(190, 192, 196))
        for i in range(10):
            x = 152 + i * 24
            d.rectangle((x, 285, x + 12, 340), fill=c3)
        d.rounded_rectangle((250, 400, 350, 420), radius=5, fill=c2)
    elif kind == "stroller":
        d.rounded_rectangle((210, 250, 390, 370), radius=28, fill=c1, outline=c2, width=5)
        d.line((390, 360, 445, 205), fill=c2, width=12)
        d.line((445, 205, 480, 205), fill=c2, width=12)
        d.line((215, 370, 400, 370), fill=c2, width=10)
        for x in (240, 380):
            d.ellipse((x - 28, 425, x + 28, 481), fill=c3, outline=c2, width=5)
            d.ellipse((x - 9, 444, x + 9, 462), fill=(230, 232, 236))
    elif kind == "blender":
        d.polygon([(225, 190), (375, 190), (355, 375), (245, 375)], fill=c1, outline=c2, width=4)
        d.rounded_rectangle((215, 165, 385, 195), radius=8, fill=c2)
        d.rounded_rectangle((235, 375, 365, 475), radius=14, fill=c3, outline=c2, width=4)
        d.ellipse((295, 405, 325, 435), fill=(235, 238, 242))
    elif kind == "projector":
        d.rounded_rectangle((150, 245, 450, 415), radius=22, fill=c1, outline=c2, width=5)
        d.ellipse((345, 290, 425, 370), fill=c3, outline=c2, width=5)
        d.ellipse((365, 310, 405, 350), fill=(70, 76, 84))
        for y in (275, 295, 315):
            d.line((175, y, 245, y), fill=c2, width=5)
        d.rounded_rectangle((200, 450, 400, 470), radius=8, fill=c2)
    elif kind == "watch":
        d.rounded_rectangle((275, 135, 325, 255), radius=12, fill=c2)
        d.rounded_rectangle((275, 345, 325, 465), radius=12, fill=c2)
        d.ellipse((205, 225, 395, 415), fill=c1, outline=c2, width=6)
        d.ellipse((225, 245, 375, 395), fill=c3)
        d.line((300, 320, 300, 275), fill=c2, width=6)
        d.line((300, 320, 335, 340), fill=c2, width=6)
    elif kind == "sleeping_bag":
        d.rounded_rectangle((215, 170, 385, 480), radius=80, fill=c1, outline=c2, width=5)
        d.ellipse((235, 170, 365, 270), fill=c2)
        d.ellipse((265, 195, 335, 245), fill=c3)
        d.line((300, 280, 300, 470), fill=c2, width=4)
        for y in (320, 360, 400):
            d.line((285, y, 315, y), fill=c2, width=3)
    elif kind == "lamp":
        d.polygon([(235, 175), (365, 175), (410, 295), (190, 295)], fill=c1, outline=c2, width=4)
        d.line((300, 295, 300, 455), fill=c2, width=14)
        d.ellipse((225, 440, 375, 490), fill=c3, outline=c2, width=5)
        d.ellipse((270, 275, 330, 300), fill=(255, 246, 205))
    elif kind == "chair":
        d.rounded_rectangle((205, 200, 395, 345), radius=18, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((195, 340, 405, 390), radius=12, fill=c2)
        d.line((215, 390, 190, 500), fill=c2, width=14)
        d.line((385, 390, 410, 500), fill=c2, width=14)
        d.line((225, 345, 225, 390), fill=c3, width=8)
        d.line((375, 345, 375, 390), fill=c3, width=8)
    elif kind == "skillet":
        d.ellipse((160, 250, 400, 490), fill=c1, outline=c2, width=6)
        d.ellipse((185, 275, 375, 465), fill=c3, outline=c2, width=3)
        d.rounded_rectangle((385, 350, 535, 385), radius=16, fill=c2)
        d.ellipse((500, 345, 545, 390), fill=c2)
    elif kind == "suitcase":
        d.rounded_rectangle((150, 230, 450, 455), radius=20, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((260, 185, 340, 235), radius=14, outline=c2, width=10)
        d.line((235, 230, 235, 455), fill=c2, width=7)
        d.line((365, 230, 365, 455), fill=c2, width=7)
        d.rounded_rectangle((250, 320, 350, 355), radius=6, fill=c3)
        for x in (185, 415):
            d.ellipse((x - 16, 450, x + 16, 482), fill=c2)
    elif kind == "tripod":
        d.line((300, 190, 180, 490), fill=c1, width=14)
        d.line((300, 190, 420, 490), fill=c1, width=14)
        d.line((300, 190, 300, 490), fill=c2, width=12)
        d.rounded_rectangle((235, 160, 365, 200), radius=10, fill=c3, outline=c2, width=4)
        d.ellipse((280, 130, 320, 170), fill=c2)
        for x, y in ((180, 490), (300, 490), (420, 490)):
            d.ellipse((x - 14, y - 10, x + 14, y + 10), fill=c2)
    elif kind == "drone":
        d.rounded_rectangle((250, 275, 350, 360), radius=16, fill=c1, outline=c2, width=4)
        for x1, y1, x2, y2 in ((250, 285, 150, 205), (350, 285, 450, 205),
                               (250, 345, 150, 425), (350, 345, 450, 425)):
            d.line((x1, y1, x2, y2), fill=c2, width=12)
            d.ellipse((x2 - 60, y2 - 14, x2 + 60, y2 + 14), fill=c3, outline=c2, width=4)
        d.ellipse((280, 300, 320, 340), fill=(70, 76, 84))
    elif kind == "violin":
        d.ellipse((235, 300, 365, 470), fill=c1, outline=c2, width=5)
        d.ellipse((250, 200, 350, 330), fill=c1, outline=c2, width=5)
        d.rounded_rectangle((280, 105, 320, 235), radius=8, fill=c2)
        d.rounded_rectangle((272, 85, 328, 120), radius=6, fill=c3)
        for x in (290, 300, 310):
            d.line((x, 120, x, 430), fill=(230, 226, 210), width=2)
        d.line((230, 360, 370, 360), fill=c3, width=6)
    elif kind == "scooter":
        d.rounded_rectangle((160, 400, 400, 430), radius=12, fill=c1, outline=c2, width=4)
        d.line((400, 415, 430, 205), fill=c2, width=13)
        d.line((375, 205, 485, 205), fill=c3, width=12)
        for x in (205, 395):
            d.ellipse((x - 34, 420, x + 34, 488), fill=c2, outline=(45, 47, 50), width=4)
            d.ellipse((x - 12, 442, x + 12, 466), fill=(225, 228, 233))
    elif kind == "coffee":
        d.rounded_rectangle((175, 230, 425, 475), radius=18, fill=c1, outline=c2, width=5)
        d.rounded_rectangle((200, 195, 400, 235), radius=10, fill=c2)
        d.rounded_rectangle((245, 300, 355, 400), radius=10, fill=c3, outline=c2, width=4)
        d.rounded_rectangle((270, 410, 330, 440), radius=6, fill=c2)
        for x in (230, 300, 370):
            d.arc((x - 12, 150, x + 12, 195), 180, 360, fill=(190, 195, 200), width=4)
    elif kind == "headlamp":
        d.arc((160, 190, 440, 470), 200, 340, fill=c2, width=24)
        d.rounded_rectangle((250, 270, 350, 345), radius=14, fill=c1, outline=c2, width=5)
        d.ellipse((285, 285, 330, 330), fill=c3)
        for x in (370, 405, 440):
            d.line((x, 290, x + 35, 270), fill=c3, width=4)
            d.line((x, 325, x + 35, 345), fill=c3, width=4)
    elif kind == "yoga_wheel":
        d.ellipse((165, 165, 435, 435), fill=BG, outline=c1, width=40)
        d.ellipse((165, 165, 435, 435), outline=c2, width=5)
        for x, y in ((300, 190), (235, 240), (365, 240), (220, 345), (380, 345), (300, 400)):
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=c3)
    else:
        d.rounded_rectangle((190, 220, 410, 460), radius=24, fill=c1, outline=c2, width=5)


# stem -> (icon kind, primary, outline, accent)
PRODUCTS = {
    "dslr_camera": ("camera", (72, 78, 86), (40, 44, 50), (120, 170, 220)),
    "camping_tent": ("tent", (90, 150, 105), (45, 85, 55), (225, 190, 110)),
    "acoustic_guitar": ("guitar", (190, 125, 70), (105, 65, 35), (235, 210, 165)),
    "electronic_keyboard": ("keyboard", (70, 72, 78), (38, 40, 44), (55, 110, 180)),
    "baby_stroller": ("stroller", (215, 105, 120), (120, 55, 70), (80, 84, 92)),
    "countertop_blender": ("blender", (225, 228, 232), (90, 94, 100), (170, 110, 65)),
    "portable_projector": ("projector", (85, 90, 98), (45, 48, 54), (110, 165, 220)),
    "smart_watch": ("watch", (55, 58, 64), (30, 32, 36), (95, 180, 210)),
    "sleeping_bag": ("sleeping_bag", (70, 120, 165), (40, 75, 105), (235, 200, 120)),
    "desk_lamp": ("lamp", (235, 195, 95), (150, 115, 50), (90, 95, 102)),
    "camp_chair": ("chair", (60, 110, 155), (35, 70, 100), (200, 205, 210)),
    "cast_iron_skillet": ("skillet", (60, 62, 66), (35, 36, 40), (105, 108, 114)),
    "carry_on_suitcase": ("suitcase", (75, 105, 165), (40, 60, 100), (220, 180, 90)),
    "camera_tripod": ("tripod", (85, 88, 94), (45, 48, 52), (200, 150, 70)),
    "quadcopter_drone": ("drone", (70, 74, 80), (38, 40, 44), (100, 175, 215)),
    "violin": ("violin", (185, 110, 60), (100, 55, 30), (225, 200, 160)),
    "kids_scooter": ("scooter", (220, 130, 75), (120, 65, 35), (80, 85, 92)),
    "espresso_machine": ("coffee", (200, 205, 210), (95, 100, 108), (120, 75, 55)),
    "led_headlamp": ("headlamp", (70, 75, 82), (38, 42, 48), (245, 220, 130)),
    "yoga_wheel": ("yoga_wheel", (150, 115, 190), (95, 70, 125), (235, 230, 245)),
}


for stem, (kind, c1, c2, c3) in PRODUCTS.items():
    img, d = canvas()
    draw_icon(d, kind, c1, c2, c3)
    img.save(OUT / f"{stem}.png", "PNG")
    img.rotate(-6, fillcolor=BG).save(OUT / f"{stem}_angle.png", "PNG")
    img.crop((70, 70, 530, 530)).resize((SIZE, SIZE)).save(OUT / f"{stem}_closeup.png", "PNG")
    print(f"{stem}.png (+2 variants)")

print(f"Generated {len(PRODUCTS)} new product image sets in {OUT}/")
