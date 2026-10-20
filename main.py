"""Main program for Modified Huffman Compression."""

from pathlib import Path

from src.compression import encode_file


SEPARATOR = "=" * 64
SUB_SEPARATOR = "-" * 64


def print_header(title: str) -> None:
    """Display a formatted section header."""
    print(f"\n{SEPARATOR}")
    print(f"{title:^{len(SEPARATOR)}}")
    print(SEPARATOR)


def compress_file() -> None:
    """Ask for a text file, compress it, and display the results."""

    input_path = input(
        "\nEnter the path of the text file to compress: "
    ).strip().strip('"')

    if not input_path:
        print("\nError: No input file path provided.")
        return

    input_file = Path(input_path)

    if not input_file.is_file():
        print("\nError: The input file does not exist.")
        return

    output_path = input(
        "Enter the output path for the compressed result "
        "(e.g. examples/compressed_sample.txt): "
    ).strip().strip('"')

    if not output_path:
        print("\nError: No output path provided.")
        return

    output_file = Path(output_path)

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

        # Save the logical bitstream as text.
        # Binary packing and metadata are handled separately.
        output_file.write_text(
            result.bitstream,
            encoding="ascii",
        )

        # Calculate file sizes.
        original_size = input_file.stat().st_size
        bitstream_bits = len(result.bitstream)
        actual_output_size = output_file.stat().st_size

        # Estimate the size after packing bits into bytes.
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
            f"{'Estimated packed size:':<28} "
            f"{theoretical_packed_size:,} bytes"
        )
        print(
            f"{'Actual output file size:':<28} "
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

            print(f"{'Estimated packed ratio:':<28} {packed_ratio:>8.2f}%")
            print(f"{'Estimated space saved:':<28} {packed_saving:>8.2f}%")
            print()
            print(f"{'Actual text-file ratio:':<28} {actual_ratio:>8.2f}%")
            print(f"{'Actual text-file saving:':<28} {actual_saving:>8.2f}%")
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

        print(f"{'Probability threshold:':<28} "
              f"{result.minimum_probability_limit:.2%}")

        print(SEPARATOR)
        print("Compression completed successfully.")

        print(
            "\nNote: The output currently stores the bitstream as text. "
            "The estimated packed size does not include file metadata "
            "or padding."
        )

    except (OSError, UnicodeError, ValueError) as error:
        print(f"\nCompression error: {error}")


def main() -> None:
    """Display the main menu."""

    while True:
        print_header("MODIFIED HUFFMAN COMPRESSION")
        print("  1. Compress a file")
        print("  2. Decompress a file (not available yet)")
        print("  0. Exit")
        print(SUB_SEPARATOR)

        choice = input("Choose an option: ").strip()

        if choice == "1":
            compress_file()

        elif choice == "2":
            print(
                "\nDecompression is not available yet. "
                "It will be connected when its implementation is ready."
            )

        elif choice == "0":
            print("\nExiting the program. Goodbye!")
            break

        else:
            print("\nInvalid choice. Please select 1, 2, or 0.")


if __name__ == "__main__":
    main()