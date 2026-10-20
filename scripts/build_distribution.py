"""Build two small, self-contained source bundles; never include local data."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
CORE=[
"video-agent.py","requirements.txt","constraints.txt",
"video_agent/__init__.py","video_agent/__main__.py","video_agent/cli.py","video_agent/runtime.py",
"video_agent/extract.py","video_agent/pipeline.py","video_agent/mining.py","video_agent/menu.py",
"video_agent/render.py","video_agent/serve.py","video_agent/local_jobs.py","video_agent/library.py",
"video_agent/templates/local-tool.html",
]
SKILL=["skills/video-agent/SKILL.md","skills/video-agent/agents/openai.yaml"]

def build(output=None):
    output=Path(output or ROOT/"output/releases").resolve()
    if not output.is_relative_to(ROOT):raise ValueError("打包输出必须位于项目内")
    output.mkdir(parents=True,exist_ok=True)
    reports=[]
    for mode in ("local","agent"):
        names=CORE+(SKILL if mode=="agent" else [])
        quickstart=ROOT/("docs/QUICKSTART_AGENT.md" if mode=="agent" else "docs/QUICKSTART_LOCAL.md")
        path=output/f"video-agent-{mode}.zip"
        with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            archive.writestr("video-agent/README.md",quickstart.read_text(encoding="utf-8"))
            for name in names:
                source=(ROOT/name).resolve()
                if not source.is_relative_to(ROOT) or not source.is_file():raise ValueError("缺少分发文件："+name)
                archive.write(source,"video-agent/"+name)
        reports.append({"mode":mode,"file":path.name,"bytes":path.stat().st_size,
                        "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"files":len(names)+1})
    (output/"checksums.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return reports

if __name__=="__main__":
    print(json.dumps(build(),ensure_ascii=False))
