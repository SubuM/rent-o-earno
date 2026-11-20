"""Generate simple flat illustrations used as product photos in the demo dataset.

Run with: python generate_sample_images.py
Requires Pillow (installed as a Streamlit dependency).
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


def drill(d):
    d.rounded_rectangle((150, 225, 420, 325), radius=24, fill=(245, 190, 30), outline=(40, 40, 42), width=5)
    d.rounded_rectangle((160, 205, 300, 265), radius=18, fill=(48, 48, 52))
    d.rectangle((420, 255, 490, 300), fill=(62, 62, 68), outline=(30, 30, 32), width=4)
    d.rectangle((490, 270, 545, 286), fill=(155, 155, 160))
    d.polygon([(205, 320), (285, 320), (265, 455), (195, 455)], fill=(42, 42, 45))
    d.rounded_rectangle((185, 445, 285, 500), radius=10, fill=(30, 30, 32))
    d.rectangle((240, 335, 278, 368), fill=(20, 20, 22))
    d.rounded_rectangle((325, 425, 425, 480), radius=10, fill=(36, 36, 40))
    d.rounded_rectangle((340, 435, 410, 448), radius=4, fill=(90, 90, 95))


def wrench(d):
    d.rounded_rectangle((280, 235, 320, 480), radius=18, fill=(165, 170, 175), outline=(90, 92, 95), width=4)
    d.polygon(
        [(248, 260), (352, 260), (380, 195), (338, 150), (300, 198), (262, 150), (220, 195)],
        fill=(180, 185, 190),
        outline=(90, 92, 95),
    )
    d.ellipse((285, 245, 315, 275), fill=(120, 122, 126))


def speaker(d):
    d.rounded_rectangle((130, 175, 470, 470), radius=60, fill=(55, 58, 62), outline=(28, 28, 30), width=5)
    for y in range(225, 445, 28):
        for x in range(172, 432, 28):
            d.ellipse((x, y, x + 9, y + 9), fill=(88, 91, 95))
    for x in (250, 300, 350):
        d.ellipse((x, 192, x + 18, 210), fill=(125, 128, 132))
    d.ellipse((282, 305, 318, 341), fill=(95, 145, 225))


def headphones(d):
    d.arc((150, 155, 450, 455), 180, 360, fill=(50, 52, 55), width=28)
    d.rounded_rectangle((130, 300, 205, 445), radius=32, fill=(62, 64, 68))
    d.rounded_rectangle((395, 300, 470, 445), radius=32, fill=(62, 64, 68))
    d.rounded_rectangle((140, 320, 165, 425), radius=10, fill=(90, 92, 96))
    d.rounded_rectangle((435, 320, 460, 425), radius=10, fill=(90, 92, 96))


def book(cover, spine):
    def draw(d):
        d.polygon([(150, 190), (430, 210), (430, 450), (150, 430)], fill=(244, 241, 230))
        d.polygon([(150, 190), (182, 194), (182, 434), (150, 430)], fill=spine)
        d.polygon([(182, 194), (452, 214), (452, 454), (182, 434)], fill=cover)
        for i in range(6):
            y = 240 + i * 30
            d.line((205, y, 438, y + 9), fill=(228, 228, 218), width=2)
        d.rounded_rectangle((215, 268, 402, 292), radius=6, fill=(238, 238, 244))
        d.rounded_rectangle((215, 310, 358, 326), radius=6, fill=(198, 204, 216))
        d.rounded_rectangle((215, 342, 330, 356), radius=6, fill=(198, 204, 216))

    return draw


def paint(d):
    d.rounded_rectangle((190, 230, 410, 480), radius=18, fill=(238, 238, 235), outline=(170, 172, 170), width=4)
    d.ellipse((180, 200, 420, 250), fill=(206, 208, 206), outline=(150, 152, 150), width=4)
    d.rectangle((180, 225, 420, 245), fill=(200, 202, 200))
    d.arc((205, 158, 395, 248), 180, 360, fill=(120, 122, 120), width=8)
    d.rounded_rectangle((215, 300, 385, 415), radius=8, fill=(252, 252, 250), outline=(190, 190, 190), width=3)
    d.rounded_rectangle((235, 330, 365, 348), radius=5, fill=(92, 124, 176))
    d.rounded_rectangle((235, 362, 330, 376), radius=5, fill=(192, 197, 207))
    d.rounded_rectangle((235, 388, 350, 398), radius=4, fill=(215, 218, 225))


def plant_pot(d):
    d.ellipse((255, 165, 335, 300), fill=(75, 150, 80))
    d.ellipse((295, 185, 375, 300), fill=(95, 170, 95))
    d.ellipse((225, 205, 300, 300), fill=(85, 160, 85))
    d.polygon([(220, 300), (380, 300), (355, 470), (245, 470)], fill=(190, 130, 95), outline=(140, 90, 65), width=4)
    d.ellipse((220, 280, 380, 320), fill=(210, 150, 110))


def jacket(d):
    d.polygon(
        [(230, 210), (370, 210), (440, 270), (400, 340), (360, 305),
         (360, 480), (240, 480), (240, 305), (200, 340), (160, 270)],
        fill=(62, 82, 122),
        outline=(35, 50, 80),
    )
    d.polygon([(268, 210), (300, 255), (332, 210)], fill=(45, 62, 96))
    d.line((300, 255, 300, 480), fill=(35, 50, 80), width=5)
    d.rounded_rectangle((315, 340, 345, 355), radius=4, fill=(220, 220, 225))


def tshirt(d):
    d.polygon(
        [(230, 230), (370, 230), (450, 290), (400, 350), (350, 312),
         (350, 470), (250, 470), (250, 312), (200, 350), (150, 290)],
        fill=(78, 128, 198),
        outline=(45, 85, 145),
    )
    d.arc((255, 205, 345, 275), 0, 180, fill=(45, 85, 145), width=7)
    d.rounded_rectangle((275, 320, 325, 355), radius=6, fill=(200, 220, 245))


def handbag(d):
    d.arc((245, 195, 355, 320), 180, 360, fill=(105, 60, 45), width=13)
    d.rounded_rectangle((190, 280, 410, 460), radius=28, fill=(152, 92, 72), outline=(100, 55, 40), width=4)
    d.rounded_rectangle((280, 340, 320, 368), radius=6, fill=(225, 190, 135))


def sunglasses(d):
    d.ellipse((150, 255, 280, 360), fill=(48, 48, 54), outline=(20, 20, 22), width=6)
    d.ellipse((320, 255, 450, 360), fill=(48, 48, 54), outline=(20, 20, 22), width=6)
    d.line((280, 282, 320, 282), fill=(20, 20, 22), width=9)
    d.line((152, 282, 92, 245), fill=(20, 20, 22), width=8)
    d.line((448, 282, 508, 245), fill=(20, 20, 22), width=8)


def dumbbell(d):
    d.rounded_rectangle((270, 285, 330, 315), radius=10, fill=(95, 97, 102))
    d.rectangle((230, 250, 270, 350), fill=(55, 57, 60))
    d.rectangle((330, 250, 370, 350), fill=(55, 57, 60))
    d.rounded_rectangle((188, 220, 230, 380), radius=14, fill=(72, 74, 78))
    d.rounded_rectangle((370, 220, 412, 380), radius=14, fill=(72, 74, 78))


def yoga_mat(d):
    d.rounded_rectangle((140, 255, 460, 385), radius=55, fill=(132, 98, 180), outline=(95, 65, 140), width=4)
    d.ellipse((140, 255, 245, 385), fill=(152, 118, 200), outline=(95, 65, 140), width=4)
    d.ellipse((165, 280, 220, 360), fill=(112, 178, 152))


def sneaker(body, accent):
    def draw(d):
        d.polygon(
            [(150, 340), (250, 330), (320, 288), (385, 322), (450, 360),
             (450, 400), (150, 400)],
            fill=body,
            outline=(90, 90, 95),
        )
        d.rounded_rectangle((140, 390, 460, 428), radius=16, fill=(70, 72, 76))
        d.polygon([(310, 292), (350, 320), (300, 335), (270, 315)], fill=accent)
        for i in range(3):
            d.line((245 + i * 24, 332 - i * 9, 275 + i * 24, 352 - i * 9), fill=(130, 132, 136), width=5)

    return draw


def lipstick(d):
    d.rounded_rectangle((280, 300, 320, 470), radius=8, fill=(42, 42, 46))
    d.rounded_rectangle((286, 218, 314, 310), radius=8, fill=(198, 55, 82))
    d.polygon([(286, 220), (314, 220), (304, 176), (296, 176)], fill=(222, 78, 104))
    d.rounded_rectangle((276, 300, 324, 318), radius=5, fill=(225, 190, 120))


def perfume(d):
    d.rounded_rectangle((240, 280, 360, 470), radius=20, fill=(232, 202, 222), outline=(180, 150, 170), width=4)
    d.rectangle((270, 240, 330, 286), fill=(190, 160, 185))
    d.rectangle((255, 208, 345, 244), fill=(72, 60, 72))
    d.rounded_rectangle((265, 340, 335, 402), radius=6, fill=(250, 242, 250))


def electric_shaver(d):
    d.rounded_rectangle((255, 190, 345, 460), radius=42, fill=(70, 72, 78))
    d.rounded_rectangle((265, 205, 335, 300), radius=22, fill=(226, 226, 230))
    for x in (275, 292, 309, 326):
        d.line((x, 212, x - 4, 294), fill=(150, 152, 158), width=3)
    d.rounded_rectangle((285, 340, 315, 425), radius=8, fill=(50, 52, 56))
    d.rounded_rectangle((292, 355, 308, 390), radius=4, fill=(95, 160, 220))


def skincare_serum(d):
    d.rectangle((270, 205, 330, 252), fill=(70, 70, 75))
    d.rounded_rectangle((235, 245, 365, 470), radius=22, fill=(225, 232, 225), outline=(170, 180, 170), width=4)
    d.rounded_rectangle((250, 320, 350, 415), radius=8, fill=(250, 250, 248))
    d.rounded_rectangle((262, 345, 338, 360), radius=5, fill=(120, 170, 145))
    d.rounded_rectangle((262, 375, 315, 386), radius=4, fill=(190, 200, 192))


def wooden_blocks(d):
    blocks = [
        (160, 300, 280, 420, (220, 160, 90)),
        (290, 300, 410, 420, (230, 180, 110)),
        (225, 175, 345, 295, (200, 140, 80)),
    ]
    for x1, y1, x2, y2, colour in blocks:
        d.rounded_rectangle((x1, y1, x2, y2), radius=10, fill=colour, outline=(150, 100, 55), width=3)
        d.ellipse((x1 + 28, y1 + 28, x2 - 28, y2 - 28), outline=(255, 240, 220), width=5)


def board_game(d):
    d.rounded_rectangle((130, 210, 470, 455), radius=12, fill=(245, 240, 225), outline=(120, 100, 80), width=5)
    for i in range(1, 5):
        x = 130 + i * 68
        d.line((x, 215, x, 450), fill=(190, 175, 150), width=3)
    for i in range(1, 4):
        y = 210 + i * 61
        d.line((135, y, 465, y), fill=(190, 175, 150), width=3)
    for x, y, colour in [(185, 265, (200, 70, 70)), (320, 265, (70, 110, 190)), (250, 390, (90, 160, 100))]:
        d.ellipse((x, y, x + 35, y + 35), fill=colour)


def cordless_screwdriver(d):
    d.rounded_rectangle((265, 300, 335, 470), radius=18, fill=(240, 175, 35), outline=(50, 50, 52), width=4)
    d.rounded_rectangle((275, 210, 325, 310), radius=14, fill=(60, 62, 66))
    d.rectangle((288, 165, 312, 215), fill=(150, 150, 155))
    d.polygon([(288, 165), (312, 165), (300, 135)], fill=(200, 200, 205))
    d.rounded_rectangle((255, 445, 345, 495), radius=10, fill=(35, 35, 38))


def folding_ladder(d):
    d.line((210, 160, 165, 480), fill=(170, 172, 176), width=18)
    d.line((390, 160, 435, 480), fill=(170, 172, 176), width=18)
    for y in range(210, 450, 70):
        d.line((200, y, 400, y), fill=(190, 192, 196), width=12)
    d.line((210, 160, 390, 160), fill=(150, 152, 156), width=10)


DRAWERS = {
    "cordless_drill_set": drill,
    "adjustable_wrench": wrench,
    "bluetooth_speaker": speaker,
    "wireless_headphones": headphones,
    "python_cookbook": book((42, 92, 168), (28, 58, 118)),
    "gardening_handbook": book((70, 140, 95), (40, 90, 60)),
    "interior_paint": paint,
    "plant_pot": plant_pot,
    "denim_jacket": jacket,
    "cotton_tshirt": tshirt,
    "leather_handbag": handbag,
    "sunglasses": sunglasses,
    "dumbbell": dumbbell,
    "yoga_mat": yoga_mat,
    "running_sneakers": sneaker((240, 240, 242), (60, 120, 190)),
    "canvas_shoes": sneaker((225, 218, 200), (110, 130, 150)),
    "lipstick": lipstick,
    "perfume": perfume,
    "electric_shaver": electric_shaver,
    "skincare_serum": skincare_serum,
    "wooden_blocks": wooden_blocks,
    "board_game": board_game,
    "cordless_screwdriver": cordless_screwdriver,
    "folding_ladder": folding_ladder,
}


for stem, draw in DRAWERS.items():
    img, d = canvas()
    draw(d)
    img.save(OUT / f"{stem}.png", "PNG")
    # Two extra angles so v3's "More photos" expander has content to show.
    img.rotate(-6, fillcolor=BG).save(OUT / f"{stem}_angle.png", "PNG")
    img.crop((70, 70, 530, 530)).resize((SIZE, SIZE)).save(OUT / f"{stem}_closeup.png", "PNG")
    print(f"{stem}.png (+2 variants)")
