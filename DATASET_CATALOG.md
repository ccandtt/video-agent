# 数据集总览

更新日期：2026-10-19。当前已登记 **8 条来源**（7 条已生成笔记，新增课程暂下载第 1 集、待确认整理范围），覆盖 **美食探店、知识讲解、商品推荐与评测** 三类场景。

本文件记录原始来源、内容、数据位置与产物，是项目样例数据的统一入口。新增或删除视频、补充产物、处理状态变化时同步更新。云端“我的笔记”按登录用户单独管理，本表不表示对应总结当前一定保存在云端。

## 样例清单

| 视频 ID | 原始链接 | 类别 | 视频内容简述 | 时长 | 处理状态／结果 |
| --- | --- | --- | --- | --- | --- |
| BV1cHen6EEen | [北京纯吃攻略！没废话！狂吃11家20年老店和正宗小店](https://www.bilibili.com/video/BV1cHen6EEen/) | 美食探店 · 多店攻略 | 介绍北京 11 家餐饮店，包含店铺外观、披萨与甜品等菜品、部分价格及口味评价；按店铺整理简介、推荐菜单、菜品图片和时间戳。 | 07:27 | 本地自动流程已跑通；11 家店、93 张关联截图；HTML、Markdown、JSON 已保存。 |
| BV1aCWszYE31 | [反直觉现象：彻底搞懂辛普森悖论！4个关键反问识破生活中的数据陷阱](https://www.bilibili.com/video/BV1aCWszYE31/) | 知识讲解 · 统计科普 | 用医院死亡率和大学录取案例解释总体与分组趋势反转、加权平均和混淆变量，整理样本来源、群体结构、隐藏因素、细分比较四个反问。 | 05:48 | 本地 OCR／ASR 完成；内容经源视频整理，9 个章节、9 张截图；HTML、Markdown 已保存。 |
| BV16Y4y1z72G | [因果推断1小时入门 causal inference in statistics: a primer](https://www.bilibili.com/video/BV16Y4y1z72G/) | 知识讲解 · 课程讲义 | 从观察、干预与反事实出发，介绍辛普森悖论、结构因果模型、因果图与 d-separation、后门／前门调整、逆概率加权和反事实推理。 | 1:00:25 | 本地 OCR／ASR 完成；已生成 8 章、23 页 PDF 讲义，含 16 张源视频截图及可点击目录；另有 31 页博主原课件视频提取版，保留原画面、OCR 搜索层和逐页书签。 |
| BV1u7Hj6HEV2 | [如果这个城市消失 那全球幸福指数恐怕会下降一半](https://www.bilibili.com/video/BV1u7Hj6HEV2/) | 美食探店 · 街头小摊 | 天津美食行程，涵盖包子早餐、天津菜、月饼、寿司、岸边饮品、两处刨冰、卷圈及饺子；部分点位没有可确认店名。 | 03:29 | 自动流程已跑通；9 处探吃点，其中 7 处有视频名称、2 处使用描述性名称；55 张关联截图；HTML、Markdown、JSON 已保存。 |
| BV1YHHC6YEsh | [降温也要将睡得舒服进行到底](https://www.bilibili.com/video/BV1YHHC6YEsh/) | 商品推荐与评测 · 家居寝具 | M2 STUDIO 睡衣、与眠家抱枕、壹月叁拾半边绒毛毯及蚂蚁同学睡眠袜，保留视频标价、使用体验与取舍。 | 08:12 | 原视频及完整语音已保存；4 节图文笔记、8 张截图；单视频整理完成。 |
| BV1TW816JE49 | [小小水晶原产地无痛拿下！](https://www.bilibili.com/video/BV1TW816JE49/) | 商品推荐与评测 · 水晶饰品选购 | 分享雾里天然水晶店铺与蔚神原创珠宝设计的手串、定制款、项链及报价与售后说法；内容是选购分享，不是线下产地探店。 | 10:04 | 原视频及完整语音已保存；6 节图文笔记、14 张截图；单视频整理完成。 |
| BV182HY6iEB5 | [无广！！《如何在卧室当皇帝》教程](https://www.bilibili.com/video/BV182HY6iEB5/) | 商品推荐与评测 · 卧室好物 | 床边灯、托盘小物、重力眼罩、枕具、电脑桌、趴趴枕、长柄粘毛器与平板支架的使用分享。 | 04:12 | 原视频及完整语音已保存；6 节图文笔记、11 张截图；单视频整理完成。 |
| BV1XYsSzgEEc | [因果推断与机器学习](https://www.bilibili.com/video/BV1XYsSzgEEc/) | 知识讲解 · 多分集课程 | 来源目录共9集，涉及因果推理、匹配、内生性、双重差分、合成控制、机器学习及论文设计；尚未整理课程正文。 | 全课程约21:59:42；第1集3:17:29 | 第1集原视频已下载并通过抽样解码，等待用户确认分集范围；尚未生成笔记。 |

时长按秒四舍五入显示；处理方式与规模依据当前本地结果及验证文件登记。“知识讲解”两项和“商品推荐与评测”三项是源视频单次整理样例，不表示工具已开放这些类别的通用自动生成；一小时课程也超出当前网页版 20 分钟限制。

## 数据与产物地址

项目根目录：E:/Workspace/video_agent/。下列链接均指向项目内的实际文件，离开本机后需要连同对应目录一起迁移。

| 视频 ID | 原始视频／元数据 | OCR／语音文本 | 内容结构／图文总结 | 验证记录 |
| --- | --- | --- | --- | --- |
| BV1cHen6EEen | [原始视频](data/raw/BV1cHen6EEen/video.mp4) · [来源元数据](data/raw/BV1cHen6EEen/video.info.json) | [OCR](data/processed/BV1cHen6EEen/ocr.json) · [转写](data/processed/BV1cHen6EEen/transcript.json) | [HTML](data/processed/BV1cHen6EEen/notes.html) · [Markdown](data/processed/BV1cHen6EEen/notes.md) · [结构化结果](data/processed/BV1cHen6EEen/notes.json) · [主题与概括](data/processed/BV1cHen6EEen/classification.json) | [验证结果](data/processed/BV1cHen6EEen/validation.json) |
| BV1aCWszYE31 | [原始视频](data/raw/BV1aCWszYE31/video.mp4) · [来源元数据](data/raw/BV1aCWszYE31/video.info.json) | [OCR](data/processed/BV1aCWszYE31/ocr.json) · [转写](data/processed/BV1aCWszYE31/transcript.json) | [HTML](data/processed/BV1aCWszYE31/notes.html) · [Markdown](data/processed/BV1aCWszYE31/notes.md) · [章节内容](data/processed/BV1aCWszYE31/summary.json) | [验证结果](data/processed/BV1aCWszYE31/summary_validation.json) |
| BV16Y4y1z72G | [原始视频](data/raw/BV16Y4y1z72G/video.mp4) · [来源元数据](data/raw/BV16Y4y1z72G/video.info.json) | [OCR](data/processed/BV16Y4y1z72G/ocr.json) · [转写](data/processed/BV16Y4y1z72G/transcript.json) | [PDF 讲义](output/pdf/因果推断入门_视频讲义.pdf) · [博主原课件（31 页）](output/pdf/因果推断_博主原课件_完整31页.pdf) · [讲义内容结构](data/processed/BV16Y4y1z72G/handout.json) | [PDF 验证结果](data/processed/BV16Y4y1z72G/pdf_validation.json) |
| BV1u7Hj6HEV2 | [原始视频](data/raw/BV1u7Hj6HEV2/video.mp4) · [来源元数据](data/raw/BV1u7Hj6HEV2/video.info.json) | [OCR](data/processed/BV1u7Hj6HEV2/ocr.json) · [转写](data/processed/BV1u7Hj6HEV2/transcript.json) | [HTML](data/processed/BV1u7Hj6HEV2/notes.html) · [Markdown](data/processed/BV1u7Hj6HEV2/notes.md) · [结构化结果](data/processed/BV1u7Hj6HEV2/notes.json) · [主题与概括](data/processed/BV1u7Hj6HEV2/classification.json) | [验证结果](data/processed/BV1u7Hj6HEV2/validation.json) |
| BV1YHHC6YEsh | [原视频](data/raw/BV1YHHC6YEsh/video.mp4) · [元数据](data/raw/BV1YHHC6YEsh/video.info.json) | [OCR](data/processed/BV1YHHC6YEsh/ocr.json) · [转写](data/processed/BV1YHHC6YEsh/transcript.json) | [HTML](data/processed/BV1YHHC6YEsh/notes.html) · [Markdown](data/processed/BV1YHHC6YEsh/notes.md) · [内容结构](data/processed/BV1YHHC6YEsh/summary.json) · [分类](data/processed/BV1YHHC6YEsh/classification.json) | [验证结果](data/processed/BV1YHHC6YEsh/summary_validation.json) |
| BV1TW816JE49 | [原视频](data/raw/BV1TW816JE49/video.mp4) · [元数据](data/raw/BV1TW816JE49/video.info.json) | [OCR](data/processed/BV1TW816JE49/ocr.json) · [转写](data/processed/BV1TW816JE49/transcript.json) | [HTML](data/processed/BV1TW816JE49/notes.html) · [Markdown](data/processed/BV1TW816JE49/notes.md) · [内容结构](data/processed/BV1TW816JE49/summary.json) · [分类](data/processed/BV1TW816JE49/classification.json) | [验证结果](data/processed/BV1TW816JE49/summary_validation.json) |
| BV182HY6iEB5 | [原视频](data/raw/BV182HY6iEB5/video.mp4) · [元数据](data/raw/BV182HY6iEB5/video.info.json) | [OCR](data/processed/BV182HY6iEB5/ocr.json) · [转写](data/processed/BV182HY6iEB5/transcript.json) | [HTML](data/processed/BV182HY6iEB5/notes.html) · [Markdown](data/processed/BV182HY6iEB5/notes.md) · [内容结构](data/processed/BV182HY6iEB5/summary.json) · [分类](data/processed/BV182HY6iEB5/classification.json) | [验证结果](data/processed/BV182HY6iEB5/summary_validation.json) |
| BV1XYsSzgEEc | [第1集视频](data/raw/BV1XYsSzgEEc/video.mp4) · [第1集元数据](data/raw/BV1XYsSzgEEc/video.info.json) · [全课程分集目录](data/raw/BV1XYsSzgEEc/source.pages.json) | 尚未提取 | [分类](data/processed/BV1XYsSzgEEc/classification.json) · [整理范围状态](data/processed/BV1XYsSzgEEc/course_scope.json)；尚未生成笔记 | [下载验证](data/processed/BV1XYsSzgEEc/download_validation.json) |

原始数据目录为 data/raw/视频ID/；处理结果目录为 data/processed/视频ID/。OCR 截图保存在对应处理目录的 frames/，课程讲义插图保存在其 figures/。

## 数据规模与维护

| 视频 ID | 完整 OCR 时间点 | 完整 ASR 段落 | 成品选用截图 |
| --- | --- | --- | --- |
| BV1cHen6EEen | 683 | 259 | 93 张关联截图 |
| BV1aCWszYE31 | 174 | 156 | 9 张总结截图 |
| BV16Y4y1z72G | 101 | 648 | 16 张讲义插图；另有 31 页原课件（全视频逐秒补扫 3626 次） |
| BV1u7Hj6HEV2 | 246 | 143 | 55 张关联截图 |
| BV1YHHC6YEsh | 62 | 359 | 8 张图文笔记截图 |
| BV1TW816JE49 | 76 | 483 | 14 张图文笔记截图 |
| BV182HY6iEB5 | 32 | 175 | 11 张图文笔记截图 |
| BV1XYsSzgEEc | 尚未提取 | 尚未提取 | 尚未生成；等待确认分集范围 |

新增的三条商品样例使用 8 秒间隔画面 OCR，结合完整语音与代表画面核看整理；采样缓存已完成，不代表逐帧分析。原始视频、音频与画面均保存在项目目录。

- 以视频 ID 区分样例，同一视频的分离音轨、不同清晰度文件、重复生成的网页和云端任务不重复计数。
- 原始链接用于追溯来源；原视频和识别缓存用于复现；HTML／Markdown／PDF 用于阅读，JSON 保留结构与依据。
- 删除云端总结不会自动删除这里的本地原视频和缓存；本地数据删除后，应同步修改本表的状态及地址。
- OCR、ASR 和内容整理仍可能存在误识别或解释偏差；验证文件主要记录程序、引用和人工检查结果，不能视为所有语义均已核实。
- 当前为人工维护的目录文件，不是实时云端任务数据库；新增数据后需要同步登记。

本地统一工具首页为 http://127.0.0.1:8765/；启动后可在同一页生成、查看历史笔记、分类筛选与搜索。因果讲义另有可在工具中打开的 [PDF 副本](data/processed/BV16Y4y1z72G/lecture.pdf)。

项目范围见 [PROJECT_BRIEF](PROJECT_BRIEF.md)，使用方法见 [README](README.md)，具体问题见 [BUG 记录](docs/BUG_LOG.md)。
