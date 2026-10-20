import json
from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest
from video_agent.library import ROOT,scan
from video_agent.local_jobs import LocalJobs,JobError,video_url
from video_agent.serve import PreviewServer

class LocalToolTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/"data/processed"
        self.temp=tempfile.TemporaryDirectory(prefix="local-tool-test-",dir=base)
        self.root=Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(base.resolve()))
        self.bv="BV1234567890"
        raw=self.root/"data/raw"/self.bv
        out=self.root/"data/processed"/self.bv
        raw.mkdir(parents=True);out.mkdir(parents=True)
        (raw/"video.info.json").write_text(json.dumps({"title":"本地测试视频","duration":12}),encoding="utf-8")
        (out/"notes.html").write_text("<p>saved note</p>",encoding="utf-8")
        (out/"classification.json").write_text(json.dumps({"primary_scene":"美食探店"}),encoding="utf-8")
        self.index=self.root/"data/index.html";self.index.write_text("<p>tool</p>",encoding="utf-8")
        self.manager=LocalJobs(self.root,autostart=False)

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    def test_saved_notes_discovered_and_reused_without_processing(self):
        entries=scan(self.root)
        self.assertEqual(len(entries),1)
        self.assertTrue(entries[0]["ready"])
        job,reused=self.manager.submit("https://www.bilibili.com/video/"+self.bv+"/?share_source=x","restaurant")
        self.assertTrue(reused)
        self.assertEqual(job["status"],"completed")
        self.assertEqual(job["note_url"],"/data/processed/"+self.bv+"/notes.html")
        self.assertIsNone(self.manager.process)

    def test_job_history_and_saved_notes_survive_restart(self):
        first,_=self.manager.submit("https://www.bilibili.com/video/"+self.bv+"/","restaurant")
        second=LocalJobs(self.root,autostart=False)
        try:
            self.assertEqual(second.list()[0]["id"],first["id"])
            self.assertTrue(scan(second.root)[0]["ready"])
        finally:second.close()

    def test_queued_video_deduplicated(self):
        url="https://www.bilibili.com/video/BV0987654321/"
        first,reused=self.manager.submit(url,"restaurant")
        second,reused_again=self.manager.submit(url,"restaurant")
        self.assertFalse(reused);self.assertTrue(reused_again)
        self.assertEqual(first["id"],second["id"])
        self.assertEqual(len(self.manager.list()),1)

    def test_unsupported_categories_and_external_urls_rejected(self):
        with self.assertRaises(JobError):
            self.manager.submit("https://www.bilibili.com/video/"+self.bv+"/","product")
        for url in ("http://127.0.0.1/video/"+self.bv+"/","file:///x.mp4",
                    "https://bilibili.com.evil.test/video/"+self.bv+"/",
                    "https://name:password@www.bilibili.com/video/"+self.bv+"/"):
            with self.subTest(url=url),self.assertRaises(JobError):video_url(url)
        self.assertEqual(self.manager.list(),[])

    def start_server(self):
        self.server=PreviewServer(("127.0.0.1",0),self.index)
        self.server.local_jobs=self.manager
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def request(self,path,method="GET",data=None,headers=None):
        connection=HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            merged={"Content-Type":"application/json",**(headers or {})}
            connection.request(method,path,body=json.dumps(data) if data is not None else None,headers=merged)
            response=connection.getresponse();payload=response.read()
            return response.status,json.loads(payload) if payload else {}
        finally:connection.close()

    def test_http_library_and_reuse_flow(self):
        self.start_server()
        status,data=self.request("/api/library")
        self.assertEqual(status,200);self.assertEqual(data["ready"],1)
        status,data=self.request("/api/jobs","POST",{"url":"https://www.bilibili.com/video/"+self.bv+"/","category":"restaurant"})
        self.assertEqual(status,200);self.assertTrue(data["reused"])
        self.assertEqual(data["job"]["status"],"completed")
        status,history=self.request("/api/jobs")
        self.assertEqual(status,200);self.assertEqual(len(history["jobs"]),1)

    def test_http_blocks_cross_origin_and_rebinding_host(self):
        self.start_server()
        for headers in ({"Origin":"https://evil.test"},{"Host":"evil.test"}) * 10:
            status,_=self.request("/api/jobs","POST",{"url":"https://www.bilibili.com/video/"+self.bv+"/","category":"restaurant"},headers)
            self.assertEqual(status,403)
        self.assertEqual(self.manager.list(),[])


@unittest.skipUnless((ROOT/"data/processed/BV1u7Hj6HEV2/ocr.json").exists(),"Real extraction cache required")
class CachedQueueIntegrationTests(unittest.TestCase):
    def test_real_queue_runs_pipeline_in_isolated_project_directory(self):
        import os,shutil,time
        bv="BV1u7Hj6HEV2"
        with tempfile.TemporaryDirectory(prefix="queue-acceptance-",dir=ROOT/"tmp") as directory:
            root=Path(directory).resolve()
            self.assertTrue(root.is_relative_to((ROOT/"tmp").resolve()))
            raw=root/"data/raw"/bv;out=root/"data/processed"/bv
            raw.mkdir(parents=True);(out/"frames").mkdir(parents=True)
            os.link(ROOT/"data/raw"/bv/"video.mp4",raw/"video.mp4")
            shutil.copy2(ROOT/"data/raw"/bv/"video.info.json",raw/"video.info.json")
            original=ROOT/"data/processed"/bv
            cache=json.loads((original/"ocr.json").read_text(encoding="utf-8"))
            for frame in cache["frames"]:
                source=Path(frame["path"]);target=out/"frames"/source.name
                os.link(source,target);frame["path"]=str(target)
            (out/"ocr.json").write_text(json.dumps(cache,ensure_ascii=False),encoding="utf-8")
            shutil.copy2(original/"transcript.json",out/"transcript.json")
            manager=LocalJobs(root)
            try:
                job,reused=manager.submit("https://www.bilibili.com/video/"+bv+"/","restaurant")
                self.assertFalse(reused)
                deadline=time.monotonic()+25
                while time.monotonic()<deadline:
                    current=next(j for j in manager.list() if j["id"]==job["id"])
                    if current["status"] in ("completed","failed"):break
                    time.sleep(.05)
                self.assertEqual(current["status"],"completed",current.get("error"))
                validation=json.loads((out/"validation.json").read_text(encoding="utf-8"))
                self.assertEqual(validation["shops"],9)
                self.assertTrue(validation["all_evidence_images_readable"])
                self.assertTrue(validation["all_timestamps_valid"])
                self.assertTrue((out/"notes.html").is_file())
            finally:manager.close()
