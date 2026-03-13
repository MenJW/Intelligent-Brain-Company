from intelligent_brain_company.services.llm_client import _extract_first_json_value


def test_extract_first_json_object_from_mixed_text() -> None:
    text = (
        "下面是我的分析过程（可忽略）...\n"
        "{\"solutions\": [{\"name\": \"A\", \"summary\": \"ok\", \"feasibility_score\": 7}]}\n"
        "以上是结果"
    )
    extracted = _extract_first_json_value(text)
    assert extracted is not None
    assert extracted.startswith("{")
    assert '"solutions"' in extracted


def test_extract_first_json_array_from_mixed_text() -> None:
    text = (
        "先给出思考，再给结果。\n"
        "[{\"name\": \"A\", \"summary\": \"ok\"}, {\"name\": \"B\", \"summary\": \"ok\"}]\n"
        "以上。"
    )
    extracted = _extract_first_json_value(text)
    assert extracted is not None
    assert extracted.startswith("[")
    assert '"name"' in extracted
