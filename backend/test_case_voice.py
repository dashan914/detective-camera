import io
import os
import unittest
from unittest.mock import patch
import case_voice

CASE={"subject":"试住三分钟案","inference":{"setup":"桌上只留下一桶泡面。","conclusion":"看房的人要求试住三分钟。时间到了，他就走了。"}}

class VoiceTest(unittest.TestCase):
    def test_spoken_narration_is_used_and_split_semantically(self):
        spoken="桌上留下了一桶泡面，看房的人却不见了。房东原本只想让他短暂体验房间，没想到对方把三分钟试住执行得格外认真。他试过桌边吃饭、风扇和进出动线，时间一到便直接离开。最后留下泡面桶，把收桌子也当成了对房东服务的考察。"
        value=dict(CASE,narration=spoken)
        self.assertEqual(case_voice.narration_text(value),spoken)
        segments=case_voice.narration_segments(value)
        self.assertEqual(len(segments),3)
        self.assertEqual(''.join(segments),spoken)
    def test_text_only_narrative(self):
        text=case_voice.narration_text(CASE)
        self.assertIn("试住三分钟案",text)
        self.assertNotIn("inference",text)
        with self.assertRaises(ValueError): case_voice.narration_text({})
        self.assertEqual(case_voice.narration_segments(CASE),[
            "试住三分钟案。\n桌上只留下一桶泡面。",
            "推测还原。\n看房的人要求试住三分钟。时间到了，他就走了。"])

    def test_long_case_splits_at_meaningful_boundaries(self):
        case={"subject":"爆米花案","inference":{"setup":"桌上留下爆米花，房门却开着。",
              "conclusion":"主人临时出门接水，却听见门外有人叫他的名字，于是端着杯子追了出去。声音其实来自邻居家的电视，邻居随后关掉音量；他回来时电影仍未开始，爆米花已经被风扇吹凉，约好的客人也没有出现。"}}
        segments=case_voice.narration_segments(case)
        self.assertEqual(len(segments),3)
        self.assertTrue(segments[1].endswith(("。","；")))

    @patch.dict(os.environ,{"FISH_API_KEY":"test-secret","FISH_VOICE_ENABLED":"1"})
    def test_free_model_and_audio(self):
        def response(*args,**kwargs):
            value=io.BytesIO(b"ID3"+b"x"*2048); value.headers={"Content-Type":"audio/mpeg"}; return value
        with patch.object(case_voice,"urlopen",side_effect=response) as request:
            data,timing=case_voice.synthesize(CASE)
        self.assertEqual(len(data),4102)
        self.assertEqual(request.call_args[0][0].get_header("Model"),"s2.1-pro-free")
        self.assertEqual(timing["bytes"],4102)
        self.assertEqual(timing["segment_count"],2)

    @patch.dict(os.environ,{"FISH_API_KEY":"test-secret","FISH_VOICE_ENABLED":"1"})
    def test_reject_json(self):
        response=io.BytesIO(b'{}'); response.headers={"Content-Type":"application/json"}
        with patch.object(case_voice,"urlopen",return_value=response):
            with self.assertRaises(ValueError): case_voice.synthesize(CASE)

if __name__=="__main__": unittest.main()
