"""Acceptance checks against manually observed title frames, not pipeline input."""
import json,re
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data'/'processed'/'BV1cHen6EEen'/'notes.json'
pytestmark=pytest.mark.skipif(not OUTPUT.exists(),reason='Run the bundled real-video sample before acceptance checks')
def result():return json.loads(OUTPUT.read_text(encoding='utf-8'))
def expected():return json.loads((ROOT/'tests'/'fixtures'/'BV1cHen6EEen_expected.json').read_text(encoding='utf-8'))
def key(s):return re.sub(r'[^\w\u3400-\u9fff]','',s).lower()
def test_real_shop_titles_and_boundaries():
    shops=result()['shops'];truth=expected()
    assert len(shops)==len(truth['names'])
    for shop,name in zip(shops,truth['names']):
        assert key(shop['name']) in [key(x) for x in truth['aliases'].get(name,[name])]
    assert all(abs(s['start']-t)<=truth['time_tolerance'] for s,t in zip(shops,truth['start_times']))
    assert shops[-1]['end']<truth['outro_before']
def test_no_false_addresses_and_core_foods():
    shops=result()['shops']
    assert not any(s['locations'] for s in shops),'Sample has no evidenced detailed postal addresses'
    for name,word in [('Tacobar','塔克'),('印厨','咖喱'),('新疆驻京办','包尔萨克'),('四川驻京办','白肉'),('澜玖拾柒','宽粉')]:
        aliases=expected()['aliases'].get(name,[name])
        shop=next(s for s in shops if key(s['name']) in [key(x) for x in aliases])
        assert any(word in d for d in shop['dishes']),f'Missing evidenced dish {name}: {word}'
def test_real_fact_provenance_and_screenshot_files():
    data=result()
    for shop in data['shops']:
        for field in ['dishes','prices','locations','highlights']:
            facts=shop['fact_evidence'][field]
            assert [p['text'] for p in facts]==shop[field]
            assert all(shop['start']<=p['time']<shop['end'] and p['source'] in ['asr','ocr'] and p['original'] for p in facts)
        for evidence in shop['evidence']:
            path=Path(evidence['path'])
            assert path.resolve().is_relative_to(ROOT.resolve()) and path.is_file()
