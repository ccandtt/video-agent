"""Regression checks for false boundaries, unsupported correction and leakage."""
import unittest

from video_agent.mining import infer_shops


def frame(time, text, y=350, height=70, score=0.98, extra=None, sharpness=50):
    lines = [{"text": text, "score": score, "box": [[100,y], [900,y], [900,y+height], [100,y+height]]}]
    lines.extend(extra or [])
    return {"time": time, "path": f"frame-{time}.jpg", "width": 1080, "height": 1920,
            "sharpness": sharpness, "ocr": lines}


def segment(start, end, text):
    return {"start": start, "end": end, "text": text}


class MiningTests(unittest.TestCase):
    def test_watermark_and_bottom_caption_cannot_create_shops(self):
        frames = [frame(0, "1 2 3 4 5 6 7 8 9 10 11", y=0),
                  frame(2, "1.香味餐厅", y=1550),
                  frame(5, "2.别家面馆", y=1550)]
        shops = infer_shops(frames, [], 10)
        self.assertEqual(len(shops), 1)
        self.assertTrue(shops[0]["uncertain"])
        self.assertEqual(shops[0]["name"], "第1家店铺")

    def test_ocr_corrects_a_local_similar_asr_name_with_source(self):
        frames = [frame(1, "1.香满楼餐厅"), frame(2, "1.香满楼餐厅")]
        shops = infer_shops(frames, [segment(0.5, 3, "第一家是香满娄餐厅，点了烤鸭")], 20)
        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0]["name"], "香满楼餐厅")
        self.assertEqual(shops[0]["name_evidence"]["original"], "香满娄餐厅")
        self.assertIn("OCR", shops[0]["name_evidence"]["reason"])
        self.assertFalse(shops[0]["uncertain"])
        self.assertTrue(any(e["kind"] == "shop_name" for e in shops[0]["evidence"]))

    def test_distant_asr_is_not_presented_as_a_confirmed_correction(self):
        frames = [frame(20, "1.香满楼餐厅")]
        shops = infer_shops(frames, [segment(0, 2, "第一家是香满娄餐厅")], 35)
        corrected = [s for s in shops if not s["uncertain"]][0]
        self.assertEqual(corrected["name_evidence"]["original"], "香满楼餐厅")

    def test_chapters_and_prices_do_not_leak_between_shops(self):
        frames = [frame(0, "1.香满楼餐厅"), frame(10, "2.清风面馆")]
        speech = [segment(1, 12, "喜欢烤鸭，这份是88元。"),
                  segment(11, 13, "牛肉面一碗18元。")]
        shops = infer_shops(frames, speech, 20)
        self.assertEqual(len(shops), 2)
        self.assertEqual(shops[0]["end"], shops[1]["start"])
        self.assertIn("88元", shops[0]["prices"])
        self.assertNotIn("88元", shops[1]["prices"])
        self.assertNotIn("18元", shops[0]["prices"])
        self.assertIn("18元", shops[1]["prices"])
        self.assertEqual(shops[0]["transcript"][0]["end"], 10)
        self.assertEqual(shops[1]["fact_evidence"]["prices"][0]["source"], "asr")

    def test_asr_only_name_and_empty_facts_remain_uncertain(self):
        shops = infer_shops([], [segment(2, 4, "第一家是清风面馆")], 10)
        self.assertEqual(shops[0]["name"], "清风面馆")
        self.assertTrue(shops[0]["uncertain"])
        self.assertIsNone(shops[0]["name_evidence"])
        self.assertEqual(shops[0]["locations"], [])
        self.assertEqual(shops[0]["prices"], [])

    def test_unrelated_nearby_ocr_cannot_claim_asr_name_correction(self):
        shops = infer_shops([frame(2, "1.清风面馆")], [segment(1, 3, "第一家是香满楼餐厅")], 10)
        self.assertEqual(shops[0]["name_evidence"]["original"], "清风面馆")

    def test_snapshot_selection_deduplicates_paths_and_spreads_times(self):
        frames = [frame(0, "1.清风面馆"), frame(2, "牛肉面", y=1450, sharpness=100),
                  frame(3, "牛肉面", y=1450, sharpness=120), frame(8, "炒饭", y=1450),
                  frame(15, "面包", y=1450)]
        shops = infer_shops(frames, [], 20)
        evidence = shops[0]["evidence"]
        self.assertEqual(len({item["path"] for item in evidence}), len(evidence))
        scene_times = [e["time"] for e in evidence if e["kind"] == "scene"]
        self.assertIn(3, scene_times)
        self.assertNotIn(2, scene_times)
        self.assertGreaterEqual(len(scene_times), 2)

    def test_separate_ordinal_and_name_asr_segments(self):
        shops = infer_shops([], [segment(1, 2, "第一家"), segment(2, 3, "Garden Cafe")], 10)
        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0]["name"], "Garden Cafe")
        self.assertTrue(shops[0]["uncertain"])

    def test_narrated_ordinal_subtitle_is_allowed_but_packaging_is_not(self):
        frames = [frame(1, "第三家清风面馆", y=1460),
                  frame(6, "迪拜巧克力软曲奇", y=400, height=150),
                  frame(8, "辣椒面偏辣", y=500, height=140),
                  frame(10, "贵州辣椒面比较辣请适量添加", y=500, height=140)]
        shops = infer_shops(frames, [], 15)
        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0]["name"], "清风面馆")

    def test_distance_route_transition_and_english_storefront(self):
        frames = [frame(2, "第一家清风面馆", y=1460),
                  frame(10, "GARDEN DELI", y=500, height=40)]
        speech = [segment(9, 11, "再往前走1.5公里就是个花园美食廊")]
        shops = infer_shops(frames, speech, 20)
        self.assertEqual(len(shops), 2)
        self.assertEqual(shops[1]["name"], "GARDEN DELI")
        self.assertEqual(shops[1]["name_evidence"]["original"], "花园美食廊")

    def test_multiple_stop_recap_poster_cannot_create_new_stops(self):
        poster_extra = [{"text": "第二家香满楼餐厅", "score": .98,
                         "box": [[100,1460],[900,1460],[900,1530],[100,1530]]}]
        frames = [frame(1, "第一家清风面馆", y=1460),
                  frame(15, "第三家花园咖啡馆", y=350, extra=poster_extra)]
        shops = infer_shops(frames, [], 20)
        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0]["name"], "清风面馆")

    def test_outro_does_not_leak_next_episode_food_or_screenshots(self):
        frames = [frame(0, "第一家清风面馆", y=1460),
                  frame(9, "下期小龙虾", y=1460)]
        speech = [segment(1, 2, "喜欢牛肉面"), segment(8, 9, "这期的文字版总结"),
                  segment(9, 10, "下期给大家分享小龙虾")]
        shops = infer_shops(frames, speech, 12)
        self.assertEqual(shops[0]["end"], 8)
        self.assertNotIn("小龙虾", shops[0]["dishes"])
        self.assertTrue(all(e["time"] < 8 for e in shops[0]["evidence"]))

    def test_repeated_name_evidence_prefers_a_clear_stable_frame(self):
        frames = [frame(1, "第一家清风面馆", y=1460, sharpness=5),
                  frame(1.4, "第一家清风面馆", y=1460, sharpness=250),
                  frame(1.8, "第一家清风面馆", y=1460, sharpness=60)]
        shops = infer_shops(frames, [], 10)
        name_shot = next(e for e in shops[0]["evidence"] if e["kind"] == "shop_name")
        self.assertEqual(name_shot["time"], 1.4)
        self.assertEqual(shops[0]["start"], 1)

    def test_street_words_and_queue_numbers_are_not_addresses(self):
        frames = [frame(0, "第一家清风面馆", y=1460), frame(3, "过号优先"),
                  frame(4, "奶路八中图"), frame(5, "3.五博之号", y=1500)]
        shops = infer_shops(frames, [], 10)
        self.assertFalse(any(s["locations"] for s in shops))

    def test_explicit_address_requires_a_supported_address_structure(self):
        frames = [frame(0, "第一家清风面馆", y=1460), frame(3, "地址：青云路18号")]
        shops = infer_shops(frames, [], 10)
        self.assertEqual(shops[0]["locations"], ["青云路18号"])
        self.assertEqual(shops[0]["fact_evidence"]["locations"][0]["source"], "ocr")

    def test_specific_named_dishes_and_local_ocr_character_errors(self):
        frames = [frame(0, "第一家清风面馆", y=1460),
                  frame(2, "猪肉塔可碎肉塔可和牛舌塔克", y=1460),
                  frame(4, "点了一个咖喱羊肉和黄油饼", y=1460),
                  frame(6, "他家的热评榜第一大刀自肉", y=1460)]
        speech = [segment(5.5, 6.5, "他家的热瓶榜第一大刀白肉")]
        shop = infer_shops(frames, speech, 10)[0]
        for dish in ["猪肉塔可", "碎肉塔可", "牛舌塔克", "咖喱羊肉", "黄油饼", "大刀白肉"]:
            self.assertIn(dish, shop["dishes"])
        self.assertEqual(shop["fact_evidence"]["dishes"][0]["source"], "ocr")

    def test_highlights_keep_late_criticism_and_dont_erase_raw_asr(self):
        speech = [segment(i * 3, i * 3 + 2, "这个菜味道不错很推荐") for i in range(8)]
        speech.append(segment(27, 29, "唯一的缺点就是太油了不太好消化"))
        shop = infer_shops([frame(0, "第一家清风面馆", y=1460)], speech, 35)[0]
        self.assertTrue(any("缺点" in h for h in shop["highlights"]))
        self.assertEqual(shop["transcript"][-1]["text"], speech[-1]["text"])

    def test_scene_images_do_not_repeat_the_intro_card(self):
        frames = [frame(1, "第一家清风面馆", y=1460),
                  frame(1.2, "第一家清风面馆", y=1460, sharpness=500),
                  frame(1.6, "清风面馆", y=500, sharpness=1000),
                  frame(6, "牛肉面非常好吃", y=1460)]
        shop = infer_shops(frames, [], 12)[0]
        scenes = [e for e in shop["evidence"] if e["kind"] == "scene"]
        self.assertTrue(scenes)
        self.assertTrue(all(e["time"] >= 4 for e in scenes))

    def test_empty_video_does_not_invent_a_shop(self):
        self.assertEqual(infer_shops([], [], 0), [])


    def test_unnamed_breakfast_and_later_named_meal_are_distinct_stops(self):
        speech=[segment(1,3,"早餐吃包子"),segment(25,27,"中午来吃家常菜"),
                segment(34,36,"我去的是春风饭店"),segment(40,42,"点了牛肉")]
        shops=infer_shops([],speech,50)
        self.assertEqual(len(shops),2)
        self.assertEqual(shops[0]["name_type"],"descriptive")
        self.assertIn("包子",shops[0]["name"])
        self.assertTrue(shops[0]["uncertain"])
        self.assertEqual(shops[1]["name"],"春风饭店")
        self.assertEqual(shops[1]["start"],25)

    def test_unnamed_snack_name_does_not_absorb_the_next_named_shop(self):
        speech=[segment(1,3,"附近有一些卖月饼的"),segment(5,7,"它叫春光糕点"),
                segment(16,18,"晚上有一家寿司店叫海风寿司")]
        shops=infer_shops([],speech,30)
        self.assertEqual([s["name"] for s in shops],["春光糕点","海风寿司"])
        self.assertEqual(shops[0]["start"],1)
        self.assertEqual(shops[1]["start"],16)

    def test_unordinal_subtitle_can_correct_spoken_venue_and_is_not_a_storefront(self):
        frames=[frame(2,"我去的是春风饭店",y=1460)]
        speech=[segment(1,3,"我去的是春丰饭店")]
        shop=infer_shops(frames,speech,10)[0]
        self.assertEqual(shop["name"],"春风饭店")
        self.assertEqual(shop["name_type"],"video_name")
        self.assertTrue(any(e["kind"]=="name_reference" for e in shop["evidence"]))
        self.assertFalse(any(e["kind"]=="shop_name" for e in shop["evidence"]))

    def test_dish_names_and_ordinary_prices_do_not_create_venue_transitions(self):
        speech=[segment(0,2,"第一家清风饭店"),segment(4,6,"这个菜叫糖醋排骨"),
                segment(8,10,"另一道菜是牛肉"),segment(12,14,"最后一个是炒饭")]
        self.assertEqual(len(infer_shops([],speech,20)),1)

    def test_fleeting_name_only_caption_corrects_a_conversational_intro(self):
        frames=[frame(3,"清风楼饭店",y=1450)]
        speech=[segment(2,4,"我去的是清丰楼饭店")]
        shop=infer_shops(frames,speech,10)[0]
        self.assertEqual(shop["name"],"清风楼饭店")
        self.assertEqual(shop["name_evidence"]["original"],"清丰楼饭店")

    def test_unrelated_or_distant_caption_cannot_replace_conversational_name(self):
        frames=[frame(3,"香满楼餐厅",y=1450),frame(15,"清风楼饭店",y=1450)]
        speech=[segment(2,4,"我去的是清风楼饭店")]
        shops=infer_shops(frames,speech,20)
        first=next(s for s in shops if s["start"]<=2)
        self.assertEqual(first["name"],"清风楼饭店")
        self.assertIsNone(first["name_evidence"])

class UnnamedDrinksRegressionTests(unittest.TestCase):
    def test_packaging_cannot_rename_a_meal_or_split_its_later_introduction(self):
        shops=infer_shops([frame(5,"骨汤调料",y=400,height=200)],
            [segment(1,3,"中午来吃家常菜"),segment(12,14,"我去的是春风饭店")],25)
        self.assertEqual(len(shops),1)
        self.assertEqual(shops[0]["name"],"春风饭店")
        self.assertEqual(shops[0]["start"],1)

    def test_unnamed_drinks_create_a_separate_descriptive_stop(self):
        shops=infer_shops([frame(11,"还有一地儿就是靠在岸边喝酒的",y=1460)],
            [segment(1,3,"我去的是春风饭店"),segment(10,12,"还有一点就是靠在安眠喝酒的"),
             segment(13,15,"我去试了两杯")],20)
        self.assertEqual(len(shops),2)
        self.assertEqual(shops[1]["name_type"],"descriptive")
        self.assertEqual(shops[1]["name"],"饮品点位")
        self.assertIsNone(shops[1]["name_evidence"])
        self.assertTrue(shops[1]["uncertain"])

    def test_repeated_caption_resolves_multiple_asr_errors_in_a_long_name(self):
        shops=infer_shops([frame(3,"春风斋老味卷圈",y=1460),frame(3.5,"春风斋老味卷圈",y=1460)],
            [segment(2,4,"这家叫清真春丰摘老肉卷圈")],10)
        self.assertEqual(len(shops),1)
        self.assertEqual(shops[0]["name"],"春风斋老味卷圈")

class StopBoundaryRegressionTests(unittest.TestCase):
    def test_background_label_cannot_name_an_unnamed_drinks_stop(self):
        shops=infer_shops([frame(14,"晴空",y=400,height=120)],
            [segment(10,12,"还有一地儿就是靠在岸边喝酒的")],25)
        self.assertEqual(len(shops),1)
        self.assertEqual(shops[0]["name_type"],"descriptive")
        self.assertEqual(shops[0]["name"],"饮品点位")

    def test_food_lead_in_belongs_to_the_upcoming_named_venue(self):
        speech=[segment(1,3,"我去的是春风饭店"),
                segment(20,22,"最后一天不能遗漏一个东西"),
                segment(22,23,"就是他们的卷圈"),
                segment(24,26,"这家叫清风卷圈")]
        shops=infer_shops([],speech,35)
        self.assertEqual(len(shops),2)
        self.assertEqual(shops[1]["start"],20)
        self.assertNotIn("卷圈",shops[0]["dishes"])
        self.assertIn("卷圈",shops[1]["dishes"])

class SubtitleExcerptRegressionTests(unittest.TestCase):
    def test_subtitle_repairs_review_without_erasing_raw_speech(self):
        raw="它老公对于玩术人太甜了"
        shop=infer_shops([frame(1,"第一家春风饭店",y=1460),
                          frame(5,"它老味对于我来说有点太甜了",y=1460,score=.999)],
                         [segment(4,6,raw)],10)[0]
        self.assertTrue(any("对于我来说有点太甜了" in h for h in shop["highlights"]))
        self.assertEqual(shop["transcript"][0]["text"],raw)
        self.assertEqual(shop["fact_evidence"]["highlights"][0]["original"],raw)
        self.assertTrue(shop["fact_evidence"]["highlights"][0]["context_evidence"])

if __name__ == "__main__":
    unittest.main()
