"""Compact binary storage for Modified Huffman compression.

Version 3 compares Modified Huffman, raw-DEFLATE, and byte-level RLE.
Version 1 and 2 files remain readable.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from src.bit_utils import pack_bits, padding_bit_count, unpack_bits
from src.compression import CompressionResult, encode_file

MAGIC = b"MHUF"
VERSION = 3
PREVIOUS_VERSION = 2
LEGACY_VERSION = 1
COMPRESSED_EXTENSION = ".mhuf"

# magic(4), version(1), mode(1), probability units(2), symbol count(2),
# padding bits(1) = 11 bytes.
HEADER_FORMAT = "<4sBBHHB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
LEGACY_HEADER_FORMAT = "<4sBHHB"
LEGACY_HEADER_SIZE = struct.calcsize(LEGACY_HEADER_FORMAT)
MAX_UINT16 = 2**16 - 1
MAX_FREQUENCY = 2**32 - 1
HUFFMAN_MODE = 0
DEFLATE_MODE = 1
RLE_MODE = 2
RAW_MODE = 3  # Internal mode for a tiny file stored without a header.


@dataclass
class CompressedFile:
    """Everything needed to decode a .mhuf file."""

    bitstream: str
    frequencies: dict[str, int]
    minimum_probability_limit: float
    original_size_bytes: int
    storage_mode: int = HUFFMAN_MODE
    original_text: str | None = None


def _validate_symbol(symbol: str) -> bytes:
    if not isinstance(symbol, str):
        raise TypeError("Each symbol must be a string.")
    if len(symbol) != 1:
        raise ValueError("Each stored symbol must be exactly one character.")
    encoded = symbol.encode("utf-8")
    if not 1 <= len(encoded) <= 4:
        raise ValueError("Symbol UTF-8 encoding must be 1 to 4 bytes.")
    return encoded


def _pack_uleb128(value: int) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("frequency must be a non-negative integer.")
    if value > MAX_FREQUENCY:
        raise ValueError("frequency is too large for the binary format.")
    parts: list[int] = []
    remaining = value
    while True:
        byte = remaining & 0x7F
        remaining >>= 7
        if remaining:
            parts.append(byte | 0x80)
        else:
            parts.append(byte)
            break
    return bytes(parts)


def _read_uleb128_bytes(data: bytes, index: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while index < len(data):
        byte = data[index]
        index += 1
        result |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            if result > MAX_FREQUENCY:
                raise ValueError("Corrupted file: frequency is too large.")
            return result, index
        shift += 7
        if shift > 28:
            raise ValueError("Corrupted file: frequency varint is too long.")
    raise ValueError("Corrupted file: incomplete frequency.")


def _raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _raw_inflate(data: bytes) -> bytes:
    try:
        return zlib.decompress(data, wbits=-15)
    except zlib.error as error:
        raise ValueError("Corrupted file: invalid compressed payload.") from error


def _rle_encode(data: bytes) -> bytes:
    """Encode repeated byte runs; 0xFF introduces an RLE control record.

    FF 00 means a literal FF byte. FF count value means repeat value
    `count` times (count is 1..255). Runs shorter than four bytes are kept
    literal unless they contain the marker byte.
    """
    out = bytearray()
    i = 0
    while i < len(data):
        value = data[i]
        j = i + 1
        while j < len(data) and data[j] == value and j - i < 255:
            j += 1
        run_length = j - i
        if run_length >= 4:
            out.extend((0xFF, run_length, value))
        elif value == 0xFF:
            for _ in range(run_length):
                out.extend((0xFF, 0))
        else:
            out.extend(data[i:j])
        i = j
    return bytes(out)


def _rle_decode(data: bytes) -> bytes:
    """Decode the byte-level RLE stream, rejecting truncated records."""
    out = bytearray()
    i = 0
    while i < len(data):
        value = data[i]
        i += 1
        if value != 0xFF:
            out.append(value)
            continue
        if i >= len(data):
            raise ValueError("Corrupted file: incomplete RLE marker.")
        count = data[i]
        i += 1
        if count == 0:
            out.append(0xFF)
            continue
        if i >= len(data):
            raise ValueError("Corrupted file: incomplete RLE run.")
        repeated = data[i]
        i += 1
        out.extend(bytes((repeated,)) * count)
    return bytes(out)


def _encode_symbol_entry(symbol: str, frequency: int) -> bytes:
    encoded = _validate_symbol(symbol)
    # ASCII symbols use one byte. 0xFF is not valid in UTF-8, so it can mark
    # a multibyte symbol unambiguously.
    if len(encoded) == 1 and encoded[0] < 0x80:
        symbol_data = encoded
    else:
        symbol_data = b"\xff" + bytes((len(encoded),)) + encoded
    return symbol_data + _pack_uleb128(frequency)


def _decode_symbol_entry(data: bytes, index: int) -> tuple[str, int, int]:
    if index >= len(data):
        raise ValueError("Corrupted file: incomplete symbol table.")
    first = data[index]
    index += 1
    if first == 0xFF:
        if index >= len(data):
            raise ValueError("Corrupted file: missing UTF-8 symbol length.")
        size = data[index]
        index += 1
        if not 1 <= size <= 4 or index + size > len(data):
            raise ValueError("Corrupted file: invalid UTF-8 symbol entry.")
        encoded = data[index:index + size]
        index += size
    else:
        if first >= 0x80:
            raise ValueError("Corrupted file: invalid ASCII symbol marker.")
        encoded = bytes((first,))
    try:
        symbol = encoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Corrupted file: symbol is not valid UTF-8.") from error
    if len(symbol) != 1:
        raise ValueError("Corrupted file: stored symbol must be one character.")
    frequency, index = _read_uleb128_bytes(data, index)
    return symbol, frequency, index


def _legacy_read(file_object) -> CompressedFile:
    header = file_object.read(LEGACY_HEADER_SIZE)
    if len(header) != LEGACY_HEADER_SIZE:
        raise ValueError("Invalid compressed file: incomplete legacy header.")
    magic, version, probability_units, symbol_count, padding_bits = struct.unpack(
        LEGACY_HEADER_FORMAT, header
    )
    if magic != MAGIC or version != LEGACY_VERSION:
        raise ValueError("Invalid legacy compressed file header.")
    if probability_units > 10000 or padding_bits > 7:
        raise ValueError("Invalid legacy compressed file header values.")

    frequencies: dict[str, int] = {}
    for _ in range(symbol_count):
        length_bytes = file_object.read(1)
        if len(length_bytes) != 1:
            raise ValueError("Corrupted file: incomplete symbol length.")
        size = length_bytes[0]
        if not 1 <= size <= 4:
            raise ValueError("Corrupted file: invalid symbol length.")
        encoded = file_object.read(size)
        if len(encoded) != size:
            raise ValueError("Corrupted file: incomplete symbol bytes.")
        try:
            symbol = encoded.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Corrupted file: invalid UTF-8 symbol.") from error
        if len(symbol) != 1 or symbol in frequencies:
            raise ValueError("Corrupted file: invalid or duplicate symbol.")
        # Legacy ULEB128 reader.
        frequency = 0
        shift = 0
        while True:
            byte_data = file_object.read(1)
            if not byte_data:
                raise ValueError("Corrupted file: incomplete frequency.")
            byte = byte_data[0]
            frequency |= (byte & 0x7F) << shift
            if not byte & 0x80:
                break
            shift += 7
            if shift > 28:
                raise ValueError("Corrupted file: frequency varint is too long.")
        frequencies[symbol] = frequency

    packed = file_object.read()
    if len(packed) * 8 < padding_bits:
        raise ValueError("Corrupted file: invalid padding.")
    bit_length = len(packed) * 8 - padding_bits
    bitstream = unpack_bits(packed, bit_length)
    original_size = sum(freq * len(sym.encode("utf-8")) for sym, freq in frequencies.items())
    return CompressedFile(bitstream, frequencies, probability_units / 10000,
                          original_size, HUFFMAN_MODE)


def write_compressed_file(file_path: str | Path, result: CompressionResult) -> Path:
    """Write the smallest lossless representation among supported modes."""
    path = Path(file_path)
    if path.suffix.lower() != COMPRESSED_EXTENSION:
        raise ValueError(f"Compressed files must use the {COMPRESSED_EXTENSION} extension.")

    packed, bit_length = pack_bits(result.bitstream)
    padding_bits = padding_bit_count(bit_length)
    frequencies = result.frequencies
    if len(frequencies) > MAX_UINT16:
        raise ValueError("Too many symbols for the binary format.")
    probability_units = int(round(result.minimum_probability_limit * 10000))
    if not 0 <= probability_units <= 10000:
        raise ValueError("minimum_probability_limit is out of range.")

    original_bytes = result.original_text.encode("utf-8")

    # Candidate 0: Modified Huffman metadata + packed bitstream.
    huffman_raw = bytearray()
    for symbol, frequency in frequencies.items():
        huffman_raw.extend(_encode_symbol_entry(symbol, frequency))
    huffman_raw.extend(packed)
    huffman_payload = _raw_deflate(bytes(huffman_raw))

    # Candidate 1: direct raw-DEFLATE of the original text.
    deflate_payload = _raw_deflate(original_bytes)

    # Candidate 2: byte-level RLE. This is useful for long runs such as AAAAAA.
    rle_payload = _rle_encode(original_bytes)

    candidates = [
        (HEADER_SIZE + len(huffman_payload), HUFFMAN_MODE, huffman_payload,
         len(frequencies), padding_bits),
        (HEADER_SIZE + len(deflate_payload), DEFLATE_MODE, deflate_payload, 0, 0),
        (HEADER_SIZE + len(rle_payload), RLE_MODE, rle_payload, 0, 0),
    ]
    best_size, storage_mode, payload, symbol_count, output_padding = min(
        candidates, key=lambda candidate: candidate[0]
    )

    # For tiny files, all lossless compressed representations can be larger
    # than the source because even the header costs 11 bytes. Store raw UTF-8
    # bytes in that case, avoiding expansion. This fallback is lossless but
    # cannot make a tiny file smaller than its original size.
    looks_like_header = (
        len(original_bytes) >= 5
        and original_bytes[:4] == MAGIC
        and original_bytes[4] in (LEGACY_VERSION, PREVIOUS_VERSION, VERSION)
    )
    if len(original_bytes) <= best_size and not looks_like_header:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(original_bytes)
        except OSError as error:
            raise RuntimeError(f"Could not write compressed file:\n{error}") from error
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("wb") as file_object:
            file_object.write(struct.pack(
                HEADER_FORMAT, MAGIC, VERSION, storage_mode,
                probability_units, symbol_count, output_padding
            ))
            file_object.write(payload)
    except OSError as error:
        raise RuntimeError(f"Could not write compressed file:\n{error}") from error
    return path


def read_compressed_file(file_path: str | Path) -> CompressedFile:
    """Read legacy v1 or compact v2/v3 files and return a decoded payload."""
    path = Path(file_path)
    if path.suffix.lower() != COMPRESSED_EXTENSION:
        raise ValueError(f"Expected a {COMPRESSED_EXTENSION} compressed file.")
    if not path.exists():
        raise FileNotFoundError(f"Compressed file does not exist:\n{path}")

    try:
        with path.open("rb") as file_object:
            file_bytes = file_object.read()
            # Tiny/raw fallback files contain the original UTF-8 bytes with no
            # MHUF header. Detect them before attempting binary-header parsing.
            if len(file_bytes) < 5 or file_bytes[:4] != MAGIC:
                try:
                    raw_text = file_bytes.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ValueError("Invalid compressed file: no MHUF header and not valid UTF-8 text.") from error
                return CompressedFile("", {}, 0.0, len(file_bytes), RAW_MODE, raw_text)

            magic, version = struct.unpack("<4sB", file_bytes[:5])
            if version not in (LEGACY_VERSION, PREVIOUS_VERSION, VERSION):
                # A raw UTF-8 file can coincidentally start with the letters MHUF.
                try:
                    raw_text = file_bytes.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ValueError(f"Unsupported compressed file version: {version}") from error
                return CompressedFile("", {}, 0.0, len(file_bytes), RAW_MODE, raw_text)
            file_object.seek(0)
            if version == LEGACY_VERSION:
                return _legacy_read(file_object)

            file_object.seek(5)
            rest = file_object.read(HEADER_SIZE - 5)
            if len(rest) != HEADER_SIZE - 5:
                raise ValueError("Invalid compressed file: incomplete header.")
            mode, probability_units, symbol_count, padding_bits = struct.unpack("<BHHB", rest)
            if mode not in (HUFFMAN_MODE, DEFLATE_MODE, RLE_MODE):
                raise ValueError(f"Unsupported storage mode: {mode}")
            if probability_units > 10000 or padding_bits > 7:
                raise ValueError("Invalid compressed file header values.")
            stored_payload = file_object.read()
            if mode == RLE_MODE:
                raw = _rle_decode(stored_payload)
            else:
                raw = _raw_inflate(stored_payload)
    except OSError as error:
        raise RuntimeError(f"Could not read compressed file:\n{error}") from error

    if mode in (DEFLATE_MODE, RLE_MODE):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            label = "RLE" if mode == RLE_MODE else "DEFLATE"
            raise ValueError(f"Corrupted file: {label} payload is not valid UTF-8.") from error
        return CompressedFile("", {}, probability_units / 10000, len(raw),
                              mode, text)

    frequencies: dict[str, int] = {}
    index = 0
    for _ in range(symbol_count):
        symbol, frequency, index = _decode_symbol_entry(raw, index)
        if symbol in frequencies:
            raise ValueError("Corrupted file: duplicate symbol in table.")
        frequencies[symbol] = frequency
    packed = raw[index:]
    if len(packed) * 8 < padding_bits:
        raise ValueError("Corrupted file: padding is larger than packed data.")
    bit_length = len(packed) * 8 - padding_bits
    bitstream = unpack_bits(packed, bit_length)
    original_size = sum(freq * len(sym.encode("utf-8")) for sym, freq in frequencies.items())
    return CompressedFile(bitstream, frequencies, probability_units / 10000,
                          original_size, HUFFMAN_MODE)


def compress_path_to_binary(
    input_path: str | Path,
    output_path: str | Path,
    minimum_probability_limit: float = 0.05,
) -> CompressionResult:
    """Encode a UTF-8 text file and write a .mhuf binary file."""
    result = encode_file(input_path, minimum_probability_limit)
    write_compressed_file(output_path, result)
    return result
