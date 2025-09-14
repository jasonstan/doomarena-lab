import os, json, datetime, random
from typing import Dict, Any

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def jsonl_writer(path: str):
    ensure_dir(os.path.dirname(path))
    def write(record: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return write

def experiment_header(config: dict) -> dict:
    # Keep this small but informative
    return {
        "event": "header",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "config": config,
        "seed": config.get("seed", None),
        "rand_hint": random.random(),  # helps confirm seeding in debugging
    }
