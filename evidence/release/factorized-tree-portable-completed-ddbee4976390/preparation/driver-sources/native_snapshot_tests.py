"""Extract the exact historical tests and select the retained 916-node suite."""
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import xml.etree.ElementTree as ET

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write


def main():
    commit=subprocess.check_output(["git","rev-parse","99e3dd4"],cwd=ROOT,text=True).strip()
    destination=DEST / "test-suite-99e3dd4"
    xml=ROOT / "evidence/release/full-suite-lifted-fabrication-selection.xml"
    cases=ET.parse(xml).getroot().findall(".//testcase")
    assert len(cases)==916 and not ET.parse(xml).getroot().findall(".//failure") and not ET.parse(xml).getroot().findall(".//error")
    packed=subprocess.check_output(["git","archive","--format=tar",commit,"tests","pyproject.toml","docs/ifc-network-spec.json"],cwd=ROOT)
    files=[]
    with tarfile.open(fileobj=io.BytesIO(packed)) as archive:
        for member in archive:
            if member.isdir():
                continue
            assert member.isfile()
            parts=PurePosixPath(member.name).parts
            assert not any(part==".." for part in parts)
            path=destination.joinpath(*parts)
            assert path.resolve().is_relative_to(destination.resolve())
            data=archive.extractfile(member).read()
            if path.exists():
                assert path.read_bytes()==data
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
            files.append({"path":member.name,"sha256":sha(path),"bytes":len(data)})
    nodes=[]
    for case in cases:
        components=case.attrib["classname"].split(".")
        matches=[]
        for length in range(1,len(components)+1):
            path=destination.joinpath(*components[:length]).with_suffix(".py")
            if path.is_file():
                suffix=components[length:]+[case.attrib["name"]]
                matches.append(str(path.relative_to(ROOT)).replace("\\","/")+"::"+"::".join(suffix))
        assert len(matches)==1,(case.attrib,matches)
        nodes.append(matches[0])
    assert len(set(nodes))==916
    args=DEST / "selected-916-tests.args"
    args.write_text("\n".join(nodes)+"\n",encoding="utf-8")
    result={"status":"EXACT_HISTORICAL_TEST_NODES_STAGED","git_commit":commit,"destination":str(destination),
        "selection_xml":str(xml),"selection_xml_sha256":sha(xml),"node_count":len(nodes),
        "node_manifest":str(args),"node_manifest_sha256":sha(args),"files":files,
        "active_test_files_used":False,"source_runtime":"94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"}
    json_write(EVIDENCE / "test-selection.json",result)
    print(json.dumps({k:result[k] for k in ["status","node_count","git_commit","node_manifest_sha256"]}),flush=True)


if __name__=="__main__":
    main()
