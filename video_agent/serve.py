"""Local preview of generated notes and video, including byte-range seeking."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import mimetypes
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SUFFIXES = {
    '.html', '.md', '.json', '.jpg', '.jpeg', '.png', '.webp', '.gif',
    '.mp4', '.webm', '.mov', '.mkv', '.m4v', '.mp3', '.wav', '.m4a',
    '.vtt', '.srt', '.xml', '.pdf',
}
SENSITIVE_NAMES = {
    'config.json', 'settings.json', 'credentials.json', 'secrets.json',
    'token.json', 'tokens.json', 'auth.json',
}
CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.pdf': 'application/pdf', '.mp4': 'video/mp4',
    '.webm': 'video/webm', '.mov': 'video/quicktime', '.mkv': 'video/x-matroska',
    '.m4v': 'video/mp4', '.vtt': 'text/vtt; charset=utf-8',
    '.srt': 'text/plain; charset=utf-8', '.xml': 'application/xml; charset=utf-8',
}


def parse_range(value: str, size: int) -> tuple[int, int]:
    """Parse one bytes range and return inclusive offsets; reject invalid ranges."""
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value.strip())
    if not match or size <= 0:
        raise ValueError('Invalid or unsatisfiable byte range')
    first, last = match.groups()
    if not first:
        if not last or int(last) <= 0:
            raise ValueError('Invalid suffix byte range')
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError('Unsatisfiable byte range')
    return start, end


def public_path(url: str) -> Path:
    """Resolve a URL only to an allowed file under this project's data directory."""
    decoded = unquote(urlsplit(url).path)
    if '\\' in decoded or '\x00' in decoded or ':' in decoded:
        raise PermissionError('Invalid path')
    parts = decoded.lstrip('/').split('/')
    if not parts or parts[0] != 'data' or any(part in {'.', '..'} for part in parts):
        raise PermissionError('Only project data files are available')
    if any(part.startswith('.') for part in parts if part):
        raise PermissionError('Hidden files are not available')
    candidate = PROJECT_ROOT.joinpath(*parts).resolve()
    data_root = (PROJECT_ROOT / 'data').resolve()
    if not data_root.is_relative_to(PROJECT_ROOT) or not candidate.is_relative_to(data_root):
        raise PermissionError('Path is outside project data directory')
    if candidate.suffix.lower() not in ALLOWED_SUFFIXES or candidate.name.lower() in SENSITIVE_NAMES:
        raise PermissionError('This file type is not available')
    return candidate


def notes_url(notes: str | Path) -> str:
    path = Path(notes)
    path = path if path.is_absolute() else PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_relative_to(PROJECT_ROOT):
        raise ValueError('--notes must stay inside project directory')
    url = '/' + quote(path.relative_to(PROJECT_ROOT).as_posix(), safe='/')
    try:
        resolved = public_path(url)
    except PermissionError as error:
        raise ValueError('--notes must be an HTML file under project data directory') from error
    if resolved.suffix.lower() != '.html' or not resolved.is_file():
        raise ValueError('--notes must refer to an existing HTML file')
    return url


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], notes: str | Path):
        if address[0] != '127.0.0.1':
            raise ValueError('Preview server only listens on 127.0.0.1')
        self.notes_location = notes_url(notes)
        super().__init__(address, PreviewHandler)


class PreviewHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'VideoNotes/0.1'
    sys_version = ''

    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/"):
            self._api()
        else:
            self._send_file(head=False)

    def do_HEAD(self):
        if urlsplit(self.path).path.startswith("/api/"):
            self._api(head=True)
        else:
            self._send_file(head=True)

    def do_POST(self):
        self._api()

    def _json(self, data, status=200, head=False):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if not head:
            self.wfile.write(payload)

    def _reject_json(self, data, status):
        # Drain a small rejected POST before closing: unread bytes can cause a
        # TCP reset on Windows, hiding the JSON error from the caller.
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if 0 < length <= 8192 and not self.headers.get("Transfer-Encoding"):
            previous_timeout = self.connection.gettimeout()
            try:
                self.connection.settimeout(.5)
                self.rfile.read(length)
            except OSError:
                pass
            finally:
                self.connection.settimeout(previous_timeout)
        self.close_connection = True
        self._json(data, status)

    def _api(self, head=False):
        from .library import library_data, generation_categories
        from .local_jobs import JobError
        path = urlsplit(self.path).path
        manager = getattr(self.server, "local_jobs", None)
        if not manager:
            self._json({"error":"当前预览未启动本地生成服务"},503,head)
            return
        if self.command in ("GET","HEAD"):
            if path == "/api/health":
                from .runtime import project_id
                self._json({"app":"video-agent","mode":"local","online":True,"version":2,"project_id":project_id(manager.root),"generation_categories":generation_categories()},head=head)
            elif path == "/api/library":
                self._json(library_data(manager.root),head=head)
            elif path == "/api/jobs":
                self._json({"jobs":manager.list()},head=head)
            else:
                self._json({"error":"接口不存在"},404,head)
            return
        allowed = {"127.0.0.1:"+str(self.server.server_port),"localhost:"+str(self.server.server_port)}
        origin = self.headers.get("Origin")
        if self.headers.get("Host") not in allowed or (origin and origin not in {"http://"+host for host in allowed}):
            self._reject_json({"error":"请求来源无效"},403)
            return
        if self.headers.get("Content-Type","").split(";")[0].strip() != "application/json":
            self._reject_json({"error":"请使用 JSON 请求"},415)
            return
        try:
            length = int(self.headers.get("Content-Length",0))
            if not 0 < length <= 8192:
                self.close_connection = True
                self._json({"error":"请求内容过大或为空"},413)
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError()
            if path == "/api/jobs":
                job,reused = manager.submit(data.get("url",""),data.get("category",""))
                self._json({"job":job,"reused":reused},200 if reused else 202)
            elif path == "/api/shutdown":
                self._json({"ok":True})
                self.wfile.flush()
                threading.Thread(target=self.server.shutdown,daemon=True).start()
            else:
                self._json({"error":"接口不存在"},404)
        except JobError as error:
            self._json({"error":str(error)},error.status)
        except (ValueError,TypeError):
            self._json({"error":"请求内容无效"},400)

    def log_message(self, format, *args):
        # Browser video players issue many range requests; keep startup output readable.
        pass

    def _send_file(self, head: bool):
        requested_path = self.path
        if urlsplit(self.path).path == '/':
            if self.server.notes_location == "/data/index.html":
                requested_path = self.server.notes_location
            else:
                self.send_response(302)
                self.send_header('Location', self.server.notes_location)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
        try:
            path = public_path(requested_path)
        except (PermissionError, ValueError):
            self.send_error(403, 'Only generated project data files are available')
            return
        if not path.is_file():
            self.send_error(404, 'Data file not found')
            return
        try:
            stream = path.open('rb')
        except OSError:
            self.send_error(404, 'Data file could not be opened')
            return
        with stream:
            size = os.fstat(stream.fileno()).st_size
            start, end, status = 0, size - 1, 200
            range_header = self.headers.get('Range')
            if range_header:
                try:
                    start, end = parse_range(range_header, size)
                    status = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.send_header('Accept-Ranges', 'bytes')
                    self.end_headers()
                    return
            length = max(0, end - start + 1)
            self.send_response(status)
            content_type = CONTENT_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(length))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            if head:
                return
            stream.seek(start)
            remaining = length
            try:
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='预览本地探店笔记，支持视频时间戳定位')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--notes', type=Path, default=Path('data/index.html'))
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    if args.notes == Path("data/index.html"):
        from .library import build
        build()
    try:
        server = PreviewServer(('127.0.0.1', args.port), args.notes)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    from .local_jobs import LocalJobs
    server.local_jobs = LocalJobs()
    print(f'本地工具首页：http://127.0.0.1:{server.server_port}/', flush=True)
    print(f'项目数据目录：{PROJECT_ROOT / "data"}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.local_jobs.close()
        server.server_close()


if __name__ == '__main__':
    main()