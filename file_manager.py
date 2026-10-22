
import tkinter as tk
from tkinter import filedialog


def select_input_file():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[("All files", "*.*")]
    )

    root.destroy()
    return file_path


def select_compressed_output():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.asksaveasfilename(
        title="Save compressed file",
        defaultextension=".mhuff",
        filetypes=[("Modified Huffman files", "*.mhuff"),
                   ("All files", "*.*")]
    )

    root.destroy()
    return file_path


def select_decompressed_output():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.asksaveasfilename(
        title="Save decompressed file",
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"),
                   ("All files", "*.*")]
    )

    root.destroy()
    return file_path