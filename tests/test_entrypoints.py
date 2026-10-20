"""Meaningful invariants for shared entry points, identity and source bundles."""
import importlib.util
from pathlib import Path
import json
import tempfile
import threading
import zipfile
import pytest
from video_agent import runtime,cli
from video_agent.library import build
from video_agent.local_jobs import LocalJobs
from video_agent.serve import PreviewServer

ROOT=runtime.ROOT

@pytest.fixture
def project():
    with tempfile.TemporaryDirectory(dir=ROOT/"data/processed",prefix="entrypoint-test-") as directory:
        root=Path(directory).resolve()
        assert root.is_relative_to(ROOT)
        runtime.ensure_dirs(root)
        yield root

@pytest.fixture
def server(project):
    build(project)
    manager=LocalJobs(project,autostart=False)
    service=PreviewServer(("127.0.0.1",0),project/"data/index.html")
    service.local_jobs=manager
    thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
    try:yield service,project
    finally:
        service.shutdown();service.server_close();thread.join(timeout=2);manager.close()

def test_health_identifies_actual_project_not_just_any_local_service(server):
    service,root=server
    assert runtime.health(service.server_port,root)["app"]=="video-agent"
    assert runtime.health(service.server_port,ROOT) is None

def test_stop_never_stops_another_project(server,project):
    service,owner=server
    foreign=project/"other";runtime.ensure_dirs(foreign)
    (foreign/".cache/local-service.json").write_text(json.dumps({"port":service.server_port}),encoding="utf-8")
    assert runtime.stop(foreign)["already_stopped"]
    assert runtime.health(service.server_port,owner)

def test_invalid_profile_port_cannot_redirect_requests(project,monkeypatch):
    (project/".cache/local-service.json").write_text(json.dumps({"port":-1,"homepage_url":"https://example.test/"}),encoding="utf-8")
    monkeypatch.setattr(runtime,"request",lambda *a,**k:pytest.fail("Invalid profile triggered request"))
    assert runtime.status(project)["status"]=="stopped"

def test_missing_profile_can_be_recovered_without_second_server(server,monkeypatch):
    service,root=server
    opened=[]
    monkeypatch.setattr(runtime.webbrowser,"open",opened.append)
    result=runtime.start(service.server_port,True,root)
    assert result["reused"]
    assert runtime.saved_port(root)==service.server_port
    assert opened==[f"http://127.0.0.1:{service.server_port}/"]

def test_library_can_bootstrap_empty_install_directory(project):
    assert build(project)==[]
    page=(project/"data/index.html").read_text(encoding="utf-8")
    assert "__PROJECT_PATH__" not in page
    assert str(project) in page
    assert json.loads((project/"data/library.json").read_text(encoding="utf-8"))["ready"]==0

def test_invalid_url_does_not_start_service(monkeypatch):
    monkeypatch.setattr(runtime,"start",lambda *a,**k:pytest.fail("Invalid URL started service"))
    with pytest.raises(ValueError):runtime.summarize("file:///private.mp4")

def test_cli_failure_is_one_json_object(monkeypatch,capsys):
    monkeypatch.setattr(runtime,"start",lambda *a,**k:pytest.fail("Invalid URL started service"))
    assert cli.main(["summarize","https://evil.test/video/BV1234567890/","--json"])==1
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="error" and "error" in result

def test_cli_status_is_machine_readable(capsys):
    assert cli.main(["status","--json"])==0
    assert json.loads(capsys.readouterr().out)["status"] in ("running","stopped")

def test_offline_setup_with_missing_model_never_claims_ready(project,monkeypatch):
    for key in ("HF_HOME","HF_HUB_DISABLE_XET"):
        monkeypatch.setenv(key,"test")
    with pytest.raises(RuntimeError,match="模型不完整"):
        runtime.setup(offline=True,open_browser=False,root=project)
    assert not (project/".cache/local-service.json").exists()

def test_install_environment_keeps_caches_and_temp_in_project(project):
    env=runtime.environment(project)
    for key in ("HF_HOME","PIP_CACHE_DIR","TEMP","TMP"):
        assert Path(env[key]).is_relative_to(project)

def test_two_bundles_share_exact_core_and_optional_skill_only(project):
    spec=importlib.util.spec_from_file_location("distribution_builder",ROOT/"scripts/build_distribution.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.build(project/"bundles")
    assert {r["mode"] for r in result}=={"local","agent"}
    with zipfile.ZipFile(project/"bundles/video-agent-local.zip") as a,zipfile.ZipFile(project/"bundles/video-agent-agent.zip") as b:
        local=set(a.namelist());agent=set(b.namelist())
        assert not any("/skills/" in name for name in local)
        extra=agent-local
        assert extra=={"video-agent/"+n for n in module.SKILL}
        for name in local&agent-{"video-agent/README.md"}:assert a.read(name)==b.read(name)
        for name in local|agent:
            assert not any(part in Path(name).parts for part in (".venv","models",".cache","tests","web"))
            assert not name.endswith((".mp4",".wav",".env.local"))
        assert a.testzip() is None and b.testzip() is None
        assert max(r["bytes"] for r in result)<150000
