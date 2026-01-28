import json
from pathlib import Path

from src.engine.evaluation import load_golden_tasks


def test_load_golden_tasks_filters_invalid(tmp_path: Path) -> None:
    payload = [
        {"commander_name": "Atraxa, Praetors' Voice"},
        {"commander_name": ""},
        "bad",
    ]
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    tasks = load_golden_tasks(path)
    assert len(tasks) == 1
    assert tasks[0].commander_name == "Atraxa, Praetors' Voice"
