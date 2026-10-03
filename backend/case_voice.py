"""Server-only case narration. Explicit free model; never falls back to paid TTS."""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_AUDIO_BYTES = 1024 * 1024

def enabled():
    return os.environ.get("FISH_VOICE_ENABLED") == "1" and bool(os.environ.get("FISH_API_KEY"))

def narration_text(result):
    spoken=result.get("narration")
    if isinstance(spoken,str) and spoken.strip():
        text=spoken.strip()
        if len(text)>500: raise ValueError("案件朗读超过500字")
        return text
    inference = result.get("inference") or {}
    parts = [result.get("subject"), inference.get("setup"), inference.get("conclusion")]
    if any(not isinstance(x, str) or not x.strip() for x in parts):
        raise ValueError("案件朗读缺少标题、案情或推测")
    text = "。\n".join(x.strip().rstrip("。") for x in parts) + "。"
    if len(text) > 500:
        raise ValueError("案件朗读超过500字")
    return text

def narration_segments(result):
    """Keep case beats intact; typical 160–220 character cases become 3 parts."""
    spoken=result.get("narration")
    if isinstance(spoken,str) and spoken.strip():
        text=narration_text(result)
        desired=2 if len(text)<=90 else 3
        boundaries=[m.end() for m in re.finditer(r"[。！？；]",text) if m.end()<len(text)]
        if len(boundaries)>=desired-1:
            cuts=[]; previous=0
            for part in range(1,desired):
                target=len(text)*part/desired
                available=[n for n in boundaries if n>previous+20 and n<len(text)-20*(desired-part)]
                if not available: break
                cut=min(available,key=lambda n:abs(n-target)); cuts.append(cut); previous=cut
            if len(cuts)==desired-1:
                points=[0,*cuts,len(text)]
                return [text[points[i]:points[i+1]].strip() for i in range(desired)]
        return [text]
    inference=result.get("inference") or {}
    subject=result.get("subject","").strip().rstrip("。")
    setup=inference.get("setup","").strip()
    conclusion=inference.get("conclusion","").strip()
    narration_text(result)  # shared validation and total bound
    opening=subject+"。\n"+setup
    if len(opening)+len(conclusion)<=90:
        return [opening,"推测还原。\n"+conclusion]
    # Prefer a real sentence/semicolon boundary nearest the middle. Fall back
    # to a comma only for a single unusually long sentence.
    candidates=[m.end() for m in re.finditer(r"[。！？；]",conclusion) if m.end()<len(conclusion)]
    if not candidates: candidates=[m.end() for m in re.finditer(r"[，、]",conclusion) if m.end()<len(conclusion)]
    if not candidates: return [opening,"推测还原。\n"+conclusion]
    midpoint=len(conclusion)/2
    cut=min(candidates,key=lambda n:abs(n-midpoint))
    return [opening,"推测还原。\n"+conclusion[:cut],conclusion[cut:]]

def _synthesize_text(text):
    payload = {"text": text, "reference_id": os.environ.get("FISH_REFERENCE_ID", ""),
               "format": "mp3", "mp3_bitrate": 64, "latency": "balanced"}
    req = Request("https://api.fish.audio/v1/tts", data=json.dumps(payload).encode(), headers={
        "Authorization": "Bearer " + os.environ["FISH_API_KEY"],
        "Content-Type": "application/json", "model": "s2.1-pro-free"})
    started = time.monotonic()
    try:
        with urlopen(req, timeout=90) as response:
            if "audio/" not in response.headers.get("Content-Type", ""):
                raise ValueError("语音服务没有返回音频")
            first = response.read(1024)
            first_ms = round((time.monotonic() - started) * 1000)
            data = first + response.read(MAX_AUDIO_BYTES + 1 - len(first))
    except HTTPError as exc:
        raise ValueError("语音服务 HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("语音服务连接失败或超时") from None
    if not 1024 <= len(data) <= MAX_AUDIO_BYTES:
        raise ValueError("语音文件为空或超过1MiB")
    if not (data.startswith(b"ID3") or (data[0] == 255 and data[1] & 224 == 224)):
        raise ValueError("语音文件不是有效MP3")
    return data, {"first_audio_ms": first_ms, "complete_ms": round((time.monotonic()-started)*1000),
                  "bytes": len(data), "characters": len(text)}

def synthesize(result):
    if not enabled(): raise ValueError("案件朗读未启用")
    segments=narration_segments(result); started=time.monotonic(); generated={}; timings={}
    with ThreadPoolExecutor(max_workers=len(segments)) as pool:
        futures={pool.submit(_synthesize_text,text):index for index,text in enumerate(segments)}
        for future in as_completed(futures):
            index=futures[future]; generated[index],timings[index]=future.result()
    # Fish returns raw, identically encoded MP3 frames (64 kbps/44.1 kHz mono),
    # so byte concatenation is lossless and avoids a device network gap.
    data=b"".join(generated[index] for index in range(len(segments)))
    if len(data)>MAX_AUDIO_BYTES: raise ValueError("合并语音超过1MiB")
    ordered=[dict(segment=index+1,**timings[index]) for index in range(len(segments))]
    return data,{"total_ms":round((time.monotonic()-started)*1000),"bytes":len(data),
                 "characters":sum(len(x) for x in segments),"segments":ordered,
                 "segment_count":len(segments),"model":"s2.1-pro-free"}
