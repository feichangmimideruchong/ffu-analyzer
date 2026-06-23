from retrieval import _Bm25, tokenize


class TestTokenize:
    def test_lowercases(self):
        assert tokenize("Hello WORLD") == ["hello", "world"]

    def test_keeps_codes(self):
        # AMA codes and doc numbers should survive as single tokens.
        assert "afb.623" in tokenize("enligt AFB.623")
        assert "m-10.2-2001" in tokenize("ritning M-10.2-2001")

    def test_swedish_letters(self):
        assert tokenize("Förfrågningsunderlag") == ["förfrågningsunderlag"]

    def test_strips_punctuation(self):
        assert tokenize("hello, world!") == ["hello", "world"]


class TestBm25:
    def test_ranks_relevant_doc_higher(self):
        corpus = [
            tokenize("the contractor must submit the tender via tendsign"),
            tokenize("canadian goldenrod must be dug up with roots"),
            tokenize("negative pricing is not accepted in the bid form"),
        ]
        bm = _Bm25(corpus)
        scores = bm.scores("how is the tender submitted via tendsign")
        assert scores.argmax() == 0

    def test_unknown_term_zero_scores(self):
        corpus = [tokenize("alpha beta"), tokenize("gamma delta")]
        bm = _Bm25(corpus)
        scores = bm.scores("nonexistentterm")
        assert scores.sum() == 0.0

    def test_empty_corpus_safe(self):
        bm = _Bm25([])
        assert bm.scores("anything").shape == (0,)
