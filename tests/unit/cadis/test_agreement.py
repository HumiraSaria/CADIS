"""Unit tests for Signal 1 -- Self-Consistency / USC (CadisClaude.md section 6.1)."""

import pytest

from pentestagent.cadis.signals import agreement as ag

# --- Levenshtein + normalized edit similarity ---------------------------------


def test_levenshtein_basic():
    assert ag.levenshtein("abc", "abc") == 0
    assert ag.levenshtein("abc", "abd") == 1
    assert ag.levenshtein("", "abc") == 3


def test_similarity_identical_is_one():
    assert ag.normalized_edit_similarity("nmap -sV t", "nmap -sV t") == 1.0


def test_similarity_one_edit_over_len_three():
    # edit distance 1, max_length 3 -> 1 - 1/3
    assert ag.normalized_edit_similarity("abc", "abd") == pytest.approx(2 / 3)


def test_similarity_completely_different_equal_length_is_zero():
    assert ag.normalized_edit_similarity("abc", "xyz") == pytest.approx(0.0)


def test_similarity_two_empty_strings_is_one():
    assert ag.normalized_edit_similarity("", "") == 1.0


# --- SC(t) and USC(t) ---------------------------------------------------------


def test_five_identical_samples_usc_zero():
    cmds = ["nmap -sV target"] * 5
    assert ag.self_consistency(cmds) == pytest.approx(1.0)
    assert ag.usc(cmds) == pytest.approx(0.0)


def test_single_sample_is_trivially_consistent():
    assert ag.self_consistency(["only one"]) == 1.0
    assert ag.usc(["only one"]) == 0.0
    assert ag.usc([]) == 0.0


def test_two_samples_mean_pairwise():
    # single pair -> SC = sim = 2/3 ; USC = 1/3
    cmds = ["abc", "abd"]
    assert ag.self_consistency(cmds) == pytest.approx(2 / 3)
    assert ag.usc(cmds) == pytest.approx(1 / 3)


def test_three_samples_mean_over_all_pairs():
    # pairs: (abc,abc)=1.0, (abc,abd)=2/3, (abc,abd)=2/3 ; mean = (1 + 2/3 + 2/3)/3
    cmds = ["abc", "abc", "abd"]
    expected_sc = (1.0 + 2 / 3 + 2 / 3) / 3
    assert ag.self_consistency(cmds) == pytest.approx(expected_sc)
    assert ag.usc(cmds) == pytest.approx(1 - expected_sc)


# --- similarity strategy interface --------------------------------------------


def test_get_similarity_default_is_edit():
    assert ag.get_similarity("edit") is ag.normalized_edit_similarity


def test_embedding_similarity_is_ablation_only():
    with pytest.raises(NotImplementedError):
        ag.get_similarity("embedding")("a", "b")


def test_get_similarity_unknown_raises():
    with pytest.raises(ValueError):
        ag.get_similarity("bogus")
