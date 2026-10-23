
"""File selection and save dialogs."""

import tkinter as tk
from tkinter import filedialog


def select_input_file():
    """Select a file to compress."""

    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select a file to compress",
        filetypes=[("All files", "*.*")]
    )

    root.destroy()
    return file_path


def select_compressed_input():
    """Select a compressed Modified Huffman file."""

    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select a compressed file",
        filetypes=[
            ("Modified Huffman files", "*.mhuf"),
            ("All files", "*.*")
        ]
    )

    root.destroy()
    return file_path


def select_compressed_output():
    """Choose where to save the compressed binary file."""

    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.asksaveasfilename(
        title="Save compressed file",
        defaultextension=".mhuf",
        filetypes=[
            ("Modified Huffman files", "*.mhuf"),
            ("All files", "*.*")
        ]
    )

    root.destroy()
    return file_path


def select_decompressed_output():
    """Choose where to save the recovered file."""

    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.asksaveasfilename(
        title="Save decompressed file",
        defaultextension=".txt",
        filetypes=[
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )

    root.destroy()
    return file_path