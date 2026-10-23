"""Pack a logical bitstream of '0'/'1' characters into real bytes.

The encoder produces a string such as "1011001". This module writes
those bits into bytes (most-significant bit first) and records how
many padding bits were added so the decoder can ignore them.
"""

from __future__ import annotations


def packed_byte_count(bit_length: int) -> int:
    """Return how many bytes are needed to store bit_length bits."""

    if bit_length < 0:
        raise ValueError("bit_length cannot be negative.")
    return (bit_length + 7) // 8


def padding_bit_count(bit_length: int) -> int:
    """Return how many 0-bits are appended so the length is a multiple of 8."""

    if bit_length < 0:
        raise ValueError("bit_length cannot be negative.")
    remainder = bit_length % 8
    if remainder == 0:
        return 0
    return 8 - remainder


def validate_bitstream(bitstream: str) -> None:
    """Reject anything that is not a string of 0 and 1 characters."""

    if not isinstance(bitstream, str):
        raise TypeError("bitstream must be a string of '0' and '1'.")

    if any(character not in "01" for character in bitstream):
        raise ValueError("bitstream may contain only the characters '0' and '1'.")


def pack_bits(bitstream: str) -> tuple[bytes, int]:
    """Convert a '0'/'1' string into packed bytes.

    Returns:
        (packed_bytes, bit_length)

    bit_length is the number of real encoded bits, not including padding.
    Padding bits are always 0 and occupy the least-significant bits of
    the last byte.
    """

    validate_bitstream(bitstream)
    bit_length = len(bitstream)

    if bit_length == 0:
        return b"", 0

    padding = padding_bit_count(bit_length)
    padded = bitstream + ("0" * padding)
    packed = bytes(
        int(padded[index : index + 8], 2)
        for index in range(0, len(padded), 8)
    )
    return packed, bit_length


def unpack_bits(packed: bytes, bit_length: int) -> str:
    """Restore a '0'/'1' string from packed bytes using bit_length.

    Extra bits stored as padding in the last byte are discarded.
    """

    if not isinstance(packed, (bytes, bytearray)):
        raise TypeError("packed data must be bytes.")

    if not isinstance(bit_length, int) or isinstance(bit_length, bool):
        raise TypeError("bit_length must be an integer.")

    if bit_length < 0:
        raise ValueError("bit_length cannot be negative.")

    expected_bytes = packed_byte_count(bit_length)
    if len(packed) != expected_bytes:
        raise ValueError(
            "Packed data size does not match bit_length. "
            f"Expected {expected_bytes} byte(s), got {len(packed)}."
        )

    if bit_length == 0:
        return ""

    bits = "".join(f"{byte:08b}" for byte in packed)
    return bits[:bit_length]
