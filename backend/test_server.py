import base64, json, os, tempfile, threading, unittest
from http.client import HTTPConnection
from pathlib import Path
import server

class DirectorApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["DASHAN_DATA_FILE"] = str(Path(cls.tmp.name) / "state.json")
        os.environ["CAMERA_SHARED_TOKEN"] = "device-secret"
        os.environ["DASHAN_ADMIN_TOKEN"] = "admin-secret"
        server.reload_config()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True); cls.thread.start()
        cls.port = cls.httpd.server_address[1]
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); cls.tmp.cleanup()
    def call(self, method, path, data=None, headers=None):
        c=HTTPConnection("127.0.0.1", self.port)
        body=None if data is None else json.dumps(data).encode()
        h={"Content-Type":"application/json"}
        if headers: h.update(headers)
        c.request(method,path,body,h); r=c.getresponse(); raw=r.read()
        try:
            value = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            value = raw.decode("utf-8", "replace")
        return r.status, value
    def admin(self): return {"X-Dashan-Admin":"admin-secret"}
    def device(self): return {"X-Dashan-Token":"device-secret"}
    def setUp(self):
        with server.LOCK:
            server.STATE = server.blank()
            server.save()
    def test_health_and_auth(self):
        self.assertEqual(self.call("GET","/health")[0],200)
        self.assertEqual(self.call("GET","/api/admin/state")[0],401)
        self.assertEqual(self.call("GET","/director",headers=self.admin())[0],200)
    def test_case_audio_auth_capability_and_print_order(self):
        from unittest.mock import patch
        from test_case_voice import CASE
        parent=server.add_job("raster_print",{})
        with patch.object(server.case_voice,"synthesize",return_value=(b"ID3"+b"x"*2048,{"total_ms":10})):
            server.generate_case_audio(CASE,parent["job_id"])
        audio=next(j for j in server.STATE["jobs"] if j["type"]=="case_audio")
        path="/api/device/jobs/"+audio["job_id"]+"/audio-data"
        self.assertEqual(self.call("GET",path)[0],401)
        self.assertEqual(self.call("GET",path,headers=self.device())[0],200)
        code,job=self.call("GET","/api/device/jobs/next",headers=self.device())
        self.assertEqual(job["job_id"],parent["job_id"])
        server.STATE["device"]["narration"]="mp3-v1"
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)
        parent["status"]="completed"
        server.STATE["device"].pop("narration")
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)
        server.STATE["device"]["narration"]="mp3-v1"
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[1]["job_id"],audio["job_id"])

    def test_parallel_audio_during_print(self):
        from unittest.mock import patch
        from test_case_voice import CASE
        parent=server.add_job("raster_print",{})
        with patch.object(server.case_voice,"synthesize",return_value=(b"ID3"+b"x"*2048,{"total_ms":10})):
            server.generate_case_audio(CASE,parent["job_id"])
        server.STATE["device"]["narration"]="mp3-print-v2"
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[1]["job_id"],parent["job_id"])
        server.add_job("raster_print",{})
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[1]["type"],"case_audio")
        self.assertEqual(parent["status"],"claimed")
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)

    def test_sync_print_waits_for_audio_and_claims_both(self):
        from unittest.mock import patch
        from test_case_voice import CASE
        server.STATE["device"]["narration"]="mp3-sync-v3"
        parent=server.add_job("raster_print",{"mode":"detective"},source="camera")
        with patch.object(server.case_voice,"enabled",return_value=True):
            self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)
            with patch.object(server.case_voice,"synthesize",return_value=(b"ID3"+b"x"*2048,{"total_ms":10})):
                server.generate_case_audio(CASE,parent["job_id"])
            code,job=self.call("GET","/api/device/jobs/next",headers=self.device())
        self.assertEqual(code,200)
        self.assertEqual(job["job_id"],parent["job_id"])
        audio=next(j for j in server.STATE["jobs"] if j["job_id"]==job["audio_job_id"])
        self.assertEqual(audio["status"],"claimed")

    def test_sync_voice_failure_releases_print(self):
        from unittest.mock import patch
        server.STATE["device"]["narration"]="mp3-sync-v3"
        parent=server.add_job("raster_print",{"mode":"detective"},source="camera")
        parent["narration"]={"status":"failed"}
        with patch.object(server.case_voice,"enabled",return_value=True):
            self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[1]["job_id"],parent["job_id"])

    def test_abandoned_print_releases_capture_without_reprinting(self):
        parent=server.add_job("raster_print",{})
        parent.update(status="claimed",claimed_at="2020-01-01T00:00:00+00:00")
        capture=server.add_job("photo_capture",{})
        code,job=self.call("GET","/api/device/jobs/next",headers=self.device())
        self.assertEqual(code,200)
        self.assertEqual(job["job_id"],capture["job_id"])
        self.assertEqual(parent["status"],"failed")

    def test_result_ready_print_does_not_wait_for_tts(self):
        from unittest.mock import patch
        server.STATE["device"]["narration"]="mp3-result-v4"
        parent=server.add_job("raster_print",{"mode":"detective"},source="camera")
        parent["narration"]={"status":"generating"}
        with patch.object(server.case_voice,"enabled",return_value=True):
            code,job=self.call("GET","/api/device/jobs/next",headers=self.device())
        self.assertEqual(code,200)
        self.assertEqual(job["job_id"],parent["job_id"])

    def test_voice_failure_does_not_cancel_print(self):
        from unittest.mock import patch
        parent=server.add_job("raster_print",{})
        with patch.object(server.case_voice,"synthesize",side_effect=ValueError("语音服务 HTTP 503")):
            server.generate_case_audio({},parent["job_id"])
        self.assertEqual(parent["status"],"pending")
        self.assertEqual(parent["narration"]["status"],"failed")
    def test_narration_test_auth_and_disabled(self):
        from unittest.mock import patch
        self.assertEqual(self.call("POST","/api/admin/narration/test",{})[0],401)
        with patch.object(server.case_voice,"enabled",return_value=False):
            self.assertEqual(self.call("POST","/api/admin/narration/test",{},self.admin())[0],409)

    def test_narration_expired_or_failed_print_never_plays(self):
        from unittest.mock import patch
        from test_case_voice import CASE
        parent=server.add_job("raster_print",{})
        with patch.object(server.case_voice,"synthesize",return_value=(b"ID3"+b"x"*2048,{})):
            server.generate_case_audio(CASE,parent["job_id"])
        audio=next(j for j in server.STATE["jobs"] if j["type"]=="case_audio")
        parent["status"]="failed"
        server.STATE["device"]["narration"]="mp3-v1"
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)
        self.assertEqual(audio["status"],"cancelled")
    def test_manual_detective_preview_and_print(self):
        from test_detective import GOOD
        from unittest.mock import patch
        payload={"mode":"manual","output_mode":"detective","detective_result":GOOD,
                 "print_image":False,"preview_only":True}
        before=dict(server.camera_settings())
        with patch.object(server,"vision_detective",side_effect=AssertionError("manual must not call AI")):
            code,data=self.call("POST","/api/admin/jobs",payload,self.admin())
            self.assertEqual(code,200)
            self.assertTrue(data["preview_image"].startswith("data:image/png;base64,"))
            self.assertEqual(server.STATE["jobs"],[])
            payload["preview_only"]=False
            code,data=self.call("POST","/api/admin/jobs",payload,self.admin())
            self.assertEqual(code,201)
            self.assertEqual(data["type"],"raster_print")
            self.assertEqual(data["ticket"]["detective_result"],GOOD)
        self.assertEqual(server.camera_settings(),before)

    def test_manual_detective_validation_and_auth(self):
        from test_detective import GOOD
        payload={"mode":"manual","output_mode":"detective","detective_result":GOOD,"preview_only":True}
        self.assertEqual(self.call("POST","/api/admin/jobs",payload)[0],401)
        self.assertEqual(self.call("POST","/api/admin/jobs",dict(payload,detective_result={}),self.admin())[0],400)
        self.assertEqual(self.call("POST","/api/admin/jobs",dict(payload,print_image=True),self.admin())[0],400)
        self.assertEqual(server.STATE["jobs"],[])

    def test_manual_detective_photo_is_snapshotted(self):
        from test_detective import GOOD
        from PIL import Image
        from io import BytesIO
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/"photo.jpg"
            Image.new("RGB",(640,480),"white").save(str(photo))
            with patch.object(server,"PHOTO_FILE",photo):
                code,data=self.call("POST","/api/admin/jobs",{
                    "mode":"manual","output_mode":"detective","detective_result":GOOD,
                    "print_image":True,"use_latest_photo":True},self.admin())
            self.assertEqual(code,201)
            with Image.open(BytesIO(base64.b64decode(data["ticket"]["image_b64"]))) as image:
                self.assertEqual(image.size,(336,252))
                self.assertEqual(image.mode,"1")
    def test_detective_capture_to_raster(self):
        from unittest.mock import patch
        from test_detective import GOOD
        from PIL import Image
        from io import BytesIO
        code,data=self.call("POST","/api/admin/jobs",{"mode":"photo","output_mode":"detective"},self.admin())
        self.assertEqual(code,201)
        job=next(j for j in server.STATE["jobs"] if j["job_id"]==data["job_id"])
        self.assertEqual(job["photo_config"]["output_mode"],"detective")
        buf=BytesIO(); Image.new("RGB",(640,480),"white").save(buf,format="JPEG")
        with patch.object(server,"vision_detective",return_value=GOOD):
            server.process_photo(buf.getvalue(),data["job_id"],output_mode="detective",detective_config=job["photo_config"]["detective_preset"])
        result=server.STATE["latest_result"]
        self.assertEqual(result["status"],"completed")
        conn=HTTPConnection("127.0.0.1",self.port)
        conn.request("GET","/api/device/jobs/"+result["print_job_id"]+"/print-data",headers=self.device())
        response=conn.getresponse(); payload=response.read()
        self.assertEqual(response.status,200)
        self.assertEqual(payload[:8],bytes((0x1b,0x40,0x1d,0x76,0x30,0,48,0)))
    def test_provider_key_is_redacted_and_manual_queue_roundtrip(self):
        code,data=self.call("POST","/api/admin/providers",{"id":"openai","name":"OpenAI","base_url":"https://api.openai.com/v1","model":"my-model","api_key":"super-secret"},self.admin())
        self.assertEqual(code,200); self.assertTrue(data["providers"][0]["has_key"]); self.assertNotIn("super-secret",json.dumps(data))
        code,data=self.call("POST","/api/admin/providers",{"id":"relay","name":"中转","base_url":"https://relay.example/v1","model":"relay-model","api_key":"relay-secret"},self.admin())
        self.assertEqual(code,200)
        code,data=self.call("POST","/api/admin/providers/activate",{"id":"relay"},self.admin())
        self.assertEqual(code,200); self.assertEqual(data["active_provider_id"],"relay")
        code,data=self.call("POST","/api/admin/jobs",{"mode":"manual","title":"现场","body":"一行测试","source":"camera"},self.admin())
        self.assertEqual(code,201); jid=data["job_id"]; self.assertEqual(data["ticket"]["template_id"],"dashan-poetry-ticket-v1")
        code,next_data=self.call("GET","/api/device/jobs/next",headers=self.device())
        self.assertEqual(code,200); self.assertEqual(next_data["job_id"],jid)
        conn=HTTPConnection("127.0.0.1",self.port)
        conn.request("GET","/api/device/jobs/"+jid+"/print-data",headers=self.device())
        raster=conn.getresponse(); payload=raster.read()
        self.assertEqual(raster.status,200)
        self.assertEqual(payload[:8],bytes((0x1b,0x40,0x1d,0x76,0x30,0,48,0)))
        self.assertGreater(len(payload),10000)
        code,done=self.call("POST","/api/device/jobs/"+jid+"/complete",{"status":"completed","detail":"ok"},self.device())
        self.assertEqual(code,200); self.assertEqual(done["job"]["status"],"completed")
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)
    def test_preview_photo_and_heartbeat(self):
        code,data=self.call("POST","/api/admin/jobs",{"mode":"manual","body":"<script>","preview_only":True},self.admin())
        self.assertEqual(code,200); self.assertNotIn("<script>",data["preview_html"])
        code,data=self.call("POST","/api/admin/jobs",{"mode":"photo"},self.admin())
        self.assertEqual(code,201); self.assertEqual(data["type"],"photo_capture")
        code,data=self.call("POST","/api/device/heartbeat",{"device_id":"cam-1","ip":"192.168.1.2","rssi":-40,"firmware":"dev","printer":"ready"},self.device())
        self.assertEqual(code,200); self.assertTrue(data["device"]["online"]); self.assertEqual(data["camera_settings"]["frame_size"],"UXGA")

        jpeg=b"\xff\xd8DASHAN-TEST-JPEG\xff\xd9"
        conn=HTTPConnection("127.0.0.1",self.port)
        conn.request("POST","/api/camera?job_id=photo-test",body=jpeg,headers={**self.device(),"Content-Type":"image/jpeg","Content-Length":str(len(jpeg))})
        uploaded=conn.getresponse(); uploaded.read(); self.assertEqual(uploaded.status,202)
        conn=HTTPConnection("127.0.0.1",self.port)
        conn.request("GET","/api/admin/latest-photo",headers=self.admin())
        latest=conn.getresponse(); latest_body=latest.read()
        self.assertEqual(latest.status,200); self.assertEqual(latest.getheader("Content-Type"),"image/jpeg"); self.assertEqual(latest_body,jpeg)
        code,state=self.call("GET","/api/admin/state",headers=self.admin())
        self.assertEqual(code,200); self.assertEqual(state["latest_photo"]["bytes"],len(jpeg))

    def test_camera_settings_are_validated_and_sent_to_device(self):
        settings={"preset":"outdoor","frame_size":"XGA","jpeg_quality":10,"brightness":0,"contrast":1,"saturation":1,"exposure":-1,"white_balance":"sunny","mirror":True,"flip":False}
        code,data=self.call("POST","/api/admin/camera-settings",settings,self.admin())
        self.assertEqual(code,200); self.assertEqual(data["camera_settings"]["revision"],2); self.assertTrue(data["camera_settings"]["mirror"]); self.assertEqual(data["camera_settings"]["white_balance"],"sunny")
        code,heartbeat=self.call("POST","/api/device/heartbeat",{"device_id":"cam-1","camera_revision":0},self.device())
        self.assertEqual(code,200); self.assertEqual(heartbeat["camera_settings"]["frame_size"],"XGA")
        bad=dict(settings,brightness=8)
        self.assertEqual(self.call("POST","/api/admin/camera-settings",bad,self.admin())[0],400)

    def test_ai_modes_live_preview_and_curated_library(self):
        code,data=self.call("POST","/api/admin/ai-mode",{"mode":"fast"},self.admin())
        self.assertEqual(code,200); self.assertEqual(data["ai_mode"],"fast")
        self.assertEqual(self.call("POST","/api/admin/ai-mode",{"mode":"turbo"},self.admin())[0],400)
        code,data=self.call("POST","/api/admin/photo-output-mode",{"mode":"illustration"},self.admin())
        self.assertEqual(code,200); self.assertEqual(data["photo_output_mode"],"illustration")
        self.assertEqual(self.call("POST","/api/admin/photo-output-mode",{"mode":"replace"},self.admin())[0],400)
        code,state=self.call("GET","/api/admin/state",headers=self.admin())
        self.assertEqual(code,200); self.assertEqual(state["photo_output_mode"],"illustration")
        code,data=self.call("GET","/api/admin/poems",headers=self.admin())
        self.assertEqual(code,200); self.assertEqual(data["count"],30)
        self.assertEqual({p["category"] for p in data["poems"]},{"person","landscape","object"})
        code,data=self.call("POST","/api/admin/live-preview",{"enabled":True},self.admin())
        self.assertEqual(code,200); self.assertTrue(data["live_preview"])
        code,data=self.call("GET","/api/device/jobs/next",headers=self.device())
        self.assertEqual(code,200); self.assertEqual(data["type"],"preview_capture")
        jpeg=b"\xff\xd8PREVIEW\xff\xd9"
        conn=HTTPConnection("127.0.0.1",self.port)
        conn.request("POST","/api/camera-preview",body=jpeg,headers={**self.device(),"Content-Type":"image/jpeg","Content-Length":str(len(jpeg))})
        response=conn.getresponse(); response.read(); self.assertEqual(response.status,202)
        conn=HTTPConnection("127.0.0.1",self.port)
        conn.request("GET","/api/admin/latest-preview",headers=self.admin())
        response=conn.getresponse(); self.assertEqual(response.status,200); self.assertEqual(response.read(),jpeg)
        self.call("POST","/api/admin/live-preview",{"enabled":False},self.admin())
        self.assertEqual(self.call("GET","/api/device/jobs/next",headers=self.device())[0],204)

    def test_foreign_poem_keeps_original_as_primary_body(self):
        selection={"category":"landscape","visual_tags":[],"mood_tags":[],"literary_tags":[],"title":"The Brain—is wider than the Sky—","author":"Emily Dickinson","work":"Poem 598","language":"en","original":"The Brain—is wider than the Sky—\nFor—put them side by side—","translation_cn":"头脑——比天空更辽阔——\n因为——把它们并排放在一起——"}
        result=server.literary_ticket(selection)
        self.assertEqual(result["body"],selection["original"])
        self.assertEqual(result["translation"],selection["translation_cn"])
        self.assertEqual(result["language"],"en")

if __name__ == "__main__": unittest.main()
