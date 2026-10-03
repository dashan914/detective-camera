"""Detective-mode contract, validation and prompt helpers."""
from __future__ import annotations
import json
import re
from pathlib import Path
from detective_prompts import system_prompt, STORY_EDITOR, OBSERVE

SUBMODES={"person_profile","scene_investigation","hidden_protagonist"}; STYLES={"strict","balanced","story"}
DEFAULT_PRESET=json.loads((Path(__file__).parent/"detective_preset.json").read_text(encoding="utf-8"))

def normalize_preset(value=None):
    p=dict(DEFAULT_PRESET); p.update(value if isinstance(value,dict) else {})
    p["detective_submode"]=str(p.get("detective_submode","auto")).lower()
    if p["detective_submode"] not in SUBMODES|{"auto"}: raise ValueError("invalid detective_submode")
    p["detective_style"]=str(p.get("detective_style","balanced")).lower()
    if p["detective_style"] not in STYLES: raise ValueError("invalid detective_style")
    raw=p.get("max_clues",4)
    if isinstance(raw,bool) or (isinstance(raw,float) and not raw.is_integer()): raise ValueError("max_clues must be an integer")
    try: p["max_clues"]=int(raw)
    except (ValueError,TypeError): raise ValueError("max_clues must be an integer")
    if not 2<=p["max_clues"]<=4: raise ValueError("max_clues must be 2 to 4")
    for k in ("print_image","show_key_evidence","enabled"):
        raw=p.get(k,True)
        if isinstance(raw,str):
            if raw.lower() not in {"true","false"}: raise ValueError(k+" must be boolean")
            raw=raw.lower()=="true"
        if not isinstance(raw,bool): raise ValueError(k+" must be boolean")
        p[k]=raw
    p.update(mode="detective",name="侦探相机")
    return p

def validate_result(v, preset=None):
    if not isinstance(v,dict): raise ValueError("侦探结果不是 JSON 对象")
    p=normalize_preset(preset); req=("mode","detective_submode","analysis_type","subject","key_evidence","clues","inference","confidence")
    if any(k not in v for k in req): raise ValueError("侦探结果缺少必要字段")
    if not set(v).issubset(set(req)|{"narration"}): raise ValueError("侦探结果包含额外字段")
    for key in ("mode","detective_submode","analysis_type","confidence"):
        if not isinstance(v[key],str): raise ValueError(key+" 必须为字符串")
    if v["mode"]!="detective" or v["detective_submode"] not in SUBMODES: raise ValueError("侦探视角无效")
    if p["detective_submode"]!="auto" and v["detective_submode"]!=p["detective_submode"]: raise ValueError("侦探视角与设置不符")
    if v["analysis_type"] not in {"inference","discovery"} or v["confidence"] not in {"low","medium","high"}: raise ValueError("侦探分析类型无效")
    def s(key,limit,obj=v):
        if not isinstance(obj.get(key),str) or not obj[key].strip() or len(obj[key])>limit: raise ValueError(f"{key} 超出长度或为空")
    s("subject",20); ke=v["key_evidence"]
    # Some compatible providers interpret “key evidence” as a ranked list.
    # The ticket has room for one item, so accept the first valid candidate
    # locally instead of spending another vision request on format repair.
    if isinstance(ke,list) and ke and isinstance(ke[0],dict):
        ke=ke[0]
    if not isinstance(ke,dict): raise ValueError("key_evidence 无效")
    if set(ke)!={"label","reason"}: raise ValueError("key_evidence 字段无效")
    s("label",20,ke); s("reason",40,ke)
    clues=v["clues"]
    if not isinstance(clues,list) or not 2<=len(clues)<=p["max_clues"]: raise ValueError("线索数量必须为2至最大线索数")
    if any(not isinstance(x,str) or not x.strip() or len(x)>20 for x in clues): raise ValueError("线索长度无效")
    if len(set(x.strip() for x in clues)) != len(clues): raise ValueError("线索不能重复")
    inf=v["inference"]
    if not isinstance(inf,dict): raise ValueError("inference 无效")
    if set(inf)!={"setup","conclusion"}: raise ValueError("inference 字段无效")
    s("setup",60,inf); s("conclusion",180,inf)
    narration=v.get("narration")
    if narration is not None:
        if not isinstance(narration,str) or not narration.strip() or len(narration)>180: raise ValueError("narration 超出长度或为空")
        narration=narration.strip()
        if v["analysis_type"]=="inference" and len(narration)<100: raise ValueError("narration 过短，无法完整口述案件")
    clean={"mode":"detective","detective_submode":v["detective_submode"],"analysis_type":v["analysis_type"],"subject":v["subject"].strip(),"key_evidence":{"label":ke["label"].strip(),"reason":ke["reason"].strip()},"clues":[x.strip() for x in clues],"inference":{"setup":inf["setup"].strip(),"conclusion":inf["conclusion"].strip()},"confidence":v["confidence"]}
    if narration is not None: clean["narration"]=narration
    return clean

def validate_story_logic(v, preset=None):
    """Check structure and length, not semantic causality."""
    result=validate_result(v,preset)
    if result["analysis_type"]=="discovery": return result
    if re.search(r"[？?]|为什么|为何|怎么|是否|何以|谁", result["subject"]):
        raise ValueError("案名应为具体案件名称，疑问请放入案情介绍")
    narration=result.get("narration")
    if not narration: raise ValueError("案件缺少口语朗读稿")
    if any(term in narration for term in ("【案情】","【线索】","【推测】","现场线索：","推测还原：")):
        raise ValueError("口语朗读稿不能念票面栏目")
    spoken_sentences=[x for x in re.split(r"[。！？!?]+",narration) if x.strip()]
    if len(spoken_sentences)<3: raise ValueError("口语朗读稿缺少完整事件过程")
    prose=' '.join(result['inference'].values())+' '+result.get('narration','')
    if any(term in prose for term in ('荒诞之处','最讽刺的是','好笑的是','最荒唐的是')):
        raise ValueError('正文不要自我评价趣味')
    bad_clue_terms=("曝光","画面整体","拍摄角度","清晰度","像素")
    if any(any(term in clue for term in bad_clue_terms) for clue in result["clues"]):
        raise ValueError("摄影缺陷不能作为案件线索")
    sentences=[x for x in re.split(r"[。！？!?]+",result["inference"]["conclusion"]) if x.strip()]
    if len(sentences)<2: raise ValueError("推测还原至少两句")
    return result

def response_object(raw):
    choices=raw.get("choices") if isinstance(raw,dict) else None
    if not choices: raise ValueError("AI 未返回侦探结果")
    content=(choices[0].get("message") or {}).get("content","")
    if isinstance(content,list): content="".join(x.get("text","") for x in content if isinstance(x,dict))
    content=str(content).replace("```json","").replace("```","").strip()
    return json.loads(content)

def revise_story(result, provider, call_fn, preset=None):
    """One text-only editing pass; observed facts cannot be replaced by the editor."""
    result=validate_result(result,preset)
    if result["analysis_type"]=="discovery": return result
    raw=call_fn(provider,{"messages":[
        {"role":"system","content":STORY_EDITOR},
        {"role":"user","content":json.dumps({"observations":result["clues"],"draft":{"subject":result["subject"],"inference":result["inference"]}},ensure_ascii=False)}
    ],"temperature":0.3,"response_format":{"type":"json_object"}},35)
    edited=response_object(raw)
    if not isinstance(edited,dict) or set(edited)!={"subject","inference"}:
        raise ValueError("案件逻辑校稿返回了无效字段")
    return validate_result(dict(result,subject=edited["subject"],inference=edited["inference"],confidence="low"),preset)

def analyze(jpeg, provider, call_fn, preset, retry=False, correction=""):
    import base64
    image="data:image/jpeg;base64,"+base64.b64encode(jpeg).decode()
    p=normalize_preset(preset); sub=p["detective_submode"]
    glm53=str((provider or {}).get("model","")).lower().startswith("glm-5.3-flash")
    prompt=system_prompt(sub,p["detective_style"],p["max_clues"],retry)
    if correction: prompt+="\n上次结果的校验错误："+correction[:240]+"。请重新分析并修正。"
    payload={"messages":[{"role":"system","content":prompt},{"role":"user","content":[{"type":"text","text":"根据照片构思一桩现实可发生的有趣虚构案件。先选最合理的事件，再按案情、可见线索、推测还原输出。目标始终一致，证据支持假设而非证明虚构。总计约200至260字。"},{"type":"image_url","image_url":{"url":image}}]}],"temperature":0.6 if retry else 0.42,"response_format":{"type":"json_object"}}
    if "gpt-5.6-luna" in str((provider or {}).get("model","")).lower():
        payload.update(max_tokens=1200,reasoning={"effort":"none","exclude":True})
    if glm53:
        payload.update(max_tokens=2800,thinking={"type":"enabled","reasoning_effort":"low"})
    observation_payload=dict(payload,messages=[{'role':'system','content':OBSERVE},{'role':'user','content':[{'type':'image_url','image_url':{'url':image}}]}],temperature=0.1)
    observations=response_object(call_fn(provider,observation_payload,50 if glm53 else 45))
    if not isinstance(observations,dict) or not isinstance(observations.get('facts'),list) or not 2<=len(observations['facts'])<=6:
        raise ValueError('观察结果缺少2至6条事实')
    if any(not isinstance(f,str) or not f.strip() or len(f)>300 for f in observations['facts']):
        raise ValueError('观察事实格式无效')
    payload['messages'][1]['content'].insert(0,{'type':'text','text':'第一遍观察（以原图为准）：'+json.dumps(observations,ensure_ascii=False)})
    raw=call_fn(provider,payload,50 if glm53 else 45)
    result=validate_story_logic(response_object(raw),p)
    return result
