from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
NOTES=ROOT/'data/processed/BV1u7Hj6HEV2/notes.json'

@unittest.skipUnless(NOTES.exists(),'Generate the real stall sample first')
class StallSampleTests(unittest.TestCase):
    def test_real_stops_names_and_uncertainty(self):
        fixture=json.loads((ROOT/'tests/fixtures/BV1u7Hj6HEV2_review.json').read_text(encoding='utf-8'))
        data=json.loads(NOTES.read_text(encoding='utf-8'));shops=data['shops']
        self.assertEqual(len(shops),fixture['expected_stops'])
        self.assertEqual(shops[0]['name_type'],'descriptive')
        self.assertIn(fixture['descriptive_first_food'],shops[0]['name'])
        self.assertTrue(shops[0]['uncertain'])
        self.assertIsNone(shops[0]['name_evidence'])
        self.assertTrue(all(any(label in s['name'] for s in shops) for label in fixture['confirmed_video_labels']))
        self.assertTrue(any(s["name"]==fixture["descriptive_drinks"] and s["name_type"]=="descriptive" for s in shops))
        for left,right in zip(shops,shops[1:]):
            self.assertEqual(left['end'],right['start'])
        self.assertTrue(all(s['evidence'] for s in shops))
    def test_photo_labels_and_all_menu_links_resolve(self):
        from html.parser import HTMLParser
        class Audit(HTMLParser):
            def __init__(self):super().__init__();self.ids=[];self.targets=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if 'id' in attrs:self.ids.append(attrs['id'])
                if tag=='a' and attrs.get('href','').startswith('#'):self.targets.append(attrs['href'][1:])
        web=NOTES.with_suffix('.html').read_text(encoding='utf-8')
        a=Audit();a.feed(web)
        self.assertEqual(len(a.ids),len(set(a.ids)))
        self.assertTrue(all(t in a.ids for t in a.targets))
        self.assertIn('未注明店名',web)
        self.assertIn('点位画面',web)
        self.assertIn('探吃目录',web)
