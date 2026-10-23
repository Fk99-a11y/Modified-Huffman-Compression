"""Decode a Modified Huffman bitstream back into the original text.

Decoding steps:
    1. Read metadata + packed bits from the .mhuf file.
    2. Rebuild Huffman codes with the same rules as the encoder.
    3. Walk the bitstream:
         - match a Huffman code
         - if the code is "Others", read the fixed-length original code
    4. For DEFLATE-mode files, use the original text already recovered by
       file_format.py instead of trying to decode a Huffman bitstream.
    5. Write the recovered UTF-8 text.
"""

from __future__ import annotations

from pathlib import Path

from src.compression import build_huffman_codes, build_original_codes
from src.file_format import (
    CompressedFile,
    DEFLATE_MODE,
    RLE_MODE,
    RAW_MODE,
    read_compressed_file,
)


def rebuild_code_tables(
    frequencies: dict[str, int],
    minimum_probability_limit: float,
) -> tuple[dict[str, str], dict[str, str], set[str], int]:
    """Rebuild encoder tables from stored frequencies.

    Returns:
        huffman_codes, original_codes, others_symbols, original_code_width
    """

    if not frequencies:
        return {}, {}, set(), 0

    total_symbols = sum(frequencies.values())
    if total_symbols <= 0:
        raise ValueError("Invalid frequency table: total count must be positive.")

    probabilities = {
        symbol: count / total_symbols
        for symbol, count in frequencies.items()
    }

    others_symbols = {
        symbol
        for symbol, probability in probabilities.items()
        if probability <= minimum_probability_limit
    }

    grouped_frequencies = {
        symbol: frequencies[symbol]
        for symbol in frequencies
        if symbol not in others_symbols
    }
    if others_symbols:
        grouped_frequencies["Others"] = sum(
            frequencies[symbol] for symbol in others_symbols
        )

    huffman_codes = build_huffman_codes(grouped_frequencies)
    original_codes, original_code_width = build_original_codes(list(frequencies))
    return huffman_codes, original_codes, others_symbols, original_code_width


def decode_bitstream(
    bitstream: str,
    huffman_codes: dict[str, str],
    original_codes: dict[str, str],
    others_symbols: set[str],
    original_code_width: int,
) -> str:
    """Turn a logical bitstream back into the original text."""

    if bitstream == "":
        return ""

    if not huffman_codes:
        raise ValueError("Cannot decode: Huffman code table is empty.")

    reverse_huffman = {code: symbol for symbol, code in huffman_codes.items()}
    reverse_original = {code: symbol for symbol, code in original_codes.items()}
    max_huffman_length = max(len(code) for code in reverse_huffman)

    output: list[str] = []
    index = 0
    length = len(bitstream)

    while index < length:
        matched_symbol = None
        matched_length = 0

        for code_length in range(1, max_huffman_length + 1):
            end = index + code_length
            if end > length:
                break
            candidate = bitstream[index:end]
            if candidate in reverse_huffman:
                matched_symbol = reverse_huffman[candidate]
                matched_length = code_length
                break

        if matched_symbol is None:
            raise ValueError("Corrupted bitstream: no Huffman code matches.")

        index += matched_length

        if matched_symbol == "Others":
            extra_end = index + original_code_width
            extra = bitstream[index:extra_end]
            if len(extra) != original_code_width:
                raise ValueError(
                    "Corrupted bitstream: incomplete original code after Others."
                )
            if extra not in reverse_original:
                raise ValueError(
                    "Corrupted bitstream: unknown original code after Others."
                )
            recovered = reverse_original[extra]
            if recovered not in others_symbols:
                raise ValueError(
                    "Corrupted bitstream: original code is not in the Others group."
                )
            output.append(recovered)
            index = extra_end
        else:
            output.append(matched_symbol)

    return "".join(output)


def decompress_payload(payload: CompressedFile) -> str:
    """Decode a payload according to its storage mode."""
    # These modes are already decoded by file_format.py and do not contain
    # a Huffman bitstream. RAW_MODE is used for tiny files where a header
    # would make the file larger than the original.
    if payload.storage_mode in (DEFLATE_MODE, RLE_MODE, RAW_MODE):
        if payload.original_text is None:
            raise ValueError("Corrupted file: missing text for this storage mode.")
        return payload.original_text

    (
        huffman_codes,
        original_codes,
        others_symbols,
        original_code_width,
    ) = rebuild_code_tables(
        frequencies=payload.frequencies,
        minimum_probability_limit=payload.minimum_probability_limit,
    )
    return decode_bitstream(
        bitstream=payload.bitstream,
        huffman_codes=huffman_codes,
        original_codes=original_codes,
        others_symbols=others_symbols,
        original_code_width=original_code_width,
    )


def decompress_file(file_path: str | Path) -> str:
    """Read a .mhuf file and return the original text."""

    payload = read_compressed_file(file_path)
    return decompress_payload(payload)


def decompress_file_to_path(
    input_path: str | Path,
    output_path: str | Path,
) -> str:
    """Read a .mhuf file and write the recovered UTF-8 text."""

    text = decompress_file(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.write_text(text, encoding="utf-8")
    except OSError as error:
        raise RuntimeError(f"Could not write decompressed file:\n{error}") from error
    return text
