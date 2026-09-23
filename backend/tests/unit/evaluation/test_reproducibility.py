from backend.app.evaluation.reproducibility import _first_difference


def test_first_byte_difference_is_concise() -> None:
    assert (
        _first_difference(b"abc", b"axc")
        == "first differing byte offset 1; sizes 3 and 3"
    )


def test_length_difference_is_reported() -> None:
    assert (
        _first_difference(b"abc", b"abcx")
        == "first differing byte offset 3; sizes 3 and 4"
    )
