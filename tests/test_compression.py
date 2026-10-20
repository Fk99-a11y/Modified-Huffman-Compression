
"""Tests for the Modified Huffman compression algorithm."""

import pytest

from src.compression import (
    build_huffman_codes,
    build_original_codes,
    compress_text,
)


def test_build_huffman_codes():
    frequencies = {
        "a": 17,
        "b": 22,
        "c": 15,
        "d": 14,
        "e": 30,
        "f": 2,
    }

    codes = build_huffman_codes(frequencies)

    assert set(codes.keys()) == set(frequencies.keys())
    assert all(code for code in codes.values())
    assert all(set(code) <= {"0", "1"} for code in codes.values())


def test_empty_text():
    result = compress_text("")

    assert result.bitstream == ""
    assert result.frequencies == {}
    assert result.codes == {}
    assert result.original_size_bytes == 0


def test_single_symbol():
    result = compress_text("AAAAAA", minimum_probability_limit=0.05)

    assert result.frequencies == {"A": 6}
    assert result.bitstream
    assert set(result.bitstream) <= {"0", "1"}


def test_probability_limit_groups_rare_symbols():
    result = compress_text("ABBBBBBB", minimum_probability_limit=0.25)

    assert result.others_symbols == ["A"]
    assert result.frequencies["A"] == 1
    assert result.frequencies["B"] == 7
    assert result.codes["A"] == "00"
    assert result.codes["B"] == "1"


def test_zero_probability_limit_does_not_group_symbols():
    result = compress_text("ABBBBBBB", minimum_probability_limit=0.0)

    assert result.others_symbols == []
    assert set(result.codes.keys()) == {"A", "B"}


def test_all_symbols_can_be_grouped():
    result = compress_text("ABBA", minimum_probability_limit=1.0)

    assert result.others_symbols == ["A", "B"]
    assert result.codes["A"] == "00"
    assert result.codes["B"] == "01"
    assert result.bitstream == "00010100"


def test_invalid_probability_limit():
    with pytest.raises(ValueError):
        compress_text("ABC", minimum_probability_limit=-0.1)

    with pytest.raises(ValueError):
        compress_text("ABC", minimum_probability_limit=1.1)


def test_bitstream_contains_only_binary_digits():
    result = compress_text("Hello 123!", minimum_probability_limit=0.0)

    assert set(result.bitstream) <= {"0", "1"}


def test_original_codes_have_fixed_length():
    codes, width = build_original_codes(["A", "B", "C", "D"])

    assert width == 2
    assert set(codes.keys()) == {"A", "B", "C", "D"}
    assert all(len(code) == width for code in codes.values())


def test_compression_result_contains_all_symbols():
    text = "Modified Huffman Compression"
    result = compress_text(text, minimum_probability_limit=0.05)

    assert set(result.frequencies.keys()) == set(text)
    assert set(result.codes.keys()) == set(text)
    assert result.original_text == text
    assert result.original_size_bytes == len(text.encode("utf-8"))


def test_lecture_example():
    text = "abcazdafcqdadcuabapd"
    result = compress_text(text, minimum_probability_limit=0.05)

    assert len(text) == 20
    assert result.others_symbols == ["f", "p", "q", "u", "z"]
    assert sum(
        result.frequencies[symbol]
        for symbol in result.others_symbols
    ) == 5
    assert len(result.bitstream) == 65
from src.compression import build_huffman_codes


def test_huffman_codes_are_prefix_free():
    frequencies = {
        "a": 5,
        "b": 3,
        "c": 2,
        "d": 1,
    }

    codes = build_huffman_codes(frequencies)

    for symbol1, code1 in codes.items():
        for symbol2, code2 in codes.items():
            if symbol1 != symbol2:
                assert not code2.startswith(code1)


def test_huffman_codes_are_deterministic():
    frequencies1 = {"a": 5, "b": 3, "c": 2}
    frequencies2 = {"c": 2, "a": 5, "b": 3}

    assert build_huffman_codes(frequencies1) == (
        build_huffman_codes(frequencies2)
    )
