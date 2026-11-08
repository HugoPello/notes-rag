import pytest

from app.chunking import Chunk
from app.store import get_collection, replace_document, search


def test_closest_vector_first(tmp_path):
    collection = get_collection(tmp_path)
    chunks = [Chunk("a.pdf", 1, "about cats"), Chunk("a.pdf", 2, "about dogs"), Chunk("a.pdf", 3, "about fish")]
    replace_document(collection, "a.pdf", chunks, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])

    results = search(collection, [0, 1, 0])

    assert results[0].chunk == Chunk("a.pdf", 2, "about dogs")
    assert results[0].score == pytest.approx(1.0, abs=1e-4)
    assert results[0].score > results[1].score


def test_repeated_replace_does_not_duplicate(tmp_path):
    collection = get_collection(tmp_path)
    chunks = [Chunk("a.pdf", 1, "one"), Chunk("a.pdf", 1, "two")]
    vectors = [[1, 0, 0], [0, 1, 0]]

    replace_document(collection, "a.pdf", chunks, vectors)
    replace_document(collection, "a.pdf", chunks, vectors)

    assert collection.count() == 2


def test_shorter_second_version_removes_orphans(tmp_path):
    collection = get_collection(tmp_path)
    long_version = [Chunk("a.pdf", 1, "one"), Chunk("a.pdf", 1, "two"), Chunk("a.pdf", 2, "three")]
    replace_document(collection, "a.pdf", long_version, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])

    replace_document(collection, "a.pdf", [Chunk("a.pdf", 1, "only")], [[1, 0, 0]])

    assert collection.count() == 1
    assert search(collection, [1, 0, 0])[0].chunk.text == "only"


def test_replacing_one_document_keeps_the_other(tmp_path):
    collection = get_collection(tmp_path)
    replace_document(collection, "a.pdf", [Chunk("a.pdf", 1, "from a")], [[1, 0, 0]])
    replace_document(collection, "b.pdf", [Chunk("b.pdf", 1, "from b")], [[0, 1, 0]])

    replace_document(collection, "a.pdf", [Chunk("a.pdf", 1, "new a")], [[1, 0, 0]])

    texts = {result.chunk.text for result in search(collection, [1, 1, 0])}
    assert texts == {"new a", "from b"}


def test_search_empty_collection(tmp_path):
    assert search(get_collection(tmp_path), [1, 0, 0]) == []


def test_k_larger_than_count(tmp_path):
    collection = get_collection(tmp_path)
    replace_document(collection, "a.pdf", [Chunk("a.pdf", 1, "one")], [[1, 0, 0]])

    assert len(search(collection, [1, 0, 0], k=10)) == 1


def test_mismatched_lengths_raise(tmp_path):
    collection = get_collection(tmp_path)
    with pytest.raises(ValueError):
        replace_document(collection, "a.pdf", [Chunk("a.pdf", 1, "one")], [])
