#!/usr/bin/env python3
"""
Universal Image Toolkit - Entry Point
A portable, cross-platform image resizer, cropper, compressor, and format converter.
"""
import sys
from ui.main_window import MainWindow


def main():
    initial_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = MainWindow(initial_image_path=initial_path)
    app.mainloop()


if __name__ == "__main__":
    main()
