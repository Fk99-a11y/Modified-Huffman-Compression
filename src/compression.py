
"""Modified Huffman encoder.

Symbols whose probabilities are <= the configured limit are grouped
under the special symbol "Others".

A symbol in Others is encoded as:
    Huffman code of Others + fixed-length original symbol code.

This module prepares a logical bitstream. Packing the bits into a
binary file is handled by bit_utils.py / file_format.py.
"""

from collections import Counter
from dataclasses import dataclass
from heapq import heappush, heappop
from math import ceil, log2
from pathlib import Path


@dataclass
class HuffmanNode:
    """A node in the Huffman tree."""

    frequency: int
    symbol: str | None = None
    left: "HuffmanNode | None" = None
    right: "HuffmanNode | None" = None


@dataclass
class CompressionResult:
    """Data prepared for the binary-file writer."""

    bitstream: str
    codes: dict[str, str]
    original_codes: dict[str, str]
    frequencies: dict[str, int]
    probabilities: dict[str, float]
    others_symbols: list[str]
    minimum_probability_limit: float
    original_size_bytes: int
    original_text: str


def build_huffman_codes(
    frequencies: dict[str, int],
) -> dict[str, str]:
    """Build Huffman codes from symbol frequencies."""

    if not frequencies:
        return {}

    heap = []
    counter = 0

    # Sorting makes tie handling reproducible.
    for symbol, frequency in sorted(frequencies.items()):
        node = HuffmanNode(frequency=frequency, symbol=symbol)
        heappush(heap, (frequency, counter, node))
        counter += 1

    # Merge the two least-frequent nodes until one root remains.
    while len(heap) > 1:
        freq1, _, left = heappop(heap)
        freq2, _, right = heappop(heap)

        parent = HuffmanNode(
            frequency=freq1 + freq2,
            left=left,
            right=right,
        )

        heappush(heap, (parent.frequency, counter, parent))
        counter += 1

    root = heappop(heap)[2]
    codes = {}

    def walk(node: HuffmanNode, prefix: str) -> None:
        if node.symbol is not None:
            # A single-symbol tree needs a non-empty code.
            codes[node.symbol] = prefix or "0"
            return

        if node.left is not None:
            walk(node.left, prefix + "1")

        if node.right is not None:
            walk(node.right, prefix + "0")

    walk(root, "")
    return codes


def build_original_codes(
    symbols: list[str],
) -> tuple[dict[str, str], int]:
    """Assign fixed-length codes to the original alphabet.

    The alphabet is sorted so the mapping is deterministic.
    """

    alphabet = sorted(symbols)

    if not alphabet:
        return {}, 0

    # At least one bit is used, even for a one-symbol alphabet.
    code_width = max(1, ceil(log2(len(alphabet))))

    original_codes = {
        symbol: format(index, f"0{code_width}b")
        for index, symbol in enumerate(alphabet)
    }

    return original_codes, code_width


def compress_text(
    text: str,
    minimum_probability_limit: float = 0.05,
) -> CompressionResult:
    """Compress text using the lecture's Modified Huffman method.

    The returned bitstream is a string of '0' and '1' characters.
    It is NOT yet packed into a binary file.
    """

    if not 0 <= minimum_probability_limit <= 1:
        raise ValueError(
            "Minimum probability limit must be between 0 and 1."
        )

    if not text:
        return CompressionResult(
            bitstream="",
            codes={},
            original_codes={},
            frequencies={},
            probabilities={},
            others_symbols=[],
            minimum_probability_limit=minimum_probability_limit,
            original_size_bytes=0,
            original_text=text,
        )

    frequencies = dict(Counter(text))
    total_symbols = len(text)

    probabilities = {
        symbol: count / total_symbols
        for symbol, count in frequencies.items()
    }

    # Symbols at or below the limit are grouped into Others.
    others_symbols = sorted(
        symbol
        for symbol, probability in probabilities.items()
        if probability <= minimum_probability_limit
    )

    normal_symbols = sorted(
        symbol
        for symbol in frequencies
        if symbol not in others_symbols
    )

    # Build the reduced frequency table for Huffman coding.
    grouped_frequencies = {
        symbol: frequencies[symbol]
        for symbol in normal_symbols
    }

    if others_symbols:
        grouped_frequencies["Others"] = sum(
            frequencies[symbol] for symbol in others_symbols
        )

    huffman_codes = build_huffman_codes(grouped_frequencies)

    # Original fixed-length codes are used only for symbols in Others.
    original_codes, _ = build_original_codes(list(frequencies))

    bit_parts = []

    for symbol in text:
        if symbol in others_symbols:
            # Modified rule: Others code + original symbol code.
            bit_parts.append(huffman_codes["Others"])
            bit_parts.append(original_codes[symbol])
        else:
            bit_parts.append(huffman_codes[symbol])

    bitstream = "".join(bit_parts)

    # Report the effective code used for each original symbol.
    effective_codes = {}

    for symbol in frequencies:
        if symbol in others_symbols:
            effective_codes[symbol] = (
                huffman_codes["Others"] + original_codes[symbol]
            )
        else:
            effective_codes[symbol] = huffman_codes[symbol]

    return CompressionResult(
        bitstream=bitstream,
        codes=effective_codes,
        original_codes=original_codes,
        frequencies=frequencies,
        probabilities=probabilities,
        others_symbols=others_symbols,
        minimum_probability_limit=minimum_probability_limit,
        original_size_bytes=len(text.encode("utf-8")),
        original_text=text,
    )


def encode_file(
    input_path: str | Path,
    minimum_probability_limit: float = 0.05,
) -> CompressionResult:
    """Read a UTF-8 text file and prepare its compressed bitstream."""

    path = Path(input_path)
    text = path.read_text(encoding="utf-8")

    result = compress_text(text, minimum_probability_limit)

    # Preserve the actual input file size, including UTF-8 byte length.
    result.original_size_bytes = path.stat().st_size

    return result
