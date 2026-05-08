from bench.runner.parsing import parse_letter


def test_answer_tag():
    assert parse_letter("<answer>C</answer>") == "C"
    assert parse_letter("blah <answer>e</answer> blah") == "E"


def test_letter_first():
    assert parse_letter("A") == "A"
    assert parse_letter("Option D.") == "D"
    assert parse_letter("Answer: B") == "B"
    assert parse_letter("(C)") == "C"


def test_none_phrase():
    assert parse_letter("None of the above match.") == "E"
    assert parse_letter("none of these") == "E"


def test_ordinal_phrases():
    assert parse_letter("the second one looks closest") == "B"
    assert parse_letter("the third candidate") == "C"


def test_letter_anywhere():
    assert parse_letter("After review I'd say D.") == "D"


def test_empty_or_unparseable():
    assert parse_letter("") is None
    assert parse_letter("I cannot answer this.") is None
