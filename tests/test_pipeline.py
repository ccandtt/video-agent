from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from video_agent.pipeline import project_root, within, validate_result


class PipelineValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=project_root() / '.cache')
        self.out = Path(self.temp.name)
        self.image = self.out / 'evidence.png'
        Image.new('RGB', (10, 20), color='white').save(self.image)
        self.data = {
            'duration': 20.0,
            'shops': [{
                'name': '测试店', 'start': 2.0, 'end': 12.0,
                'evidence': [{'time': 7.0, 'path': 'evidence.png'}],
            }],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_within_accepts_project_descendant(self):
        root = project_root()
        self.assertEqual(within(root / 'data' / '..' / 'docs', root), root / 'docs')

    def test_within_rejects_sibling_prefix_and_parent_traversal(self):
        root = project_root()
        paths = [root.parent / (root.name + '_sibling') / 'file', root / '..' / 'outside.mp4']
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'inside project'):
                within(path, root)

    def test_valid_result_checks_readable_image(self):
        result = validate_result(self.data, self.out)
        self.assertEqual(result['shops'], 1)
        self.assertEqual(result['screenshots'], 1)
        self.assertTrue(result['all_timestamps_valid'])
        self.assertTrue(result['all_evidence_images_readable'])

    def test_empty_shops_and_evidence_fail(self):
        cases = [dict(duration=20, shops=[]), deepcopy(self.data)]
        cases[1]['shops'][0]['evidence'] = []
        for data in cases:
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                validate_result(data, self.out)

    def test_bad_time_ranges_fail(self):
        for start, end in [(-1, 12), (12, 12), (13, 12), (2, 21)]:
            data = deepcopy(self.data)
            data['shops'][0].update(start=start, end=end)
            with self.subTest(start=start, end=end), self.assertRaisesRegex(RuntimeError, 'Invalid segment'):
                validate_result(data, self.out)
        for moment in [0, 14, float('nan')]:
            data = deepcopy(self.data)
            data['shops'][0]['evidence'][0]['time'] = moment
            with self.subTest(moment=moment), self.assertRaisesRegex(RuntimeError, 'Evidence outside shop'):
                validate_result(data, self.out)

    def test_evidence_outside_project_fails(self):
        data = deepcopy(self.data)
        data['shops'][0]['evidence'][0]['path'] = str(project_root().parent / 'outside.png')
        with self.assertRaisesRegex(ValueError, 'inside project'):
            validate_result(data, self.out)

    def test_missing_and_corrupt_images_fail(self):
        data = deepcopy(self.data)
        data['shops'][0]['evidence'][0]['path'] = 'absent.jpg'
        with self.assertRaisesRegex(RuntimeError, 'Missing image'):
            validate_result(data, self.out)
        corrupt = self.out / 'corrupt.jpg'
        corrupt.write_text('not an image', encoding='utf-8')
        data['shops'][0]['evidence'][0]['path'] = str(corrupt)
        with self.assertRaises((RuntimeError, OSError)):
            validate_result(data, self.out)


if __name__ == '__main__':
    unittest.main()