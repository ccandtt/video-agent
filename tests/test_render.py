from pathlib import Path
import tempfile
import unittest
from video_agent.render import render_notes, timestamp, shop_introduction, storefront_evidence, display_shop_name

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RenderNotesTests(unittest.TestCase):
    def test_notes_preserve_evidence_and_missing_information(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / '.cache') as directory:
            output = Path(directory)
            data = {
                'title': '探店 <核对>', 'source_url': 'https://www.bilibili.com/video/BVtest/?foo=bar',
                'video_path': str(PROJECT_ROOT / 'data/raw/test/video.mp4'), 'duration': 447,
                'method': '测试画面与讲解', 'limitations': ['未提供详细地址'],
                'shops': [{
                    'id': 'shop-1', 'name': '<script>alert(1)</script>', 'start': 10.2, 'end': 40,
                    'dishes': ['烧饼'], 'prices': [], 'locations': [], 'highlights': ['博主提及酥脆'],
                    'name_evidence': {'original': '错误店名', 'corrected': '正确店名', 'reason': '画面店名字幕', 'time': 12},
                    'uncertain': True, 'evidence': [{'time': 12, 'path': 'frames/店名 001.jpg', 'kind': '店名', 'text': '店名字幕'}],
                    'transcript': [{'start': 10.2, 'end': 14, 'text': '<b>自动识别原文</b>'}],
                }],
            }
            paths = render_notes(data, output)
            md = paths['markdown'].read_text(encoding='utf-8')
            web = paths['html'].read_text(encoding='utf-8')
            self.assertIn('foo=bar&t=10', md)
            self.assertIn('名称待核对', md)
            self.assertNotIn('错误店名', md)
            self.assertNotIn('名称核对', web)
            self.assertNotIn('名称核对', md)
            self.assertIn('未提取到可确认的详细地址', md)
            self.assertIn('未提取到可确认的价格', web)
            self.assertIn('frames/%E5%BA%97%E5%90%8D%20001.jpg', web)
            self.assertIn('data-time="12.000"', web)
            self.assertNotIn('<script>alert(1)</script>', web)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', web)
            self.assertIn('&lt;b&gt;自动识别原文&lt;/b&gt;', web)
            self.assertIn('player.currentTime=', web)
            self.assertIn('07:27', web)

    def test_each_fact_has_matching_evidence_timestamp_and_source(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / '.cache') as directory:
            data = {
                'title': '事实定位', 'source_url': 'https://www.bilibili.com/video/BVtest/',
                'duration': 90, 'shops': [{
                    'name': '测试店', 'start': 5, 'end': 80,
                    'dishes': ['烧饼', '没有对应依据'], 'prices': ['6 元'],
                    'locations': ['胡同'], 'highlights': ['酥脆'],
                    'fact_evidence': {
                        'dishes': [{'text': '烧饼', 'time': 12, 'source': 'asr', 'original': '这个烧饼酥脆'},
                                   {'text': '无关菜品', 'time': 79, 'source': 'asr', 'original': '不应匹配'}],
                        'prices': [{'text': '6 元', 'time': 23, 'source': 'ocr', 'original': '烧饼 6元'}],
                        'locations': [{'text': '胡同', 'time': 34, 'source': 'ASR', 'original': '就在这个胡同'}],
                        'highlights': [{'text': '酥脆', 'time': 45, 'source': 'ASR', 'original': '这个酥脆'}],
                    },
                    'evidence': [], 'transcript': [{'start': 12, 'text': '这个烧饼酥脆'}],
                }],
            }
            paths = render_notes(data, Path(directory))
            md = paths['markdown'].read_text(encoding='utf-8')
            web = paths['html'].read_text(encoding='utf-8')
            for seconds in [12, 23, 34, 45]:
                self.assertIn(f'?t={seconds}', md)
                self.assertIn(f'data-time="{seconds}.000"', web)
            self.assertIn('ASR', md)
            self.assertIn('OCR', web)
            self.assertIn('识别文本：这个烧饼酥脆', md)
            self.assertIn('识别文本（可能误识别）：烧饼 6元', web)
            self.assertIn('讲解识别文本（可能误识别）', md)
            self.assertNotIn('?t=79', md)
            self.assertNotIn('data-time="79.000"', web)
            self.assertIn('<strong>没有对应依据</strong>', web)

    def test_intro_and_storefront_are_grounded_and_not_duplicated(self):
        shop = {'name': '示例店', 'start': 0, 'end': 30,
                'transcript': [{'text': '属于意大利餐'}],
                'highlights': ['讲解摘录（自动识别）：披萨外酥里软，芝士浓郁'],
                'evidence': [{'kind': 'scene', 'path': 'food.jpg', 'time': 12},
                             {'kind': 'shop_name', 'path': 'entrance.jpg', 'time': 1}]}
        self.assertIn('意大利菜', shop_introduction(shop))
        self.assertIn('披萨外酥里软', shop_introduction(shop))
        self.assertNotIn('意大利', shop_introduction({'dishes': ['烧饼']}))
        self.assertIsNone(storefront_evidence({'evidence': [shop['evidence'][0]]}))
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / '.cache') as directory:
            paths = render_notes({'shops': [shop]}, Path(directory))
            web = paths['html'].read_text(encoding='utf-8')
            md = paths['markdown'].read_text(encoding='utf-8')
            self.assertEqual(web.count('src="entrance.jpg"'), 1)
            self.assertEqual(md.count('](entrance.jpg)'), 1)
            self.assertIn('<strong>意大利菜</strong>', web)
            self.assertIn('**意大利菜**', md)
            self.assertNotIn('博主评价：', web)
            self.assertIn('class="storefront"', web)
            self.assertIn('href="#shop-1"', web)
            self.assertLess(web.index('class="restaurant-intro"'), web.index('class="storefront"'))

    def test_english_brand_spacing_uses_matching_sign_and_keeps_acronyms(self):
        shop = {'name': 'Riverhouse', 'start': 1, 'end': 20}
        frames = [{'time': 2, 'ocr': [{'text': 'RIVER HOUSE', 'score': .96},
                                    {'text': 'OTHER BRAND', 'score': .99}]}]
        self.assertEqual(display_shop_name(shop, frames), 'River House')
        self.assertEqual(display_shop_name({'name': 'THE TACO BAR'}), 'THE TACO BAR')
        self.assertEqual(display_shop_name({'name': 'ourBakery'}), 'our Bakery')
        self.assertEqual(display_shop_name({'name': '印厨'}), '印厨')

    def test_empty_result_and_timestamp(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / '.cache') as directory:
            paths = render_notes({'title': '空结果', 'shops': []}, Path(directory))
            self.assertIn('尚未提取到店铺条目', paths['html'].read_text(encoding='utf-8'))
        self.assertEqual(timestamp(0), '00:00')
        self.assertEqual(timestamp(3661), '01:01:01')


    def test_descriptive_stop_is_not_shown_as_an_official_name_or_storefront(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / '.cache') as directory:
            shop={'name':'包子点位','name_type':'descriptive','start':1,'end':10,
                  'dishes':['包子'],'uncertain':True,
                  'evidence':[{'kind':'context','path':'baozi.jpg','time':2}]}
            paths=render_notes({'shops':[shop]},Path(directory))
            web=paths['html'].read_text(encoding='utf-8')
            self.assertIn('按视频食物线索命名，未注明店名。',web)
            self.assertIn('点位画面',web)
            self.assertIn('探吃目录',web)
            self.assertNotIn('店铺门头',web)

if __name__ == '__main__':
    unittest.main()