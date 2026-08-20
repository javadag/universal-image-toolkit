"""
Batch processing dialog for converting, resizing, and optimizing queues of images.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from tkinter import filedialog, messagebox
from typing import List, Optional
import customtkinter as ctk
from PIL import Image

from engine.processor import ImageProcessor, ResampleFilter
from engine.format_handler import ExportFormat, ExportOptions, FormatHandler, FORMAT_EXTENSION_MAP
from engine.optimizer import SizeEstimate
from ui.theme import COLORS, FONTS


class BatchProcessorDialog(ctk.CTkToplevel):
    """
    Modal window for multi-image and folder batch optimization.
    """

    def __init__(self, master, current_options: Optional[ExportOptions] = None, **kwargs):
        super().__init__(master, **kwargs)

        self.title("⚡ Universal Batch Image Processor")
        self.geometry("860x620")
        self.minsize(700, 500)
        self.configure(fg_color=COLORS["bg_dark"])

        self.queue_files: List[Path] = []
        self.output_dir: Optional[Path] = None
        self.is_processing = False
        self.stop_requested = False

        self.export_options = current_options or ExportOptions()

        self._build_ui()
        self.grab_set()  # Make modal

    def _build_ui(self):
        # 1. Top Header & Add Files Bar
        top_bar = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        top_bar.pack(fill="x", padx=14, pady=12)

        lbl_header = ctk.CTkLabel(
            top_bar, text="Batch Optimization Queue", font=FONTS["title"], text_color=COLORS["text_primary"]
        )
        lbl_header.pack(side="left", padx=14, pady=12)

        btn_add_files = ctk.CTkButton(
            top_bar,
            text="+ Add Files",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            command=self._add_files,
            height=32,
        )
        btn_add_files.pack(side="right", padx=10, pady=12)

        btn_add_folder = ctk.CTkButton(
            top_bar,
            text="📁 Add Folder",
            font=FONTS["body_bold"],
            fg_color=COLORS["card_border"],
            hover_color=COLORS["accent_purple"],
            text_color=COLORS["text_primary"],
            command=self._add_folder,
            height=32,
        )
        btn_add_folder.pack(side="right", padx=6, pady=12)

        # 2. Main Content Split (Left Queue Table, Right Settings Panel)
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # Left Queue Listbox / ScrollFrame
        queue_container = ctk.CTkFrame(content_frame, fg_color=COLORS["sidebar_bg"], corner_radius=10)
        queue_container.pack(side="left", fill="both", expand=True, padx=(0, 8))

        q_header = ctk.CTkFrame(queue_container, fg_color="transparent")
        q_header.pack(fill="x", padx=10, pady=8)
        self.lbl_queue_count = ctk.CTkLabel(
            q_header, text="Queue (0 files)", font=FONTS["body_bold"], text_color=COLORS["text_secondary"]
        )
        self.lbl_queue_count.pack(side="left")

        btn_clear = ctk.CTkButton(
            q_header,
            text="Clear",
            font=FONTS["small"],
            width=50,
            height=24,
            fg_color="transparent",
            hover_color=COLORS["accent_danger"],
            text_color=COLORS["text_secondary"],
            command=self._clear_queue,
        )
        btn_clear.pack(side="right")

        self.queue_scroll = ctk.CTkScrollableFrame(queue_container, fg_color="transparent")
        self.queue_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Right Batch Settings Panel
        settings_panel = ctk.CTkScrollableFrame(content_frame, fg_color=COLORS["card_bg"], corner_radius=10, width=280)
        settings_panel.pack(side="right", fill="both", padx=(8, 0))

        ctk.CTkLabel(settings_panel, text="BATCH SETTINGS", font=FONTS["badge"], text_color=COLORS["text_muted"]).pack(
            anchor="w", pady=(4, 6)
        )

        # Target Format
        ctk.CTkLabel(settings_panel, text="Output Format", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.combo_format = ctk.CTkComboBox(
            settings_panel,
            values=[f.value for f in ExportFormat],
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            height=30,
        )
        self.combo_format.set(self.export_options.format.value)
        self.combo_format.pack(fill="x", pady=(2, 6))

        # Quality Slider
        ctk.CTkLabel(settings_panel, text="Quality (1-100)", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.slider_quality = ctk.CTkSlider(settings_panel, from_=1, to=100, number_of_steps=99)
        self.slider_quality.set(self.export_options.quality)
        self.slider_quality.pack(fill="x", pady=(2, 6))

        # Resize option
        ctk.CTkLabel(settings_panel, text="Max Dimension (Resize)", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.combo_max_dim = ctk.CTkComboBox(
            settings_panel,
            values=["Original (No Resize)", "4K (3840 px)", "1080p (1920 px)", "720p (1280 px)", "800 px", "50% Scale", "25% Scale"],
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            height=30,
        )
        self.combo_max_dim.set("Original (No Resize)")
        self.combo_max_dim.pack(fill="x", pady=(2, 6))

        # EXIF Stripping
        self.chk_strip = ctk.CTkCheckBox(
            settings_panel, text="Strip EXIF / Metadata", font=FONTS["small"], checkbox_height=18, checkbox_width=18
        )
        self.chk_strip.select()
        self.chk_strip.pack(anchor="w", pady=6)

        # Output Folder Selection
        ctk.CTkLabel(settings_panel, text="Destination Folder", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(8, 2))
        self.btn_dest_folder = ctk.CTkButton(
            settings_panel,
            text="Same folder (/optimized)",
            font=FONTS["small"],
            fg_color=COLORS["card_border"],
            hover_color=COLORS["accent_primary"],
            text_color=COLORS["text_primary"],
            command=self._select_output_folder,
            height=30,
        )
        self.btn_dest_folder.pack(fill="x", pady=(0, 6))

        # 3. Bottom Progress Bar & Run Button
        bottom_bar = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        bottom_bar.pack(fill="x", padx=14, pady=(0, 14))

        self.progress_bar = ctk.CTkProgressBar(bottom_bar, height=12, progress_color=COLORS["accent_success"])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=14, pady=(12, 6))

        status_row = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        status_row.pack(fill="x", padx=14, pady=(0, 10))

        self.lbl_status = ctk.CTkLabel(
            status_row, text="Ready. Add files to begin.", font=FONTS["small"], text_color=COLORS["text_secondary"]
        )
        self.lbl_status.pack(side="left")

        self.btn_start = ctk.CTkButton(
            status_row,
            text="🚀 Start Batch Processing",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_success"],
            hover_color="#059669",
            text_color="#ffffff",
            command=self._start_batch,
            height=34,
        )
        self.btn_start.pack(side="right")

    def _add_files(self):
        filetypes = [("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif *.avif *.gif"), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="Select Images for Batch", filetypes=filetypes)
        for p in paths:
            path = Path(p)
            if path not in self.queue_files:
                self.queue_files.append(path)
        self._refresh_queue_view()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder of Images")
        if not folder:
            return
        folder_path = Path(folder)
        supported_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".avif", ".gif"}
        for f in folder_path.rglob("*"):
            if f.is_file() and f.suffix.lower() in supported_exts:
                if f not in self.queue_files:
                    self.queue_files.append(f)
        self._refresh_queue_view()

    def _clear_queue(self):
        if self.is_processing:
            return
        self.queue_files.clear()
        self._refresh_queue_view()

    def _select_output_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_dir = Path(folder)
            self.btn_dest_folder.configure(text=self.output_dir.name)

    def _refresh_queue_view(self):
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()

        self.lbl_queue_count.configure(text=f"Queue ({len(self.queue_files)} files)")

        for i, file_path in enumerate(self.queue_files):
            row = ctk.CTkFrame(self.queue_scroll, fg_color=COLORS["card_bg"], height=32, corner_radius=6)
            row.pack(fill="x", pady=2)

            lbl_name = ctk.CTkLabel(row, text=file_path.name, font=FONTS["small"], anchor="w")
            lbl_name.pack(side="left", padx=8, expand=True, fill="x")

            size_kb = file_path.stat().st_size / 1024.0
            lbl_size = ctk.CTkLabel(
                row,
                text=f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB",
                font=FONTS["small"],
                text_color=COLORS["text_secondary"],
            )
            lbl_size.pack(side="right", padx=8)

    def _start_batch(self):
        if not self.queue_files:
            messagebox.showwarning("Empty Queue", "Please add images to the batch queue first.")
            return

        if self.is_processing:
            self.stop_requested = True
            return

        self.is_processing = True
        self.stop_requested = False
        self.btn_start.configure(text="⏹ Stop Processing", fg_color=COLORS["accent_danger"])

        # Run processing in worker thread
        threading.Thread(target=self._process_worker, daemon=True).start()

    def _process_worker(self):
        total = len(self.queue_files)
        success_count = 0
        total_orig_bytes = 0
        total_out_bytes = 0

        # Read settings
        fmt_str = self.combo_format.get()
        chosen_fmt = ExportFormat.WEBP
        for f in ExportFormat:
            if f.value == fmt_str:
                chosen_fmt = f
                break

        quality = int(self.slider_quality.get())
        strip_meta = bool(self.chk_strip.get())
        max_dim_choice = self.combo_max_dim.get()

        ext = FORMAT_EXTENSION_MAP.get(chosen_fmt, ".webp")

        for idx, file_path in enumerate(self.queue_files):
            if self.stop_requested:
                break

            try:
                img, info = ImageProcessor.load_image(file_path)
                total_orig_bytes += info.file_size_bytes

                # Apply max dimension if selected
                if "3840" in max_dim_choice:
                    img = ImageProcessor.resize(img, target_width=3840, target_height=3840, keep_aspect_ratio=True)
                elif "1920" in max_dim_choice:
                    img = ImageProcessor.resize(img, target_width=1920, target_height=1920, keep_aspect_ratio=True)
                elif "1280" in max_dim_choice:
                    img = ImageProcessor.resize(img, target_width=1280, target_height=1280, keep_aspect_ratio=True)
                elif "800" in max_dim_choice:
                    img = ImageProcessor.resize(img, target_width=800, target_height=800, keep_aspect_ratio=True)
                elif "50%" in max_dim_choice:
                    img = ImageProcessor.resize(img, scale_percent=50)
                elif "25%" in max_dim_choice:
                    img = ImageProcessor.resize(img, scale_percent=25)

                options = ExportOptions(
                    format=chosen_fmt,
                    quality=quality,
                    strip_metadata=strip_meta,
                )

                # Output path
                if self.output_dir:
                    out_path = self.output_dir / f"{file_path.stem}_opt{ext}"
                else:
                    opt_dir = file_path.parent / "optimized"
                    opt_dir.mkdir(parents=True, exist_ok=True)
                    out_path = opt_dir / f"{file_path.stem}{ext}"

                out_bytes = FormatHandler.export(img, out_path, options)
                total_out_bytes += out_bytes
                success_count += 1

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

            # Update UI Progress
            progress = (idx + 1) / total
            self.after(0, lambda p=progress, i=idx + 1: self._update_progress_ui(p, i, total))

        self.after(0, lambda: self._finish_batch(success_count, total, total_orig_bytes, total_out_bytes))

    def _update_progress_ui(self, progress: float, current: int, total: int):
        self.progress_bar.set(progress)
        self.lbl_status.configure(text=f"Processing {current} of {total} ({int(progress * 100)}%)...")

    def _finish_batch(self, count: int, total: int, orig_bytes: int, out_bytes: int):
        self.is_processing = False
        self.btn_start.configure(text="🚀 Start Batch Processing", fg_color=COLORS["accent_success"])

        diff = orig_bytes - out_bytes
        pct = (diff / orig_bytes * 100.0) if orig_bytes > 0 else 0

        orig_str = SizeEstimate.format_bytes(orig_bytes)
        out_str = SizeEstimate.format_bytes(out_bytes)

        summary = f"Processed {count}/{total} images!\nOriginal: {orig_str} ➔ Output: {out_str}\nTotal Savings: {pct:.1f}%"
        self.lbl_status.configure(text=f"Complete! Saved {pct:.1f}% disk space.")
        messagebox.showinfo("Batch Complete", summary)
