from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import quote
from video_agent.serve import PROJECT_ROOT, PreviewServer, notes_url, parse_range, public_path


class RangeTests(unittest.TestCase):
    def test_valid_ranges(self):
        for header, expected in [('bytes=0-3', (0, 3)), ('bytes=5-', (5, 9)), ('bytes=-3', (7, 9)), ('bytes=-50', (0, 9)), ('bytes=5-100', (5, 9)), ('bytes=0-0', (0, 0))]:
            with self.subTest(header=header):
                self.assertEqual(parse_range(header, 10), expected)

    def test_invalid_ranges(self):
        for header in ['bytes=', 'bytes=-', 'bytes=-0', 'bytes=10-', 'bytes=6-3', 'bytes=0-1,3-4', 'items=0-1', 'bytes=a-b']:
            with self.subTest(header=header), self.assertRaises(ValueError):
                parse_range(header, 10)
        with self.assertRaises(ValueError):
            parse_range('bytes=0-', 0)


class PreviewHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = PROJECT_ROOT / 'data' / 'processed'
        base.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='serve-test-', dir=base)
        cls.output = Path(cls.temp.name)
        cls.notes = cls.output / '笔记.html'
        cls.notes.write_text('<!doctype html><p>中文笔记</p>', encoding='utf-8')
        cls.payload = b'0123456789abcdefghijklmnopqrstuvwxyz'
        (cls.output / 'video.mp4').write_bytes(cls.payload)
        (cls.output / 'source.py').write_text('print("not public")', encoding='utf-8')
        (cls.output / '.env').write_text('SECRET=not_public', encoding='utf-8')
        (cls.output / 'credentials.json').write_text('{}', encoding='utf-8')
        cls.prefix = '/' + quote(cls.output.relative_to(PROJECT_ROOT).as_posix(), safe='/')
        cls.server = PreviewServer(('127.0.0.1', 0), cls.notes)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def request(self, path, method='GET', headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_root_redirect_and_chinese_url(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 302)
        self.assertEqual(headers['Location'], notes_url(self.notes))
        self.assertEqual(body, b'')
        status, headers, body = self.request(headers['Location'])
        self.assertEqual(status, 200)
        self.assertIn('charset=utf-8', headers['Content-Type'])
        self.assertIn('中文笔记', body.decode('utf-8'))

    def test_full_and_head_video(self):
        status, headers, body = self.request(self.prefix + '/video.mp4')
        self.assertEqual(status, 200)
        self.assertEqual(body, self.payload)
        self.assertEqual(headers['Content-Type'], 'video/mp4')
        status, headers, body = self.request(self.prefix + '/video.mp4', method='HEAD')
        self.assertEqual(status, 200)
        self.assertEqual(int(headers['Content-Length']), len(self.payload))
        self.assertEqual(body, b'')

    def test_range_requests_and_range_head(self):
        for header, expected, content_range in [('bytes=5-9', self.payload[5:10], 'bytes 5-9/36'), ('bytes=-4', self.payload[-4:], 'bytes 32-35/36'), ('bytes=32-', self.payload[32:], 'bytes 32-35/36')]:
            status, headers, body = self.request(self.prefix + '/video.mp4', headers={'Range': header})
            self.assertEqual(status, 206)
            self.assertEqual(body, expected)
            self.assertEqual(headers['Content-Range'], content_range)
        status, headers, body = self.request(self.prefix + '/video.mp4', method='HEAD', headers={'Range': 'bytes=5-9'})
        self.assertEqual(status, 206)
        self.assertEqual(headers['Content-Length'], '5')
        self.assertEqual(body, b'')

    def test_invalid_range_returns_416(self):
        for header in ['bytes=100-', 'bytes=3-1', 'bytes=0-1,4-5']:
            status, headers, body = self.request(self.prefix + '/video.mp4', headers={'Range': header})
            self.assertEqual(status, 416)
            self.assertEqual(headers['Content-Range'], 'bytes */36')
            self.assertEqual(body, b'')

    def test_traversal_and_private_files_denied(self):
        paths = ['/data/../docs/SCENARIOS.md', '/data/%2e%2e/docs/SCENARIOS.md', '/data/%5c..%5cmodels/file.bin', '/data/C%3a/Windows/file.mp4', '/.venv/pyvenv.cfg', '/models/model.bin', '/.cache/test.json', '/video_agent/render.py', self.prefix + '/source.py', self.prefix + '/.env', self.prefix + '/credentials.json', self.prefix + '/']
        for path in paths:
            with self.subTest(path=path):
                status, _, _ = self.request(path)
                self.assertEqual(status, 403)

    def test_missing_file_and_notes_outside_data(self):
        self.assertEqual(self.request(self.prefix + '/missing.jpg')[0], 404)
        for path in [PROJECT_ROOT / 'docs' / 'SCENARIOS.md', PROJECT_ROOT.parent / 'outside.html']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                notes_url(path)
        with self.assertRaises(ValueError):
            PreviewServer(('0.0.0.0', 0), self.notes)

    def test_symlink_escape_denied(self):
        link = self.output / 'outside.md'
        try:
            link.symlink_to(PROJECT_ROOT / 'docs' / 'SCENARIOS.md')
        except OSError:
            self.skipTest('Windows environment does not permit symlink creation')
        try:
            with self.assertRaises(PermissionError):
                public_path(self.prefix + '/outside.md')
        finally:
            link.unlink()


if __name__ == '__main__':
    unittest.main()