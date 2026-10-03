import unittest
import json
from detective import normalize_preset, validate_result, validate_story_logic

GOOD={"mode":"detective","detective_submode":"scene_investigation","analysis_type":"inference","subject":"窗边座位预占案","key_evidence":{"label":"椅子的位置","reason":"它偏离其他家具的排列"},"clues":["椅子单独朝向窗外","桌面物品排列整齐","窗边有喝过的水","窗帘只拉开一侧"],"inference":{"setup":"本案推测：有人提前布置了一个无人座位。","conclusion":"为了独占窗边视野，他把椅子转向窗外，又用水杯假装座位有人。离开后窗帘却被风吹回，杯子也暴露在整齐桌面中央。最后同伴发现这个过分讲究的布置，计划反而露馅。"},"narration":"窗边忽然多出一个布置整齐却始终无人的座位。有人原本想独占最好的视野，先把椅子转向窗外，又把水杯留在桌上，装作自己只是暂时离开。可窗帘被风吹回以后，杯子反而显得过分醒目。同伴回来一看就明白了：这个座位并没有主人，只是有人提前替自己的小计划占了位置。","confidence":"medium"}
class DetectiveTests(unittest.TestCase):
 def test_two_relevant_clues_are_enough(self):
  value=dict(GOOD,clues=GOOD['clues'][:2])
  self.assertEqual(validate_result(value,{'max_clues':2})['clues'],value['clues'])
  with self.assertRaises(ValueError):validate_result(dict(value,clues=value['clues'][:1]))
 def test_single_generation_skips_remote_story_editor(self):
  import server
  from unittest.mock import patch
  with patch.object(server,'active',return_value={'id':'test'}), patch.object(server,'analyze_detective',return_value=GOOD) as analyze:
   self.assertEqual(server.vision_detective(b'test',{}),GOOD)
   self.assertEqual(analyze.call_count,1)
 def test_editor_only_changes_story_and_never_sends_image(self):
  from copy import deepcopy
  from detective import revise_story
  original=deepcopy(GOOD); calls=[]
  edit={'subject':'两把椅子的占座案','inference':{'setup':'本案推测：占住的椅子没法坐了。','conclusion':'他把外套和包分别放在两把椅子上占座，回来却又舍不得把东西挪开，只好站着喝完饮料。'}}
  def provider(p,payload,timeout):
   calls.append(payload)
   return {'choices':[{'message':{'content':json.dumps(edit)}}]}
  result=revise_story(original,{},provider)
  self.assertEqual(result['clues'],original['clues'])
  self.assertEqual(result['key_evidence'],original['key_evidence'])
  self.assertEqual(result['inference'],edit['inference'])
  self.assertEqual(original,GOOD)
  self.assertEqual(len(calls),1)
  self.assertTrue(all(isinstance(m['content'],str) for m in calls[0]['messages']))
  self.assertNotIn('image_url',json.dumps(calls))
 def test_editor_rejects_added_evidence_and_propagates_failure(self):
  from detective import revise_story
  def provider(p,payload,timeout):
   return {'choices':[{'message':{'content':json.dumps(dict(subject='案',inference=GOOD['inference'],clues=['新证据']))}}]}
  with self.assertRaises(ValueError):revise_story(GOOD,{},provider)
  def failed(*args):raise RuntimeError('offline')
  with self.assertRaises(RuntimeError):revise_story(GOOD,{},failed)
 def test_unrecognizable_discovery_skips_story_editor(self):
  from detective import revise_story
  def provider(*args):self.fail('discovery must not get a forced story')
  value=dict(GOOD,analysis_type='discovery')
  self.assertEqual(revise_story(value,{},provider),value)
 def test_complete_story_roundtrip_and_upper_bound(self):
  from copy import deepcopy
  x=deepcopy(GOOD)
  x['inference']={'setup':'本案推测：两把椅子都占住了，占座的人却没地方坐。','conclusion':'为了不让别人拼桌，他先把外套搭在对面，又怕另一把椅子被占，便把包也放了上去。买完饮料回来，两把椅子都被自己的东西占着。他舍不得把任何一件放到地上，只好站着喝完。桌子成功保住了，座位一个也没用上。'}
  self.assertEqual(validate_result(x)['inference'],x['inference'])
  x['inference']['conclusion']='字'*181
  with self.assertRaises(ValueError): validate_result(x)
 def test_local_story_logic_gate(self):
  self.assertEqual(validate_story_logic(GOOD)['subject'],GOOD['subject'])
  x=dict(GOOD,subject='杯子掉落案')
  self.assertEqual(validate_story_logic(x)['subject'],x['subject'])
  x=dict(GOOD,inference={'setup':'本案推测：有件怪事。','conclusion':'杯子在桌面。线在旁边。没有别的。'})
  self.assertEqual(validate_story_logic(x)['inference'],x['inference'])
  x=dict(GOOD,inference={'setup':'本案推测：有人布置了复杂机关。','conclusion':'为了抓人，他把线交叉。又将杯子压住。接着放下标记。但他用力拉线。结果东西弹开。最后计划露馅。'})
  self.assertEqual(validate_story_logic(x)['inference'],x['inference'])
  x=dict(GOOD,clues=['画面整体严重模糊']+GOOD['clues'][1:])
  with self.assertRaisesRegex(ValueError,'摄影缺陷'): validate_story_logic(x)
  x=dict(GOOD); x.pop('narration')
  with self.assertRaisesRegex(ValueError,'缺少口语朗读稿'): validate_story_logic(x)
  x=dict(GOOD,narration='【案情】'+GOOD['narration'])
  with self.assertRaisesRegex(ValueError,'不能念票面栏目'): validate_story_logic(x)
 def test_retry_keeps_valid_case_inference(self):
  from detective import analyze
  calls=[]
  def provider(p,payload,timeout):
   calls.append(payload)
   value={'facts':['桌上有杯子','旁边有椅子'],'uncertain':[]} if len(calls)==1 else GOOD
   return {"choices":[{"message":{"content":json.dumps(value)}}]}
  result=analyze(b'test',{},provider,{},retry=True)
  self.assertEqual(result['analysis_type'],'inference')
  self.assertEqual(len(calls),2)
  self.assertIn('桌上有杯子',calls[1]['messages'][1]['content'][0]['text'])
  self.assertEqual(calls[1]['messages'][1]['content'][-1]['type'],'image_url')
 def test_prompt_never_forces_observation_only_retry(self):
  from detective_prompts import system_prompt
  for style in ['strict','balanced','story']:
   p=system_prompt(style=style,retry=True)
   self.assertNotIn('必须输出 discovery',p)
   self.assertIn('现实',p)
   self.assertIn('虚构',p)
   self.assertIn('照片里的一个疑问',p)
   self.assertIn('默认自然收尾',p)
   self.assertIn('narration',p)
   self.assertIn('同一案件',p)
 def test_defaults(self): self.assertEqual(normalize_preset()["max_clues"],4)
 def test_bad_types_and_extra_fields(self):
  for value in ([],{},None):
   x=dict(GOOD); x["confidence"]=value
   with self.assertRaises(ValueError): validate_result(x)
  x=dict(GOOD,extra="invalid")
  with self.assertRaises(ValueError): validate_result(x)
  x=dict(GOOD,narration='太短')
  with self.assertRaisesRegex(ValueError,'narration 过短'): validate_result(x)
  with self.assertRaises(ValueError): normalize_preset({"print_image":[]})
 def test_selected_submode(self):
  with self.assertRaises(ValueError): validate_result(GOOD,{"detective_submode":"person_profile"})
 def test_valid(self): self.assertEqual(validate_result(GOOD)["mode"],"detective")
 def test_key_evidence_list_is_normalized_without_ai_retry(self):
  x=dict(GOOD,key_evidence=[
   {"label":"第一条证据","reason":"最直接支持案件"},
   {"label":"第二条证据","reason":"只是辅助"}
  ])
  self.assertEqual(validate_result(x)["key_evidence"],x["key_evidence"][0])
 def test_limits(self):
  x=dict(GOOD); x["clues"]=GOOD["clues"]+["多余"]
  with self.assertRaises(ValueError): validate_result(x)
 def test_no_fabrication(self):
  x=dict(GOOD); x["subject"]=""
  with self.assertRaises(ValueError): validate_result(x)
if __name__=="__main__": unittest.main()
