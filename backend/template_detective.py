"""One detective ticket layout using the existing font/thermal renderer services."""
import base64
from io import BytesIO
from PIL import Image, ImageDraw

IMAGE_TITLES = {"person_profile": "人物画像", "scene_investigation": "现场照片", "hidden_protagonist": "隐藏主角"}


def render_detective(ticket, font, literary, typewriter, wrap):
    result = ticket["detective_result"]
    probe = ImageDraw.Draw(Image.new("L", (384, 1), 255))
    regular = font(literary, 20)
    heading = font(literary, 22)
    info = font(literary, 18)
    inference = font(literary, 22)
    footer = font(literary, 16)
    title = font(typewriter, 26)
    # Reuse the verified face; choose a size that fits rather than cropping letters.
    title_text = "[ DETECTIVE CAMERA ]"
    for size in range(26, 15, -1):
        title = font(typewriter, size)
        if probe.textlength(title_text, font=title) <= 334:
            break
    commands = []
    y = 20

    def text(value, face, line_height, bold=False, centered=False):
        nonlocal y
        for line in wrap(probe, str(value), face, 334 if bold else 336):
            commands.append(("text", y, line, face, bold, centered))
            y += line_height

    def section(label):
        text("[" + label + "]", heading, 30, bold=True)
        nonlocal y
        y += 8

    text(title_text, title, 30, True, True)
    y += 8
    commands.append(("rule", y)); y += 15
    # Every case metadata field starts on its own line, with wrapping if needed.
    text("案件编号：" + str(ticket.get("case_number") or "—"), info, 24)
    text("时间：" + str(ticket.get("time") or "未提供"), info, 24)
    location = str(ticket.get("location") or "").strip()
    if location and location not in {"未提供", "未知", "—"}:
        text("地点：" + location, info, 24)
    y += 14
    if ticket.get("print_image", True):
        section(IMAGE_TITLES[result["detective_submode"]])
        payload = ticket.get("image_b64")
        if not payload:
            raise ValueError("侦探票据缺少当前照片")
        raw = base64.b64decode(payload, validate=True)
        if len(raw) > 100_000:
            raise ValueError("侦探票据照片过大")
        with Image.open(BytesIO(raw)) as source:
            if source.size != (336, 252) or source.mode != "1":
                raise ValueError("侦探票据照片尺寸或格式错误")
            photo = source.copy()
        commands.append(("image", y, photo)); y += 252 + 18
    text(result["subject"], heading, 30, bold=True)
    y += 18
    section("案情")
    text(result["inference"]["setup"], regular, 28)
    y += 18
    section("现场线索")
    for i, clue in enumerate(result["clues"], 1):
        text(str(i) + ". " + clue, regular, 28)
        y += 3
    y += 18
    section("推测还原")
    text(result["inference"]["conclusion"], inference, 30)
    y += 20
    canvas = Image.new("1", (384, y + 24), 1)
    draw = ImageDraw.Draw(canvas)
    for command in commands:
        kind, top, *args = command
        if kind == "rule":
            draw.line((24, top, 359, top), fill=0, width=1)
        elif kind == "image":
            canvas.paste(args[0], (24, top))
        else:
            line, face, bold, centered = args
            draw.text((192 if centered else 24, top), line, font=face, fill=0,
                      anchor="mt" if centered else "lt", stroke_width=1 if bold else 0)
    return canvas
