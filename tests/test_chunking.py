import pytest

from app.chunking import chunk_pages, split_text

WORDS = [f"w{i}" for i in range(200)]
TEXT = " ".join(WORDS)


def test_empty_and_whitespace_only_give_no_chunks():
    assert split_text("") == []
    assert split_text("  \n\t ") == []


def test_short_text_is_one_normalized_chunk():
    assert split_text("hello   world") == ["hello world"]


def test_whitespace_is_normalized():
    assert split_text("a\n\n b\t c") == ["a b c"]


def test_chunks_respect_size():
    chunks = split_text(TEXT, size=50, overlap=10)
    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)


def test_no_split_words():
    chunks = split_text(TEXT, size=50, overlap=10)
    original = set(WORDS)
    assert all(token in original for c in chunks for token in c.split())


def test_every_word_is_covered():
    chunks = split_text(TEXT, size=50, overlap=10)
    covered = {token for c in chunks for token in c.split()}
    assert covered == set(WORDS)


def test_consecutive_chunks_overlap():
    chunks = split_text(TEXT, size=50, overlap=10)
    for current, following in zip(chunks, chunks[1:]):
        assert current.split()[-1] in following.split()


def test_text_without_spaces_terminates_with_hard_cuts():
    chunks = split_text("x" * 500, size=50, overlap=10)
    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)


def test_overlap_not_smaller_than_size_raises():
    with pytest.raises(ValueError):
        split_text("some text", size=10, overlap=10)


def test_chunk_pages_keeps_page_numbers_and_never_mixes_pages():
    chunks = chunk_pages("doc.pdf", ["alpha beta", "", "gamma"])
    assert [c.page for c in chunks] == [1, 3]
    assert all(c.document == "doc.pdf" for c in chunks)
    assert not any("alpha" in c.text and "gamma" in c.text for c in chunks)
