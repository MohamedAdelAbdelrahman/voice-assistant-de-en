import json
import time

from pipeline.timing import LatencyLog


def test_stage_records_duration_and_meta(tmp_path):
    log = LatencyLog(tmp_path / "lat.jsonl")
    with log.stage("stt", file="a.wav") as out:
        time.sleep(0.01)
        out["language"] = "de"

    rec = log.last("stt")
    assert rec["ms"] >= 10
    assert rec["file"] == "a.wav" and rec["language"] == "de"

    lines = (tmp_path / "lat.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["stage"] == "stt"


def test_new_run_separates_records():
    log = LatencyLog()
    with log.stage("stt"):
        pass
    first = log.run_id
    log.new_run()
    assert log.run_id != first
    assert log.last("stt") is None
    assert log.mark("first_audio") >= 0
