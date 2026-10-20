import copy
import hashlib
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image
import pytest
from video_agent.technical_flow import ROOT, load_spec, render, validate

def spec():
    return {
        "title":"通用任务 <流程>",
        "nodes":[
            {"id":"input","title":"读取材料","inputs":["source.txt"],"technology":["文件读取"],"outputs":["原始文本"]},
            {"id":"work","title":"执行处理","inputs":["原始文本"],"technology":["文本规范化"],"outputs":["result.txt"]},
        ],
        "edges":[{"from":"input","to":"work"}],
    }

@pytest.mark.parametrize("failure",["cycle","missing","self","duplicate_edge","duplicate_id","disconnected"])
def test_invalid_graphs_fail_before_drawing(failure):
    data=spec()
    if failure=="cycle":data["edges"].append({"from":"work","to":"input"})
    elif failure=="missing":data["edges"][0]["to"]="absent"
    elif failure=="self":data["edges"][0]["to"]="input"
    elif failure=="duplicate_edge":data["edges"].append(copy.deepcopy(data["edges"][0]))
    elif failure=="duplicate_id":data["nodes"][1]["id"]="input"
    else:data["edges"]=[]
    with pytest.raises(ValueError):validate(data)

@pytest.mark.parametrize("field",["inputs","technology","outputs"])
def test_each_step_requires_inputs_technology_and_artifacts(field):
    data=spec();data["nodes"][0][field]=[]
    with pytest.raises(ValueError):validate(data)

def test_project_only_paths_and_directory_prefixes():
    for output in [ROOT,ROOT/"docs",ROOT.parent/"outside-project-flow"]:
        with pytest.raises(ValueError):render(spec(),output,scale=1)

def test_render_actual_png_and_escaped_editable_svg():
    with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="flow-") as directory:
        out=Path(directory)/"task"
        result=render(spec(),out,scale=1)
        with Image.open(out.with_suffix(".png")) as image:
            assert list(image.size)==result["png_dimensions"]
            image.verify()
        xml=ET.parse(out.with_suffix(".svg"))
        ns={"s":"http://www.w3.org/2000/svg"}
        assert xml.find("s:title",ns).text=="通用任务 <流程>"
        labels=[node.text for node in xml.findall(".//s:text",ns)]
        assert all(value in labels for value in ["source.txt","文件读取","result.txt"])
        assert not xml.findall(".//s:image",ns)
        assert result["png_sha256"]==hashlib.sha256(out.with_suffix(".png").read_bytes()).hexdigest()
        assert json.loads(out.with_name("task.validation.json").read_text(encoding="utf-8"))==result

def test_unrelated_task_branches_and_merge_without_project_specific_steps():
    example=load_spec(ROOT/"docs/architecture/technical-flow.example.json")
    # Config order does not need to be topological.
    example["nodes"]=list(reversed(example["nodes"]))
    with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="flow-branch-") as directory:
        result=render(example,Path(directory)/"generic",scale=1)
        assert result["nodes"]==4
        assert result["levels"]==3
        xml=ET.parse(Path(directory)/"generic.svg")
        ns={"s":"http://www.w3.org/2000/svg"}
        labels=[node.text or "" for node in xml.findall(".//s:text",ns)]
        assert labels.index("读取原始数据")<labels.index("导出结果")
        assert any("quality.json" in label for label in labels)
        assert "RapidOCR" not in "".join(labels)

def test_long_labels_wrap_without_losing_artifact_text():
    data=spec()
    data["nodes"][0]["outputs"]=["长文本中间产物"*12+" unique-result.json"]
    data["edges"][0]["label"]="具有较长说明的步骤连接标签"*4
    with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="flow-wrap-") as directory:
        out=Path(directory)/"long"
        render(data,out,scale=1)
        labels=[n.text or "" for n in ET.parse(out.with_suffix(".svg")).findall(".//{http://www.w3.org/2000/svg}text")]
        assert "unique-result.json" in "".join(labels)

def test_bad_config_does_not_overwrite_existing_artifact():
    with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="flow-invalid-") as directory:
        out=Path(directory)/"old"
        out.with_suffix(".png").write_bytes(b"keep")
        data=spec();data["nodes"][0]["outputs"]=[]
        with pytest.raises(ValueError):render(data,out)
        assert out.with_suffix(".png").read_bytes()==b"keep"

def test_oversized_configuration_is_rejected():
    with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="flow-limit-") as directory:
        config=Path(directory)/"big.json";config.write_text(" "*512001,encoding="utf-8")
        with pytest.raises(ValueError):load_spec(config)

def test_default_project_configuration_is_a_valid_complete_chain():
    data,levels=validate(load_spec(ROOT/"docs/architecture/technical-flow.json"))
    assert len(levels)==len(data["nodes"])
    assert any("transcript.json" in item for n in data["nodes"] for item in n["outputs"])
    assert any("notes.html" in item for n in data["nodes"] for item in n["outputs"])
