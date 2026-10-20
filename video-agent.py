"""Standard-library bootstrap. User entry: python video-agent.py setup/start."""
from pathlib import Path
import json
import os
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent

def run():
    args=sys.argv[1:]
    if not args or args[0] in ("-h","--help"):
        print("Video Agent\\n首次：python video-agent.py setup\\n以后：python video-agent.py start\\nAgent：python video-agent.py summarize URL --json\\n其他：status / stop / doctor".replace("\\n","\n"))
        return 0
    if sys.version_info<(3,11):
        print("需要 Python 3.11 或更新版本。",file=sys.stderr);return 1
    from video_agent.runtime import ensure_dirs,environment,file_lock
    ensure_dirs(ROOT)
    os.environ.update(environment(ROOT))
    python=ROOT/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    try:
        if args[0]=="setup":
            with file_lock(ROOT/".cache/bootstrap.lock",timeout=60):
                if not python.exists():venv.EnvBuilder(with_pip=True).create(ROOT/".venv")
                log_path=ROOT/".cache/install.log"
                command=[str(python),"-m","pip","install","--disable-pip-version-check","--cache-dir",str(ROOT/".cache/pip"),"-r",str(ROOT/"requirements.txt")]
                if "--offline" in args:command+=["--no-index"]
                print("检查并安装项目依赖…",file=sys.stderr,flush=True)
                with log_path.open("ab") as log:
                    code=subprocess.run(command,cwd=ROOT,env=environment(ROOT),stdout=log,stderr=subprocess.STDOUT).returncode
                if code:raise RuntimeError("依赖安装未完成；查看 "+str(log_path))
        elif not python.exists():
            raise RuntimeError("首次使用请先运行：python video-agent.py setup")
        return subprocess.call([str(python),"-m","video_agent",*args],cwd=ROOT,env=environment(ROOT))
    except (OSError,RuntimeError) as error:
        result={"status":"error","error":str(error)}
        print(json.dumps(result,ensure_ascii=False) if "--json" in args else result["error"],file=sys.stdout if "--json" in args else sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(run())
