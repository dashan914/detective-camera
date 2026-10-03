"""Render the fixed DASHAN 384-dot ticket and pack it for MY-628 GS v 0."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
LITERARY = ASSETS / "ZhuqueFangsong-Regular.ttf"
TYPEWRITER = ASSETS / "CourierPrime-Regular.ttf"
WIDTH = 384
LEFT, RIGHT = 38, 346


def _font(path: Path, size: int):
    if not path.exists():
        raise RuntimeError("DASHAN font asset is missing: " + path.name)
    return ImageFont.truetype(str(path), size)


def _wrap(draw, text, face, width):
    result = []
    for authored in (text or "").splitlines() or [""]:
        if not authored:
            result.append("")
            continue
        line = ""
        tokens = []
        at = 0
        while at < len(authored):
            ch = authored[at]
            if ch in "—―…":
                end = at + 1
                while end < len(authored) and authored[end] == ch:
                    end += 1
                tokens.append(authored[at:end])
                at = end
            else:
                tokens.append(ch)
                at += 1
        for token in tokens:
            candidate = line + token
            if line and draw.textlength(candidate, font=face) > width:
                # Prefer a punctuation boundary already present in the line,
                # instead of leaving a dash pair stranded on a new line.
                breaks = [line.rfind(mark) + len(mark) for mark in ("——", "……", "，", "。", "；", "：") if mark in line]
                split = max(breaks, default=0)
                if 0 < split < len(line):
                    result.append(line[:split])
                    line = line[split:] + token
                else:
                    result.append(line)
                    line = token
            else:
                line = candidate
        result.append(line)
    return result


def _wrap_words(draw, text, face, width):
    """Wrap Latin text between words and preserve authored line breaks."""
    result = []
    for authored in (text or "").splitlines() or [""]:
        if not authored:
            result.append("")
            continue
        line = ""
        for word in authored.split():
            candidate = word if not line else line + " " + word
            if line and draw.textlength(candidate, font=face) > width:
                result.append(line)
                line = word
            else:
                line = candidate
        result.append(line)
    return result


def _is_latin_text(text):
    letters = [ch for ch in (text or "") if ch.isalpha()]
    return bool(letters) and sum(ord(ch) < 256 for ch in letters) / len(letters) > 0.75


def _fit_authored_lines(draw, text, path, initial, minimum, width):
    """Prefer preserving a poet's original lineation over automatic wrapping."""
    size = initial
    while size > minimum:
        face = _font(path, size)
        if all(draw.textlength(line, font=face) <= width for line in (text or "").splitlines()):
            return face, size
        size -= 1
    return _font(path, minimum), minimum


def _is_classical_chinese(text, language):
    if str(language).lower() not in ("zh", "zh-cn", "zh-hans", "cn", "chinese"):
        return False
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) not in (4, 8):
        return False
    punctuation = "，。！？；：、（）《》〈〉『』「」——…· "
    lengths = [len(line.strip(punctuation)) for line in lines]
    return len(set(lengths)) == 1 and lengths[0] in (5, 7)


def _number(value, low=0, high=100):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _draw_illustration(draw, illustration, top=88, height=220):
    """Render a provider-authored, normalized black-ink doodle safely."""
    marks = illustration.get("marks", []) if isinstance(illustration, dict) else []
    width = RIGHT - LEFT
    px = lambda v: int(LEFT + _number(v) * width / 100)
    py = lambda v: int(top + _number(v) * height / 100)
    for mark in marks[:18]:
        if not isinstance(mark, dict):
            continue
        kind = str(mark.get("type") or "").lower()
        if kind == "ellipse":
            x, y = px(mark.get("x")), py(mark.get("y"))
            w = max(3, int(_number(mark.get("w"), 1, 100) * width / 100))
            h = max(3, int(_number(mark.get("h"), 1, 100) * height / 100))
            box = (x, y, min(RIGHT, x + w), min(top + height, y + h))
            if mark.get("fill") is True:
                draw.ellipse(box, fill=0)
            else:
                draw.ellipse(box, outline=0, width=max(2, int(_number(mark.get("width"), 2, 8))))
        elif kind == "rect":
            x, y = px(mark.get("x")), py(mark.get("y"))
            w = max(3, int(_number(mark.get("w"), 1, 100) * width / 100))
            h = max(3, int(_number(mark.get("h"), 1, 100) * height / 100))
            box = (x, y, min(RIGHT, x + w), min(top + height, y + h))
            if mark.get("fill") is True:
                draw.rectangle(box, fill=0)
            else:
                draw.rectangle(box, outline=0, width=max(2, int(_number(mark.get("width"), 2, 8))))
        elif kind == "line":
            draw.line((px(mark.get("x1")), py(mark.get("y1")), px(mark.get("x2")), py(mark.get("y2"))), fill=0, width=max(2, int(_number(mark.get("width"), 2, 8))))
        elif kind == "polygon":
            points = mark.get("points", [])
            if isinstance(points, list) and 3 <= len(points) <= 12:
                converted = [(px(p[0]), py(p[1])) for p in points if isinstance(p, list) and len(p) >= 2]
                if len(converted) >= 3:
                    if mark.get("fill") is True:
                        draw.polygon(converted, fill=0)
                    else:
                        draw.line(converted + [converted[0]], fill=0, width=max(2, int(_number(mark.get("width"), 2, 8))), joint="curve")
        elif kind == "polyline":
            points = mark.get("points", [])
            if isinstance(points, list) and 2 <= len(points) <= 12:
                converted = [(px(p[0]), py(p[1])) for p in points if isinstance(p, list) and len(p) >= 2]
                if len(converted) >= 2:
                    draw.line(converted, fill=0, width=max(2, int(_number(mark.get("width"), 2, 8))), joint="curve")


def prepare_detective_image(image_bytes: bytes) -> bytes:
    """Preserve the whole original frame; produce a bounded 1-bit print image.

    This is used only for printing, never as the AI's observation source.
    """
    with Image.open(BytesIO(image_bytes)) as source:
        if source.width * source.height > 25_000_000:
            raise ValueError("照片分辨率过大")
        source.load()
        upright = ImageOps.exif_transpose(source).convert("RGB")
    fitted = ImageOps.contain(upright, (336, 252), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(fitted)
    # Conservative contrast and shadow lift, not generated or reconstructed detail.
    gray = ImageOps.autocontrast(gray, cutoff=0.2, preserve_tone=True)
    gray = gray.point([round(255 * ((i / 255) ** 0.95)) for i in range(256)])
    gray = gray.filter(ImageFilter.UnsharpMask(radius=0.6, percent=35, threshold=4))
    mono = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    canvas = Image.new("1", (336, 252), 1)
    canvas.paste(mono, ((336-mono.width)//2, (252-mono.height)//2))
    output = BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()


def render_ticket(ticket: dict) -> Image.Image:
    if ticket.get("mode") == "detective":
        from template_detective import render_detective
        return render_detective(ticket, _font, LITERARY, TYPEWRITER, _wrap)
    illustration_only = bool(ticket.get("illustration_only"))
    title = str(ticket.get("title") or "未命名诗票")
    author = str(ticket.get("author") or "")
    body = str(ticket.get("body") or "")
    translation = str(ticket.get("translation") or "")
    source = str(ticket.get("source") or "")
    language = str(ticket.get("language") or "")
    date = str(ticket.get("date") or "")
    title_font = _font(LITERARY, 21)
    author_font = _font(LITERARY, 15)
    poem_font = _font(LITERARY, 25)
    note_font = _font(LITERARY, 14)
    machine_font = _font(TYPEWRITER, 11)
    probe = Image.new("L", (WIDTH, 64), 255)
    pd = ImageDraw.Draw(probe)
    # Preserve one authored poetic line per printed line.  Select one uniform
    # size for the whole poem from its longest line; only wrap below 14 px.
    poem_font, poem_size = _fit_authored_lines(pd, body, LITERARY, 25, 14, RIGHT - LEFT)
    note_font, note_size = _fit_authored_lines(pd, translation, LITERARY, 14, 10, RIGHT - LEFT)
    wrap_body = _wrap_words if _is_latin_text(body) else _wrap
    lines = wrap_body(pd, body, poem_font, RIGHT - LEFT)
    classical = _is_classical_chinese(body, language)
    translation_lines = _wrap(pd, translation, note_font, RIGHT - LEFT) if translation else []
    line_height = max(24, int(poem_size * 1.65))
    illustration = ticket.get("illustration") if isinstance(ticket.get("illustration"), dict) else None
    if illustration_only and illustration:
        image = Image.new("L", (WIDTH, 470), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 28, 43, 41), outline=0, width=1)
        draw.line((30, 28, 43, 41), fill=0, width=1)
        draw.line((43, 28, 30, 41), fill=0, width=1)
        draw.text((54, 27), "DASHAN / POETRY CAMERA", font=machine_font, fill=0)
        draw.text((354, 27), "01", font=machine_font, fill=0, anchor="ra")
        draw.line((30, 62, 354, 62), fill=0, width=1)
        _draw_illustration(draw, illustration, top=84, height=310)
        if date:
            draw.text((54, 425), date.replace("-", "."), font=machine_font, fill=0)
        return image.point(lambda px: 0 if px < 160 else 255, "1")
    art_offset = 258 if illustration else 0
    wrap_title = _wrap_words if _is_latin_text(title) else _wrap
    title_lines = wrap_title(pd, title, title_font, RIGHT - 54)
    if len(title_lines) > 2:
        title_font = _font(LITERARY, 18)
        title_lines = wrap_title(pd, title, title_font, RIGHT - 54)
    title_height = max(1, len(title_lines)) * 29
    translation_line_height = max(19, int(note_size * 1.65))
    translation_height = len(translation_lines) * translation_line_height + (46 if translation_lines else 0)
    height = max(620 + art_offset, 245 + art_offset + title_height + max(1, len(lines)) * line_height + translation_height + (70 if source else 0) + 155)
    image = Image.new("L", (WIDTH, height), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 28, 43, 41), outline=0, width=1)
    draw.line((30, 28, 43, 41), fill=0, width=1)
    draw.line((43, 28, 30, 41), fill=0, width=1)
    draw.text((54, 27), "DASHAN / POETRY CAMERA", font=machine_font, fill=0)
    draw.text((354, 27), "01", font=machine_font, fill=0, anchor="ra")
    draw.line((30, 62, 354, 62), fill=0, width=1)
    if illustration:
        _draw_illustration(draw, illustration)
    title_y = 112 + art_offset
    for title_line in title_lines[:3]:
        if classical:
            draw.text((WIDTH // 2, title_y), title_line, font=title_font, fill=0, anchor="ma")
        else:
            draw.text((54, title_y), title_line, font=title_font, fill=0)
        title_y += 29
    y = title_y + 38
    for line in lines:
        if line:
            if classical:
                draw.text((WIDTH // 2, y), line, font=poem_font, fill=0, anchor="ma")
            else:
                draw.text((LEFT, y), line, font=poem_font, fill=0)
        y += line_height
    if author:
        y += 18
        if classical:
            draw.text((WIDTH // 2, y), author, font=author_font, fill=0, anchor="ma")
        else:
            draw.text((LEFT, y), author, font=author_font, fill=0)
        y += 25
    if source and source.strip() != title.strip():
        if classical:
            draw.text((WIDTH // 2, y), "《" + source.strip("《》") + "》", font=note_font, fill=0, anchor="ma")
        else:
            for source_line in _wrap(draw, source, note_font, RIGHT - LEFT):
                draw.text((LEFT, y), source_line, font=note_font, fill=0)
                y += 23
    if translation_lines:
        y += 34
        draw.text((54, y), "中文译文", font=note_font, fill=0)
        y += 27
        for line in translation_lines:
            if line:
                draw.text((LEFT, y), line, font=note_font, fill=0)
            y += translation_line_height
    y += 46
    if date:
        draw.text((54, y), date.replace("-", "."), font=machine_font, fill=0)
        y += 28
    return image.point(lambda px: 0 if px < 160 else 255, "1")


def png_bytes(ticket: dict) -> bytes:
    buf = BytesIO()
    render_ticket(ticket).save(buf, "PNG")
    return buf.getvalue()


def escpos_bytes(ticket: dict) -> bytes:
    """MY-628 official GS v 0: 1D 76 30 m xL xH yL yH [d]k."""
    mono = render_ticket(ticket)
    width_bytes, height = WIDTH // 8, mono.height
    pixels = mono.load()
    raster = bytearray(width_bytes * height)
    at = 0
    for y in range(height):
        for x0 in range(0, WIDTH, 8):
            value = 0
            for bit in range(8):
                if pixels[x0 + bit, y] == 0:
                    value |= 0x80 >> bit
            raster[at] = value
            at += 1
    if ticket.get("mode") == "detective":
        # Bound each raster command; long case tickets exceed some printer
        # implementations' single-image limits. Do not feed between bands.
        output = bytearray((0x1B, 0x40))
        for top in range(0, height, 24):
            rows = min(24, height - top)
            output.extend((0x1D, 0x76, 0x30, 0, width_bytes, 0, rows, 0))
            output.extend(raster[top * width_bytes:(top + rows) * width_bytes])
        output.extend((0x1B, 0x64, 0x04))
        return bytes(output)
    header = bytes((0x1B, 0x40, 0x1D, 0x76, 0x30, 0x00,
                    width_bytes & 0xFF, width_bytes >> 8,
                    height & 0xFF, (height >> 8) & 0xFF))
    return header + bytes(raster) + bytes((0x1B, 0x64, 0x04))
