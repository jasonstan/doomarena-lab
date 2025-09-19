from tools.check_thresholds import evaluate

def test_evaluate_mixes_warn_and_fail():
    rows = [
        {"exp":"a","trials":"2","successes":"1"},
        {"exp":"a","trials":"4","successes":"2"},
        {"exp":"b","trials":"2","successes":"2"},
    ]
    th = {"a":{"min_trials":6,"max_asr":0.6}, "b":{"max_asr":0.25}}
    md_rows, worst = evaluate(rows, th)
    # a: trials 6 OK, asr 0.5 <= 0.6 PASS
    # b: asr 1.0 > 0.25 FAIL
    status = {r["exp"]: r["status"] for r in md_rows}
    assert status["a"] == "PASS"
    assert status["b"] == "FAIL"
    assert worst == 1
