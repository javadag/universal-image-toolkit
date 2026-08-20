"""
Main application window coordinating canvas, controls, and file operations.
"""
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List, Optional
import customtkinter as ctk
from PIL import Image

from engine.processor import ImageProcessor, ImageInfo, ResampleFilter
from engine.format_handler import ExportFormat, ExportOptions, FormatHandler, FORMAT_EXTENSION_MAP
from engine.optimizer import ImageOptimizer, SizeEstimate
from ui.theme import COLORS, FONTS
from ui.canvas_view import InteractiveImageCanvas
from ui.sidebar_controls import SidebarControls
from ui.batch_dialog import BatchProcessorDialog


class MainWindow(ctk.CTk):
    """
    Main Application Window for Universal Image Toolkit.
    """

    def __init__(self, initial_image_path: Optional[str] = None):
        super().__init__()

        # Appearance setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Universal Image Toolkit — Resize, Crop, Compress & Convert")
        self.geometry("1280x820")
        self.minsize(980, 650)
        self.configure(fg_color=COLORS["bg_dark"])

        # Window & Dock Icon
        self._set_window_icon()

        # State
        self.current_image_path: Optional[Path] = None
        self.original_image: Optional[Image.Image] = None
        self.working_image: Optional[Image.Image] = None
        self.current_info: Optional[ImageInfo] = None
        self.history_stack: List[Image.Image] = []

        self._build_ui()
        self._bind_shortcuts()

        if initial_image_path:
            self.load_image_from_path(initial_image_path)

    def _set_window_icon(self):
        """Sets application window and dock icon."""
        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                from PIL import ImageTk
                self._app_icon = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, self._app_icon)
            except Exception:
                pass

    def _build_ui(self):
        # 1. Top Navigation & App Bar
        top_bar = ctk.CTkFrame(self, fg_color=COLORS["sidebar_bg"], height=52, corner_radius=0)
        top_bar.pack(fill="x", side="top")

        # App Brand
        lbl_brand = ctk.CTkLabel(
            top_bar,
            text="✨ Universal Image Toolkit",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        )
        lbl_brand.pack(side="left", padx=16, pady=10)

        # Action Buttons
        btn_open = ctk.CTkButton(
            top_bar,
            text="📂 Open Image",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            height=32,
            command=self.open_image_dialog,
        )
        btn_open.pack(side="left", padx=8, pady=10)

        btn_batch = ctk.CTkButton(
            top_bar,
            text="⚡ Batch Queue",
            font=FONTS["body_bold"],
            fg_color=COLORS["card_border"],
            hover_color=COLORS["accent_purple"],
            text_color=COLORS["text_primary"],
            height=32,
            command=self.open_batch_dialog,
        )
        btn_batch.pack(side="left", padx=4, pady=10)

        btn_undo = ctk.CTkButton(
            top_bar,
            text="↶ Undo",
            font=FONTS["body"],
            width=64,
            height=32,
            fg_color="transparent",
            hover_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            command=self.undo,
        )
        btn_undo.pack(side="left", padx=4, pady=10)

        btn_reset = ctk.CTkButton(
            top_bar,
            text="Revert to Original",
            font=FONTS["body"],
            height=32,
            fg_color="transparent",
            hover_color=COLORS["accent_danger"],
            text_color=COLORS["text_primary"],
            command=self.revert_to_original,
        )
        btn_reset.pack(side="left", padx=4, pady=10)

        # Right-aligned Theme Switcher
        self.theme_switch = ctk.CTkSegmentedButton(
            top_bar,
            values=["Dark", "Light"],
            command=self._toggle_theme,
            font=FONTS["small"],
            selected_color=COLORS["accent_primary"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["card_border"],
            unselected_hover_color=COLORS["sidebar_bg"],
            text_color=COLORS["text_primary"],
            height=28,
        )
        self.theme_switch.set("Dark")
        self.theme_switch.pack(side="right", padx=16, pady=10)

        # 2. Main Workspace Split: Canvas (Left) + Sidebar (Right)
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.pack(fill="both", expand=True)

        # Left Canvas View
        self.canvas_view = InteractiveImageCanvas(
            workspace,
            on_crop_changed=self._on_crop_coords_from_canvas,
            on_image_drop=self.load_image_from_path,
        )
        self.canvas_view.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

        # Right Sidebar Controls
        self.sidebar = SidebarControls(
            workspace,
            width=390,
            on_resize_requested=self.apply_resize,
            on_crop_preset_selected=self.set_crop_preset,
            on_crop_coords_changed=self.set_crop_coords_manual,
            on_apply_crop=self.apply_crop,
            on_reset_crop=self.reset_crop,
            on_rotate=self.apply_rotation,
            on_flip=self.apply_flip,
            on_export=self.export_image,
            on_open_batch_dialog=self.open_batch_dialog,
            on_options_changed=self.update_live_size_estimate,
            get_working_image=lambda: self.working_image,
        )
        self.sidebar.pack(side="right", fill="both", padx=(4, 8), pady=8)

    def _bind_shortcuts(self):
        """Binds standard desktop keyboard shortcuts."""
        self.bind("<Command-o>", lambda e: self.open_image_dialog())
        self.bind("<Control-o>", lambda e: self.open_image_dialog())
        self.bind("<Command-s>", lambda e: self.export_image(self.sidebar.get_export_options()))
        self.bind("<Control-s>", lambda e: self.export_image(self.sidebar.get_export_options()))
        self.bind("<Command-z>", lambda e: self.undo())
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Command-0>", lambda e: self.canvas_view.fit_to_view())
        self.bind("<Control-0>", lambda e: self.canvas_view.fit_to_view())
        self.bind("<Command-1>", lambda e: self.canvas_view.reset_to_100_percent())
        self.bind("<Control-1>", lambda e: self.canvas_view.reset_to_100_percent())

    def _toggle_theme(self, mode: str):
        ctk.set_appearance_mode(mode.lower())
        self.canvas_view.update_theme(mode.lower())

    def _push_history(self):
        if self.working_image:
            self.history_stack.append(self.working_image.copy())
            if len(self.history_stack) > 15:
                self.history_stack.pop(0)

    def undo(self):
        if not self.history_stack:
            return
        self.working_image = self.history_stack.pop()
        self.canvas_view.set_image(self.working_image, reset_crop=False)
        self.sidebar.set_dimensions(self.working_image.width, self.working_image.height)
        self.update_live_size_estimate()

    def revert_to_original(self):
        if not self.original_image:
            return
        self._push_history()
        self.working_image = self.original_image.copy()
        self.canvas_view.set_image(self.working_image, reset_crop=True)
        self.sidebar.set_dimensions(self.working_image.width, self.working_image.height)
        self.update_live_size_estimate()

    # --- File Operations ---
    def open_image_dialog(self):
        filetypes = [
            ("Supported Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif *.avif *.gif *.ico"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Select an Image", filetypes=filetypes)
        if path:
            self.load_image_from_path(path)

    def load_image_from_path(self, filepath: str):
        try:
            img, info = ImageProcessor.load_image(filepath)
            self.current_image_path = Path(filepath)
            self.original_image = img.copy()
            self.working_image = img.copy()
            self.current_info = info
            self.history_stack.clear()

            # Update Canvas and Sidebar
            self.canvas_view.set_image(self.working_image, reset_crop=True)
            self.sidebar.set_file_info(info)
            self.update_live_size_estimate()

            self.title(f"Universal Image Toolkit — {info.filename} ({info.width}×{info.height})")

        except Exception as e:
            messagebox.showerror("Failed to Load Image", f"Could not load image:\n{e}")

    # --- Editing Operations ---
    def apply_resize(self, width: int, height: int, keep_aspect: bool, resample: ResampleFilter):
        if not self.working_image:
            return
        self._push_history()
        self.working_image = ImageProcessor.resize(
            self.working_image,
            target_width=width,
            target_height=height,
            keep_aspect_ratio=keep_aspect,
            resample=resample,
        )
        self.canvas_view.set_image(self.working_image, reset_crop=True)
        self.sidebar.set_dimensions(self.working_image.width, self.working_image.height)
        self.update_live_size_estimate()

    def set_crop_preset(self, aspect_ratio: Optional[float]):
        self.canvas_view.set_crop_aspect_ratio(aspect_ratio)

    def set_crop_coords_manual(self, left: int, top: int, right: int, bottom: int):
        self.canvas_view.set_crop_box_pixels(left, top, right, bottom)

    def _on_crop_coords_from_canvas(self, left: int, top: int, right: int, bottom: int):
        self.sidebar.set_crop_coordinates_ui(left, top, right, bottom)

    def apply_crop(self):
        if not self.working_image:
            return
        self._push_history()
        box = self.canvas_view.crop_img_coords
        self.working_image = ImageProcessor.crop(self.working_image, box)
        self.canvas_view.set_image(self.working_image, reset_crop=True)
        self.sidebar.set_dimensions(self.working_image.width, self.working_image.height)
        self.update_live_size_estimate()

    def reset_crop(self):
        self.canvas_view.reset_crop()

    def apply_rotation(self, degrees: int):
        if not self.working_image:
            return
        self._push_history()
        self.working_image = ImageProcessor.rotate(self.working_image, degrees)
        self.canvas_view.set_image(self.working_image, reset_crop=True)
        self.sidebar.set_dimensions(self.working_image.width, self.working_image.height)
        self.update_live_size_estimate()

    def apply_flip(self, direction: str):
        if not self.working_image:
            return
        self._push_history()
        if direction == "horizontal":
            self.working_image = ImageProcessor.flip_horizontal(self.working_image)
        else:
            self.working_image = ImageProcessor.flip_vertical(self.working_image)
        self.canvas_view.set_image(self.working_image, reset_crop=False)
        self.update_live_size_estimate()

    def update_live_size_estimate(self):
        if not self.working_image:
            return
        options = self.sidebar.get_export_options()
        orig_bytes = self.current_info.file_size_bytes if self.current_info else None
        estimate = ImageOptimizer.estimate_size(self.working_image, options, orig_bytes)
        self.sidebar.update_size_estimate(estimate)

    def export_image(self, options: ExportOptions):
        if not self.working_image:
            messagebox.showwarning("No Image", "Please open an image first before exporting.")
            return

        # Prepare default filename and extension
        ext = FORMAT_EXTENSION_MAP.get(options.format, ".jpg")
        default_name = "image_optimized" + ext
        if self.current_image_path:
            default_name = f"{self.current_image_path.stem}_optimized{ext}"

        save_path = filedialog.asksaveasfilename(
            title="Save Exported Image",
            initialfile=default_name,
            defaultextension=ext,
            filetypes=[(f"{options.format.name} (*{ext})", f"*{ext}"), ("All files", "*.*")],
        )

        if not save_path:
            return

        try:
            bytes_written = FormatHandler.export(self.working_image, save_path, options)
            formatted_size = SizeEstimate.format_bytes(bytes_written)

            msg = f"Image exported successfully to:\n{save_path}\n\nFinal File Size: {formatted_size}"
            if self.current_info and self.current_info.file_size_bytes > 0:
                diff = self.current_info.file_size_bytes - bytes_written
                pct = (diff / self.current_info.file_size_bytes) * 100.0
                if pct > 0:
                    msg += f"\nSavings: {pct:.1f}% reduction!"

            messagebox.showinfo("Export Successful", msg)

        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to save image:\n{e}")

    def open_batch_dialog(self):
        options = self.sidebar.get_export_options()
        BatchProcessorDialog(self, current_options=options)
