"""Stable CLI used both by the optional Skill and human users."""
import argparse
import json
import sys
from . import runtime

def main(argv=None):
    parser=argparse.ArgumentParser(description="Video Agent：同一个本地工具，Agent 与网页两种入口")
    commands=parser.add_subparsers(dest="command",required=True)
    for name in ("setup","start","status","stop","doctor","summarize"):
        item=commands.add_parser(name)
        item.add_argument("--json",action="store_true",help="仅向 stdout 返回机器可读结果")
        if name in ("setup","start","summarize"):item.add_argument("--port",type=int,default=8765)
        if name in ("setup","start"):item.add_argument("--no-browser",action="store_true")
        if name=="setup":item.add_argument("--offline",action="store_true")
        if name=="start":item.add_argument("--restart",action="store_true")
        if name=="summarize":
            item.add_argument("url")
            item.add_argument("--category",default="restaurant")
            item.add_argument("--no-wait",action="store_true")
            item.add_argument("--timeout",type=float,default=3600)
    args=parser.parse_args(argv)
    code=0
    try:
        if args.command=="setup":
            result=runtime.setup(args.offline,args.port,not args.no_browser)
        elif args.command=="start":
            if args.restart:runtime.stop()
            result=runtime.start(args.port,not args.no_browser)
        elif args.command=="stop":result=runtime.stop()
        elif args.command=="status":result=runtime.status()
        elif args.command=="doctor":
            result=runtime.doctor()
            code=0 if result["status"]=="ready" else 1
        else:
            result=runtime.summarize(args.url,args.category,not args.no_wait,args.timeout,args.port)
            code=1 if result["status"]=="failed" else 2 if result["timed_out"] else 0
    except (ValueError,OSError,RuntimeError,KeyError,StopIteration,ImportError) as error:
        result={"status":"error","error":str(error)}
        code=1
    if args.json:
        print(json.dumps(result,ensure_ascii=False))
    elif result.get("error"):
        print("未完成："+result["error"],file=sys.stderr)
    elif args.command in ("setup","start"):
        print(("部署成功" if args.command=="setup" else "工具已运行")+"："+result["homepage_url"])
        print("功能：1.探店图文笔记  2.截图与时间戳回看  3.历史分类搜索")
        print("使用：网页粘贴视频链接，或把链接发给使用本项目 Skill 的 Agent。")
    elif args.command=="summarize":
        print("状态："+result["status"])
        if result.get("note_url"):print("笔记："+result["note_url"])
        print("首页："+result["homepage_url"])
        if result["timed_out"]:print("等待超时，后台任务仍在运行，可到首页查看。")
    else:print(json.dumps(result,ensure_ascii=False,indent=2))
    return code

if __name__=="__main__":
    raise SystemExit(main())
