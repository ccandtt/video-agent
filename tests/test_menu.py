from pathlib import Path
import tempfile
import unittest
from html.parser import HTMLParser
from video_agent.menu import build_menu
from video_agent.render import render_notes
ROOT = Path(__file__).resolve().parents[1]

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if attrs.get('id'): self.ids.append(attrs['id'])
        if tag=='a' and attrs.get('href','').startswith('#'): self.links.append(attrs['href'][1:])

class MenuTests(unittest.TestCase):
    def fixture(self):
        return {'name':'示例店','start':0,'end':40,'dishes':['烧饼','汤'],
            'prices':['6 元','99 元'], 'fact_evidence':{
                'dishes':[{'text':'烧饼','time':12,'source':'ocr','original':'烧饼6元'},
                          {'text':'汤','time':25,'source':'asr','original':'汤不错'}],
                'prices':[{'text':'99 元','time':25,'original':'套餐99元','source':'ocr'}],
                'highlights':[{'text':'讲解摘录（自动识别）：烧饼外酥里软','time':12,'original':'烧饼外酥里软','source':'asr'}]},
            'evidence':[]}
    def test_price_review_image_are_matched_and_missing_is_not_filled(self):
        shop=self.fixture()
        frames=[{'time':12,'path':'dish.jpg','sharpness':30,'ocr':[{'text':'烧饼6元'}]},
                {'time':25,'path':'unrelated.jpg','sharpness':99,'ocr':[{'text':'套餐99元'}]}]
        menu=build_menu(shop,frames)
        self.assertEqual(menu[0]['price'],'¥6')
        self.assertIn('外酥里软',menu[0]['review'])
        self.assertEqual(menu[0]['image']['path'],'dish.jpg')
        self.assertEqual(menu[1]['price'],'')
        self.assertIsNone(menu[1]['image'])
        self.assertEqual(menu[0]['price_evidence']['time'],12)
    def test_links_resolve_uniquely_and_unmatched_dish_has_no_image_link(self):
        shop=self.fixture(); shop['menu']=build_menu(shop,[{'time':12,'path':'dish.jpg','sharpness':30,'ocr':[{'text':'烧饼6元'}]}])
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
            paths=render_notes({'shops':[shop,shop]},Path(directory))
            web=paths['html'].read_text(encoding='utf-8'); md=paths['markdown'].read_text(encoding='utf-8')
            parser=Links();parser.feed(web)
            self.assertEqual(len(parser.ids),len(set(parser.ids)))
            self.assertTrue(all(target in parser.ids for target in parser.links))
            self.assertNotIn('视觉证据',web)
            self.assertIn('菜品图鉴',web)
            self.assertNotIn('href="#shop-1-dish-2"',web)
            self.assertIn('[查看图片](#shop-1-dish-1)',md)
    def test_duplicate_short_label_collapses_only_with_same_mention(self):
        shop={'dishes':['芝士','芝士饼'],'fact_evidence':{'dishes':[
            {'text':'芝士','time':10,'original':'芝士饼'},
            {'text':'芝士饼','time':10,'original':'芝士饼'}]}}
        self.assertEqual([m['name'] for m in build_menu(shop)],['芝士饼'])
        shop['fact_evidence']['dishes'][0]['time']=20
        self.assertEqual(len(build_menu(shop)),2)

    def test_adjacent_ocr_typo_merges_to_high_confidence_name_and_keeps_provenance(self):
        correct, typo = '草莓迪拜巧克力软曲奇', '草莓迪翔巧克力软曲奇'
        shop={'start':0,'end':20,'dishes':[correct,typo], 'fact_evidence':{'dishes':[
            {'text':correct,'time':10,'original':correct,'source':'ocr'},
            {'text':typo,'time':10.8,'original':typo,'source':'ocr'}]}}
        frames=[{'time':10,'path':'a.jpg','ocr':[{'text':correct,'score':.9944}]},
                {'time':10.8,'path':'b.jpg','ocr':[{'text':typo,'score':.9248}]}]
        menu=build_menu(shop,frames)
        self.assertEqual(len(menu),1)
        self.assertEqual(menu[0]['name'],correct)
        self.assertEqual(set(menu[0]['aliases']),{correct,typo})
        self.assertEqual(len(menu[0]['references']),2)
        self.assertEqual(shop['dishes'],[correct,typo])
        # Real similar products shown together must remain separate.
        frames[0]['ocr'].append({'text':typo,'score':.93})
        self.assertEqual(len(build_menu(shop,frames)),2)
        frames[0]['ocr'].pop()
        frames[1]['time']=15
        self.assertEqual(len(build_menu(shop,frames)),2)
        frames[1]['time']=10.8;frames[0]['ocr'][0]['score']=.94
        self.assertEqual(len(build_menu(shop,frames)),2)
