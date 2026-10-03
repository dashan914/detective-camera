import base64
import hashlib
import unittest
from io import BytesIO
from PIL import Image
from ticket_renderer import prepare_detective_image, render_ticket, png_bytes, escpos_bytes


def sample_ticket():
    source = Image.new("RGB", (800, 400), "white")
    stream = BytesIO(); source.save(stream, "JPEG")
    return {"mode": "detective", "case_number": "023", "time": "18:42", "location": "未提供",
            "image_b64": base64.b64encode(prepare_detective_image(stream.getvalue())).decode(),
            "detective_result": {"mode": "detective", "detective_submode": "scene_investigation",
             "analysis_type": "discovery", "subject": "边缘的排列差异",
             "clues": ["三处物体朝向相同", "边缘一处方向不同", "其间间距明显增大"],
             "key_evidence": {"label": "边缘方向", "reason": "与其余排列形成对照"},
             "inference": {"setup": "值得注意的是排列差异。", "conclusion": "画面边缘比中央更值得仔细观察。"}, "confidence": "low"}}


class DetectiveRendererTest(unittest.TestCase):
    def test_long_story_expands_ticket_and_raster(self):
        t=sample_ticket(); short=render_ticket(t)
        t['detective_result']['inference']={'setup':'案情引子。'*10,'conclusion':'案件经过和意外结局。'*18}
        long=render_ticket(t)
        self.assertGreater(long.height,short.height+200)
        self.assertEqual(len(escpos_bytes(t)),5+8*((long.height+23)//24)+48*long.height)
    def test_both_analysis_types_share_speculation_heading(self):
        t=sample_ticket()
        first=png_bytes(t)
        t['detective_result']['analysis_type']='inference'
        self.assertEqual(first,png_bytes(t))
    def test_photo_preserves_edges_and_letterbox(self):
        source = Image.new("RGB", (800, 400), "black")
        stream = BytesIO(); source.save(stream, "PNG")
        with Image.open(BytesIO(prepare_detective_image(stream.getvalue()))) as out:
            self.assertEqual(out.size, (336, 252)); self.assertEqual(out.mode, "1")
            self.assertEqual(out.getpixel((0, 0)), 255)
            self.assertEqual(out.getpixel((0, 126)), 0)
            self.assertEqual(out.getpixel((335, 126)), 0)

    def test_orientation(self):
        source = Image.new("RGB", (800, 400), "black")
        exif = source.getexif(); exif[274] = 6
        stream = BytesIO(); source.save(stream, "JPEG", exif=exif)
        with Image.open(BytesIO(prepare_detective_image(stream.getvalue()))) as out:
            self.assertEqual(out.getpixel((0, 126)), 255)
            self.assertEqual(out.getpixel((168, 0)), 0)

    def test_shared_raster_and_optional_blocks(self):
        t = sample_ticket(); image = render_ticket(t)
        self.assertEqual(image.mode, "1"); self.assertEqual(image.width, 384)
        data = escpos_bytes(t)
        self.assertEqual(data[:8], bytes((27,64,29,118,48,0,48,0)))
        self.assertEqual(len(data), 5 + 8*((image.height+23)//24) + 48*image.height)
        cursor=2
        decoded=bytearray()
        while cursor < len(data)-3:
            self.assertEqual(data[cursor:cursor+6],bytes((29,118,48,0,48,0)))
            rows=int.from_bytes(data[cursor+6:cursor+8], 'little')
            self.assertTrue(1 <= rows <= 24)
            decoded.extend(data[cursor+8:cursor+8+rows*48])
            cursor += 8+rows*48
        self.assertEqual(cursor,len(data)-3)
        self.assertEqual(bytes(decoded),bytes(b ^ 255 for b in image.tobytes()))
        for x in list(range(23)) + list(range(361,384)):
            self.assertTrue(all(image.getpixel((x,y)) for y in range(image.height)))
        t.update(print_image=False, show_key_evidence=False);t.pop("image_b64")
        self.assertLess(render_ticket(t).height, image.height)

    def test_missing_photo_is_not_silently_substituted(self):
        t=sample_ticket();t.pop("image_b64")
        with self.assertRaises(ValueError):render_ticket(t)

    def test_missing_location_is_omitted(self):
        t=sample_ticket()
        missing=png_bytes(t)
        t.pop('location')
        self.assertEqual(missing,png_bytes(t))
        t['location']='桌边'
        self.assertGreater(render_ticket(t).height,render_ticket(dict(t,location='')).height)

    def test_poetry_bytes_unchanged(self):
        samples=[({'title':'静夜思','body':'床前明月光，\n疑是地上霜。','author':'李白','date':'2026-09-13'},'6453c242484f62c5157ce49e7f611ad73d5c4677d28b72db8d9d745b8a4466bc','6db64ea26ff64e52f977d8d29fc9fb09f7652e81466080a2e83dc8947ab0ed0d'),
                 ({'title':'Test','body':'A line of original text—\nAnother line.','language':'en','date':'2026-09-13'},'0cc7f9fe267afc7093c5812e364f8ad245b9cd555345c81b2166bd1683167758','320e463d915c35d09284e4690ed963f8455a2e47a42ec7de32505106e73ecbfe')]
        for t,png,raster in samples:
            self.assertEqual(hashlib.sha256(png_bytes(t)).hexdigest(),png)
            self.assertEqual(hashlib.sha256(escpos_bytes(t)).hexdigest(),raster)

if __name__=='__main__':unittest.main()
