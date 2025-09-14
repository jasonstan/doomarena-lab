import os, json
from adapters.results_logger import jsonl_writer, experiment_header

def test_jsonl_writer_creates_file(tmp_path):
    p = tmp_path / "out" / "log.jsonl"
    write = jsonl_writer(str(p))
    write(experiment_header({"seed": 1}))
    write({"event": "trial", "trial": 1})
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        lines = [json.loads(x) for x in f.read().splitlines()]
    assert lines[0]["event"] == "header"
    assert lines[1]["event"] == "trial"
