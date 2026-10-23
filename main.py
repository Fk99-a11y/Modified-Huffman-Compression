
"""Main program for Modified Huffman Compression."""

from pathlib import Path

from src.compression import encode_file
from src.decoder import decompress_file_to_path
from src.file_format import COMPRESSED_EXTENSION, write_compressed_file

from file_manager import (
    select_input_file,
    select_compressed_input,
    select_compressed_output,
    select_decompressed_output
)


SEPARATOR = "=" * 64
SUB_SEPARATOR = "-" * 64


def print_header(title: str) -> None:
    """Display a formatted section header."""

    print(f"\n{SEPARATOR}")
    print(f"{title:^{len(SEPARATOR)}}")
    print(SEPARATOR)


def compress_file() -> None:
    """Select a file, compress it, and save the binary result."""

    print("\nSelect the file you want to compress.")

    input_path = select_input_file()

    if not input_path:
        print("\nFile selection cancelled.")
        return

    input_file = Path(input_path)

    if not input_file.is_file():
        print("\nError: The input file does not exist.")
        return

    print("\nSelect where to save the compressed file.")

    output_path = select_compressed_output()

    if not output_path:
        print("\nSaving cancelled.")
        return

    output_file = Path(output_path)

    # Ensure the correct compressed file extension.
    if output_file.suffix.lower() != COMPRESSED_EXTENSION.lower():
        output_file = output_file.with_suffix(COMPRESSED_EXTENSION)

    try:
        # Prevent overwriting the original input file.
        if input_file.resolve() == output_file.resolve():
            print("\nError: Output path must differ from input path.")
            return

        # Encode the input file.
        result = encode_file(input_file)

        print("\nHuffman Codes:")

        for symbol, code in result.codes.items():
            print(f"{repr(symbol):>8} : {code}")

        print("\nOriginal Codes:")

        for symbol, code in result.original_codes.items():
            print(f"{repr(symbol):>8} : {code}")

        # Create the output directory if necessary.
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save the compressed data using the binary file format.
        write_compressed_file(output_file, result)

        # Calculate file sizes.
        original_size = input_file.stat().st_size
        bitstream_bits = len(result.bitstream)
        actual_output_size = output_file.stat().st_size
        theoretical_packed_size = (bitstream_bits + 7) // 8

        print_header("COMPRESSION RESULTS")

        print(f"{'Input file:':<28} {input_file}")
        print(f"{'Output file:':<28} {output_file}")

        print(SUB_SEPARATOR)
        print("FILE INFORMATION")
        print(SUB_SEPARATOR)

        print(f"{'Original file size:':<28} {original_size:,} bytes")
        print(
            f"{'Original text symbols:':<28} "
            f"{len(result.original_text):,}"
        )
        print(f"{'Encoded bitstream:':<28} {bitstream_bits:,} bits")
        print(
            f"{'Packed bitstream size:':<28} "
            f"{theoretical_packed_size:,} bytes"
        )
        print(
            f"{'Binary file size:':<28} "
            f"{actual_output_size:,} bytes"
        )

        print(SUB_SEPARATOR)
        print("COMPRESSION STATISTICS")
        print(SUB_SEPARATOR)

        if original_size > 0:
            packed_ratio = theoretical_packed_size / original_size * 100
            packed_saving = 100 - packed_ratio

            actual_ratio = actual_output_size / original_size * 100
            actual_saving = 100 - actual_ratio

            print(
                f"{'Packed bitstream ratio:':<28} "
                f"{packed_ratio:>8.2f}%"
            )
            print(
                f"{'Packed bitstream saved:':<28} "
                f"{packed_saving:>8.2f}%"
            )
            print()
            print(
                f"{'Binary file ratio:':<28} "
                f"{actual_ratio:>8.2f}%"
            )
            print(
                f"{'Binary space saved:':<28} "
                f"{actual_saving:>8.2f}%"
            )

            if actual_output_size < original_size:
                print("\nBinary file is smaller than the original file.")

            elif actual_output_size == original_size:
                print(
                    "\nBinary file is the same size as the original file."
                )

            else:
                print(
                    "\nBinary file is larger than the original file. "
                    "This can happen with small files because metadata "
                    "must also be stored."
                )

        else:
            print("Compression ratio: N/A (empty input file)")

        print(SUB_SEPARATOR)
        print("MODIFIED HUFFMAN INFORMATION")
        print(SUB_SEPARATOR)

        if result.others_symbols:
            print(
                f"{'Symbols grouped into Others:':<28} "
                f"{', '.join(repr(s) for s in result.others_symbols)}"
            )
        else:
            print(f"{'Symbols grouped into Others:':<28} None")

        print(
            f"{'Probability threshold:':<28} "
            f"{result.minimum_probability_limit:.2%}"
        )

        print(SEPARATOR)
        print("Compression completed successfully.")

    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"\nCompression error: {error}")


def decompress_file() -> None:
    """Select a compressed file and restore the original data."""

    print("\nSelect the compressed .mhuf file.")

    input_path = select_compressed_input()

    if not input_path:
        print("\nFile selection cancelled.")
        return

    input_file = Path(input_path)

    if not input_file.is_file():
        print("\nError: The compressed file does not exist.")
        return

    if input_file.suffix.lower() != COMPRESSED_EXTENSION.lower():
        print(
            f"\nError: Compressed files must end with "
            f"{COMPRESSED_EXTENSION}."
        )
        return

    print("\nSelect where to save the recovered file.")

    output_path = select_decompressed_output()

    if not output_path:
        print("\nSaving cancelled.")
        return

    output_file = Path(output_path)

    try:
        # Prevent overwriting the compressed input file.
        if input_file.resolve() == output_file.resolve():
            print("\nError: Output path must differ from input path.")
            return

        # Create the output directory if necessary.
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Decode the binary file and save the recovered data.
        text = decompress_file_to_path(input_file, output_file)

        compressed_size = input_file.stat().st_size
        recovered_size = output_file.stat().st_size

        print_header("DECOMPRESSION RESULTS")

        print(f"{'Input file:':<28} {input_file}")
        print(f"{'Output file:':<28} {output_file}")
        print(f"{'Compressed size:':<28} {compressed_size:,} bytes")
        print(f"{'Recovered size:':<28} {recovered_size:,} bytes")
        print(f"{'Recovered symbols:':<28} {len(text):,}")

        print(SEPARATOR)
        print("Decompression completed successfully.")
        print("The recovered file should match the original text.")

    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"\nDecompression error: {error}")


def main() -> None:
    """Display the main menu."""

    while True:
        print_header("MODIFIED HUFFMAN COMPRESSION")

        print("  1. Compress a file")
        print("  2. Decompress a file")
        print("  0. Exit")

        print(SUB_SEPARATOR)

        choice = input("Choose an option: ").strip()

        if choice == "1":
            compress_file()

        elif choice == "2":
            decompress_file()

        elif choice == "0":
            print("\nExiting the program. Goodbye!")
            break

        else:
            print("\nInvalid choice. Please select 1, 2, or 0.")


if __name__ == "__main__":
    main()