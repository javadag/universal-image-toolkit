"""
Sidebar control panel containing tools for resize, crop, compression, multi-format export, and transformations.
"""
from typing import Callable, Optional, Tuple
import customtkinter as ctk
from PIL import Image

from engine.processor import ResampleFilter, ImageInfo
from engine.format_handler import ExportFormat, ExportOptions
from engine.optimizer import ImageOptimizer, SizeEstimate
from ui.theme import COLORS, FONTS


class SidebarControls(ctk.CTkScrollableFrame):
    """
    Control panel for all image manipulation, compression, and export settings.
    """

    def __init__(
        self,
        master,
        on_resize_requested: Optional[Callable[[int, int, bool, ResampleFilter], None]] = None,
        on_crop_preset_selected: Optional[Callable[[Optional[float]], None]] = None,
        on_crop_coords_changed: Optional[Callable[[int, int, int, int], None]] = None,
        on_apply_crop: Optional[Callable[[], None]] = None,
        on_reset_crop: Optional[Callable[[], None]] = None,
        on_rotate: Optional[Callable[[int], None]] = None,
        on_flip: Optional[Callable[[str], None]] = None,
        on_export: Optional[Callable[[ExportOptions], None]] = None,
        on_open_batch_dialog: Optional[Callable[[], None]] = None,
        on_options_changed: Optional[Callable[[], None]] = None,
        get_working_image: Optional[Callable[[], Optional[Image.Image]]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=COLORS["sidebar_bg"], **kwargs)

        # Callbacks
        self.on_resize_requested = on_resize_requested
        self.on_crop_preset_selected = on_crop_preset_selected
        self.on_crop_coords_changed = on_crop_coords_changed
        self.on_apply_crop = on_apply_crop
        self.on_reset_crop = on_reset_crop
        self.on_rotate = on_rotate
        self.on_flip = on_flip
        self.on_export = on_export
        self.on_open_batch_dialog = on_open_batch_dialog
        self.on_options_changed = on_options_changed
        self.get_working_image = get_working_image

        # State
        self.current_info: Optional[ImageInfo] = None
        self.keep_aspect_ratio_var = ctk.BooleanVar(value=True)
        self.strip_metadata_var = ctk.BooleanVar(value=True)
        self.webp_lossless_var = ctk.BooleanVar(value=False)
        self.png_quantize_enabled_var = ctk.BooleanVar(value=False)
        self.is_updating_ui = False

        self._build_ui()

    def _build_ui(self):
        # 1. Header Title
        lbl_title = ctk.CTkLabel(
            self,
            text="TOOLKIT CONTROLS",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        lbl_title.pack(fill="x", padx=12, pady=(8, 4))

        # 2. File Metadata Summary Card
        self._build_file_info_card()

        # 3. Tabview for features
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=COLORS["card_bg"],
            segmented_button_selected_color=COLORS["accent_primary"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
            segmented_button_unselected_color=COLORS["card_border"],
            segmented_button_unselected_hover_color=COLORS["sidebar_bg"],
            segmented_button_fg_color=COLORS["sidebar_bg"],
            text_color=COLORS["text_primary"],
            corner_radius=12,
        )
        self.tabview._segmented_button.configure(
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            selected_color=COLORS["accent_primary"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["card_border"],
            unselected_hover_color=COLORS["sidebar_bg"],
        )
        self.tabview.pack(fill="x", padx=8, pady=8)

        self.tab_resize = self.tabview.add("Resize")
        self.tab_crop = self.tabview.add("Crop")
        self.tab_compress = self.tabview.add("Compress")
        self.tab_transform = self.tabview.add("Transforms")

        self._build_resize_tab()
        self._build_crop_tab()
        self._build_compress_tab()
        self._build_transforms_tab()

        # 4. Estimated Output Card
        self._build_estimate_card()

        # 5. Export Action Buttons
        self._build_action_buttons()

    # -------------------------------------------------------------
    # 1. File Info Card
    # -------------------------------------------------------------
    def _build_file_info_card(self):
        self.card_info = ctk.CTkFrame(
            self,
            fg_color=COLORS["card_bg"],
            border_color=COLORS["card_border"],
            border_width=1,
            corner_radius=10,
        )
        self.card_info.pack(fill="x", padx=8, pady=4)

        self.lbl_filename = ctk.CTkLabel(
            self.card_info,
            text="No file loaded",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.lbl_filename.pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_details = ctk.CTkLabel(
            self.card_info,
            text="Resolution: -- | Size: -- | Format: --",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.lbl_details.pack(fill="x", padx=10, pady=(0, 8))

    # -------------------------------------------------------------
    # 2. Resize Tab
    # -------------------------------------------------------------
    def _build_resize_tab(self):
        f = self.tab_resize

        # Pixel Dimensions Inputs
        dim_frame = ctk.CTkFrame(f, fg_color="transparent")
        dim_frame.pack(fill="x", pady=4)

        # Width
        w_box = ctk.CTkFrame(dim_frame, fg_color="transparent")
        w_box.pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkLabel(w_box, text="Width (px)", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.entry_width = ctk.CTkEntry(w_box, placeholder_text="W", height=32, corner_radius=8)
        self.entry_width.pack(fill="x")
        self.entry_width.bind("<KeyRelease>", self._on_width_input)

        # Height
        h_box = ctk.CTkFrame(dim_frame, fg_color="transparent")
        h_box.pack(side="right", expand=True, fill="x", padx=(4, 0))
        ctk.CTkLabel(h_box, text="Height (px)", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.entry_height = ctk.CTkEntry(h_box, placeholder_text="H", height=32, corner_radius=8)
        self.entry_height.pack(fill="x")
        self.entry_height.bind("<KeyRelease>", self._on_height_input)

        # Aspect Ratio Lock Toggle
        self.chk_lock_aspect = ctk.CTkCheckBox(
            f,
            text="Lock Aspect Ratio",
            variable=self.keep_aspect_ratio_var,
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            checkbox_height=18,
            checkbox_width=18,
            corner_radius=4,
        )
        self.chk_lock_aspect.pack(anchor="w", pady=(8, 4))

        # Percentage Scale Slider
        ctk.CTkLabel(f, text="Scale Percentage", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(8, 0))
        scale_box = ctk.CTkFrame(f, fg_color="transparent")
        scale_box.pack(fill="x", pady=2)

        self.slider_scale = ctk.CTkSlider(
            scale_box,
            from_=10,
            to=200,
            number_of_steps=190,
            command=self._on_scale_slider,
        )
        self.slider_scale.set(100)
        self.slider_scale.pack(side="left", expand=True, fill="x")

        self.lbl_scale_val = ctk.CTkLabel(scale_box, text="100%", font=FONTS["small"], width=42)
        self.lbl_scale_val.pack(side="right", padx=(6, 0))

        # Presets Buttons
        ctk.CTkLabel(f, text="Resolution Presets", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(8, 2))
        preset_grid = ctk.CTkFrame(f, fg_color="transparent")
        preset_grid.pack(fill="x", pady=2)

        presets = [
            ("4K (3840×2160)", 3840, 2160),
            ("1080p (1920×1080)", 1920, 1080),
            ("720p (1280×720)", 1280, 720),
            ("Square (1080×1080)", 1080, 1080),
            ("Story (1080×1920)", 1080, 1920),
            ("Thumb (400×400)", 400, 400),
        ]

        for i, (name, pw, ph) in enumerate(presets):
            row = i // 2
            col = i % 2
            btn = ctk.CTkButton(
                preset_grid,
                text=name,
                font=FONTS["small"],
                height=26,
                fg_color=COLORS["card_border"],
                hover_color=COLORS["accent_primary"],
                text_color=COLORS["text_primary"],
                command=lambda w=pw, h=ph: self._apply_preset_dimensions(w, h),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
        preset_grid.grid_columnconfigure(0, weight=1)
        preset_grid.grid_columnconfigure(1, weight=1)

        # Resampling Filter
        ctk.CTkLabel(f, text="Resampling Quality", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(8, 2))
        self.combo_filter = ctk.CTkComboBox(
            f,
            values=[f.value for f in ResampleFilter],
            font=FONTS["small"],
            dropdown_font=FONTS["small"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            height=30,
        )
        self.combo_filter.set(ResampleFilter.LANCZOS.value)
        self.combo_filter.pack(fill="x", pady=(0, 6))

        # Apply Resize Button
        self.btn_apply_resize = ctk.CTkButton(
            f,
            text="Apply Resize",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            height=32,
            command=self._trigger_resize,
        )
        self.btn_apply_resize.pack(fill="x", pady=(6, 2))

    # -------------------------------------------------------------
    # 3. Crop Tab
    # -------------------------------------------------------------
    def _build_crop_tab(self):
        f = self.tab_crop

        ctk.CTkLabel(f, text="Aspect Ratio Presets", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(2, 2))

        self.crop_presets = {
            "Freeform (Custom)": None,
            "1:1 (Square - Instagram)": 1.0,
            "16:9 (Landscape - YouTube)": 16 / 9,
            "9:16 (Story / Reel / TikTok)": 9 / 16,
            "4:3 (Standard Photo)": 4 / 3,
            "4:5 (Portrait - Instagram)": 4 / 5,
            "3:2 (Classic 35mm)": 3 / 2,
            "2:1 (Ultrawide Banner)": 2.0,
        }

        self.combo_crop_aspect = ctk.CTkComboBox(
            f,
            values=list(self.crop_presets.keys()),
            font=FONTS["small"],
            dropdown_font=FONTS["small"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            height=30,
            command=self._on_crop_aspect_selected,
        )
        self.combo_crop_aspect.set("Freeform (Custom)")
        self.combo_crop_aspect.pack(fill="x", pady=(0, 6))

        # Manual Pixel Coordinate Bounds
        ctk.CTkLabel(f, text="Crop Coordinates (px)", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(4, 2))
        coords_grid = ctk.CTkFrame(f, fg_color="transparent")
        coords_grid.pack(fill="x", pady=2)

        # Left / Top / Right / Bottom
        self.entry_crop_l = ctk.CTkEntry(coords_grid, placeholder_text="Left", height=28, font=FONTS["small"])
        self.entry_crop_t = ctk.CTkEntry(coords_grid, placeholder_text="Top", height=28, font=FONTS["small"])
        self.entry_crop_r = ctk.CTkEntry(coords_grid, placeholder_text="Right", height=28, font=FONTS["small"])
        self.entry_crop_b = ctk.CTkEntry(coords_grid, placeholder_text="Bottom", height=28, font=FONTS["small"])

        self.entry_crop_l.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.entry_crop_t.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.entry_crop_r.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        self.entry_crop_b.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        coords_grid.grid_columnconfigure(0, weight=1)
        coords_grid.grid_columnconfigure(1, weight=1)

        for ent in (self.entry_crop_l, self.entry_crop_t, self.entry_crop_r, self.entry_crop_b):
            ent.bind("<KeyRelease>", self._on_crop_entry_changed)

        # Buttons: Apply Crop & Reset Crop
        crop_btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        crop_btn_frame.pack(fill="x", pady=(8, 2))

        self.btn_reset_crop = ctk.CTkButton(
            crop_btn_frame,
            text="Reset Full",
            font=FONTS["small"],
            fg_color=COLORS["card_border"],
            hover_color=COLORS["accent_danger"],
            text_color=COLORS["text_primary"],
            height=30,
            command=self._on_reset_crop_clicked,
        )
        self.btn_reset_crop.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_apply_crop_btn = ctk.CTkButton(
            crop_btn_frame,
            text="Crop to Selection",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            height=30,
            command=self._on_apply_crop_clicked,
        )
        self.btn_apply_crop_btn.pack(side="right", expand=True, fill="x", padx=(4, 0))

    # -------------------------------------------------------------
    # 4. Compress & Convert Tab
    # -------------------------------------------------------------
    def _build_compress_tab(self):
        f = self.tab_compress

        # Format selector
        ctk.CTkLabel(f, text="Export Format", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(2, 2))
        self.combo_format = ctk.CTkComboBox(
            f,
            values=[fmt.value for fmt in ExportFormat],
            font=FONTS["body_bold"],
            dropdown_font=FONTS["body"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            height=32,
            command=self._on_format_changed,
        )
        self.combo_format.set(ExportFormat.WEBP.value)
        self.combo_format.pack(fill="x", pady=(0, 6))

        # Quality Slider (for JPEG / WebP / AVIF)
        self.frame_quality = ctk.CTkFrame(f, fg_color="transparent")
        self.frame_quality.pack(fill="x", pady=2)

        ctk.CTkLabel(self.frame_quality, text="Quality (1-100)", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        q_row = ctk.CTkFrame(self.frame_quality, fg_color="transparent")
        q_row.pack(fill="x")

        self.slider_quality = ctk.CTkSlider(
            q_row,
            from_=1,
            to=100,
            number_of_steps=99,
            command=self._on_quality_slider,
        )
        self.slider_quality.set(80)
        self.slider_quality.pack(side="left", expand=True, fill="x")

        self.lbl_quality_val = ctk.CTkLabel(q_row, text="80", font=FONTS["body_bold"], width=36)
        self.lbl_quality_val.pack(side="right", padx=(6, 0))

        # WebP Lossless Toggle
        self.chk_lossless = ctk.CTkCheckBox(
            f,
            text="Lossless Compression (WebP)",
            variable=self.webp_lossless_var,
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            command=self._on_option_toggled,
            checkbox_height=18,
            checkbox_width=18,
            corner_radius=4,
        )
        self.chk_lossless.pack(anchor="w", pady=4)

        # PNG Quantization (Color Palette Reduction)
        self.frame_png = ctk.CTkFrame(f, fg_color="transparent")
        self.frame_png.pack(fill="x", pady=2)

        self.chk_quantize = ctk.CTkCheckBox(
            self.frame_png,
            text="PNG Palette Reduction (Huge Savings)",
            variable=self.png_quantize_enabled_var,
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            command=self._on_quantize_toggled,
            checkbox_height=18,
            checkbox_width=18,
            corner_radius=4,
        )
        self.chk_quantize.pack(anchor="w", pady=2)

        self.frame_quant_colors = ctk.CTkFrame(self.frame_png, fg_color="transparent")
        self.slider_quant_colors = ctk.CTkSlider(
            self.frame_quant_colors,
            from_=8,
            to=256,
            number_of_steps=31,
            command=self._on_quant_colors_slider,
        )
        self.slider_quant_colors.set(128)
        self.slider_quant_colors.pack(side="left", expand=True, fill="x")

        self.lbl_quant_colors_val = ctk.CTkLabel(self.frame_quant_colors, text="128 colors", font=FONTS["small"], width=70)
        self.lbl_quant_colors_val.pack(side="right", padx=(4, 0))

        # EXIF Metadata Stripping
        self.chk_strip_metadata = ctk.CTkCheckBox(
            f,
            text="Strip EXIF & Metadata (Smaller size & privacy)",
            variable=self.strip_metadata_var,
            font=FONTS["small"],
            text_color=COLORS["text_primary"],
            command=self._on_option_toggled,
            checkbox_height=18,
            checkbox_width=18,
            corner_radius=4,
        )
        self.chk_strip_metadata.pack(anchor="w", pady=(4, 6))

        # Auto-Tune Quality to Target Size
        self.btn_auto_tune = ctk.CTkButton(
            f,
            text="🎯 Auto-Fit to Target File Size",
            font=FONTS["small"],
            fg_color=COLORS["card_border"],
            hover_color=COLORS["accent_purple"],
            text_color=COLORS["text_primary"],
            height=28,
            command=self._prompt_target_size,
        )
        self.btn_auto_tune.pack(fill="x", pady=(2, 4))

    # -------------------------------------------------------------
    # 5. Transforms Tab
    # -------------------------------------------------------------
    def _build_transforms_tab(self):
        f = self.tab_transform

        ctk.CTkLabel(f, text="Rotate", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(2, 2))
        rot_frame = ctk.CTkFrame(f, fg_color="transparent")
        rot_frame.pack(fill="x", pady=2)

        ctk.CTkButton(
            rot_frame, text="⟲ 90° Left", font=FONTS["small"], height=28, fg_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            command=lambda: self.on_rotate(270) if self.on_rotate else None
        ).pack(side="left", expand=True, fill="x", padx=(0, 2))

        ctk.CTkButton(
            rot_frame, text="⟳ 90° Right", font=FONTS["small"], height=28, fg_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            command=lambda: self.on_rotate(90) if self.on_rotate else None
        ).pack(side="left", expand=True, fill="x", padx=2)

        ctk.CTkButton(
            rot_frame, text="180°", font=FONTS["small"], height=28, fg_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            command=lambda: self.on_rotate(180) if self.on_rotate else None
        ).pack(side="right", expand=True, fill="x", padx=(2, 0))

        ctk.CTkLabel(f, text="Flip", font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(8, 2))
        flip_frame = ctk.CTkFrame(f, fg_color="transparent")
        flip_frame.pack(fill="x", pady=2)

        ctk.CTkButton(
            flip_frame, text="↔ Flip Horizontal", font=FONTS["small"], height=28, fg_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            command=lambda: self.on_flip("horizontal") if self.on_flip else None
        ).pack(side="left", expand=True, fill="x", padx=(0, 2))

        ctk.CTkButton(
            flip_frame, text="↕ Flip Vertical", font=FONTS["small"], height=28, fg_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            command=lambda: self.on_flip("vertical") if self.on_flip else None
        ).pack(side="right", expand=True, fill="x", padx=(2, 0))

    # -------------------------------------------------------------
    # 6. Estimated Output Card
    # -------------------------------------------------------------
    def _build_estimate_card(self):
        self.card_estimate = ctk.CTkFrame(
            self,
            fg_color=COLORS["card_bg"],
            border_color=COLORS["card_border"],
            border_width=1,
            corner_radius=10,
        )
        self.card_estimate.pack(fill="x", padx=8, pady=6)

        header_row = ctk.CTkFrame(self.card_estimate, fg_color="transparent")
        header_row.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            header_row,
            text="ESTIMATED OUTPUT",
            font=FONTS["badge"],
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        self.lbl_savings_badge = ctk.CTkLabel(
            header_row,
            text="-0%",
            font=FONTS["badge"],
            text_color=COLORS["accent_success"],
        )
        self.lbl_savings_badge.pack(side="right")

        self.lbl_estimate_text = ctk.CTkLabel(
            self.card_estimate,
            text="Estimated Size: --",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.lbl_estimate_text.pack(fill="x", padx=10, pady=(0, 8))

    # -------------------------------------------------------------
    # 7. Action Buttons (Export)
    # -------------------------------------------------------------
    def _build_action_buttons(self):
        self.btn_export = ctk.CTkButton(
            self,
            text="💾 Save / Export Image",
            font=FONTS["subtitle"],
            fg_color=COLORS["accent_success"],
            hover_color="#059669",
            text_color="#ffffff",
            height=44,
            corner_radius=10,
            command=self._trigger_export,
        )
        self.btn_export.pack(fill="x", padx=8, pady=(8, 12))

    # -------------------------------------------------------------
    # UI Event Handlers & State Sync
    # -------------------------------------------------------------
    def set_file_info(self, info: ImageInfo):
        self.current_info = info
        self.lbl_filename.configure(text=info.filename)
        self.lbl_details.configure(
            text=f"{info.width} × {info.height} px  •  {info.formatted_file_size}  •  {info.format}"
        )
        self.set_dimensions(info.width, info.height)

    def set_dimensions(self, width: int, height: int):
        self.is_updating_ui = True
        self.entry_width.delete(0, "end")
        self.entry_width.insert(0, str(width))
        self.entry_height.delete(0, "end")
        self.entry_height.insert(0, str(height))
        self.slider_scale.set(100)
        self.lbl_scale_val.configure(text="100%")
        self.is_updating_ui = False

    def set_crop_coordinates_ui(self, left: int, top: int, right: int, bottom: int):
        self.is_updating_ui = True
        self.entry_crop_l.delete(0, "end")
        self.entry_crop_l.insert(0, str(left))
        self.entry_crop_t.delete(0, "end")
        self.entry_crop_t.insert(0, str(top))
        self.entry_crop_r.delete(0, "end")
        self.entry_crop_r.insert(0, str(right))
        self.entry_crop_b.delete(0, "end")
        self.entry_crop_b.insert(0, str(bottom))
        self.is_updating_ui = False

    def update_size_estimate(self, estimate: SizeEstimate):
        self.lbl_estimate_text.configure(text=f"Estimated: {estimate.formatted_size}")
        if estimate.savings_percentage > 0:
            self.lbl_savings_badge.configure(
                text=f"-{estimate.savings_percentage:.1f}% Smaller",
                text_color=COLORS["accent_success"],
            )
        elif estimate.savings_percentage < 0:
            self.lbl_savings_badge.configure(
                text=f"+{abs(estimate.savings_percentage):.1f}% Larger",
                text_color=COLORS["accent_warning"],
            )
        else:
            self.lbl_savings_badge.configure(text="Same size", text_color=COLORS["text_secondary"])

    def get_export_options(self) -> ExportOptions:
        fmt_str = self.combo_format.get()
        # Match enum
        chosen_fmt = ExportFormat.WEBP
        for f in ExportFormat:
            if f.value == fmt_str:
                chosen_fmt = f
                break

        quality = int(self.slider_quality.get())
        strip_meta = self.strip_metadata_var.get()
        lossless = self.webp_lossless_var.get()
        quantize_colors = int(self.slider_quant_colors.get()) if self.png_quantize_enabled_var.get() else None

        return ExportOptions(
            format=chosen_fmt,
            quality=quality,
            strip_metadata=strip_meta,
            webp_lossless=lossless,
            png_quantize_colors=quantize_colors,
        )

    def _on_width_input(self, event):
        if self.is_updating_ui or not self.keep_aspect_ratio_var.get() or not self.current_info:
            return
        try:
            w = int(self.entry_width.get())
            aspect = self.current_info.aspect_ratio
            h = max(1, int(w / aspect))
            self.is_updating_ui = True
            self.entry_height.delete(0, "end")
            self.entry_height.insert(0, str(h))
            self.is_updating_ui = False
        except ValueError:
            pass

    def _on_height_input(self, event):
        if self.is_updating_ui or not self.keep_aspect_ratio_var.get() or not self.current_info:
            return
        try:
            h = int(self.entry_height.get())
            aspect = self.current_info.aspect_ratio
            w = max(1, int(h * aspect))
            self.is_updating_ui = True
            self.entry_width.delete(0, "end")
            self.entry_width.insert(0, str(w))
            self.is_updating_ui = False
        except ValueError:
            pass

    def _on_scale_slider(self, val: float):
        percent = int(val)
        self.lbl_scale_val.configure(text=f"{percent}%")
        if not self.current_info:
            return
        orig_w = self.current_info.width
        orig_h = self.current_info.height
        new_w = max(1, int(orig_w * percent / 100))
        new_h = max(1, int(orig_h * percent / 100))
        self.is_updating_ui = True
        self.entry_width.delete(0, "end")
        self.entry_width.insert(0, str(new_w))
        self.entry_height.delete(0, "end")
        self.entry_height.insert(0, str(new_h))
        self.is_updating_ui = False

    def _apply_preset_dimensions(self, width: int, height: int):
        self.is_updating_ui = True
        self.entry_width.delete(0, "end")
        self.entry_width.insert(0, str(width))
        self.entry_height.delete(0, "end")
        self.entry_height.insert(0, str(height))
        self.is_updating_ui = False
        self._trigger_resize()

    def _trigger_resize(self):
        try:
            w = int(self.entry_width.get())
            h = int(self.entry_height.get())
            keep = self.keep_aspect_ratio_var.get()
            filter_name = self.combo_filter.get()
            resample = ResampleFilter.LANCZOS
            for rf in ResampleFilter:
                if rf.value == filter_name:
                    resample = rf
                    break
            if self.on_resize_requested:
                self.on_resize_requested(w, h, keep, resample)
        except ValueError:
            pass

    def _on_crop_aspect_selected(self, choice: str):
        aspect = self.crop_presets.get(choice)
        if self.on_crop_preset_selected:
            self.on_crop_preset_selected(aspect)

    def _on_crop_entry_changed(self, event):
        if self.is_updating_ui:
            return
        try:
            l = int(self.entry_crop_l.get())
            t = int(self.entry_crop_t.get())
            r = int(self.entry_crop_r.get())
            b = int(self.entry_crop_b.get())
            if self.on_crop_coords_changed:
                self.on_crop_coords_changed(l, t, r, b)
        except ValueError:
            pass

    def _on_reset_crop_clicked(self):
        self.combo_crop_aspect.set("Freeform (Custom)")
        if self.on_reset_crop:
            self.on_reset_crop()

    def _on_apply_crop_clicked(self):
        if self.on_apply_crop:
            self.on_apply_crop()

    def _on_format_changed(self, choice: str):
        if choice.startswith("PNG"):
            self.frame_png.pack(fill="x", pady=2)
            self.frame_quality.pack_forget()
            self.chk_lossless.pack_forget()
        elif choice.startswith("WebP"):
            self.frame_png.pack_forget()
            self.frame_quality.pack(fill="x", pady=2)
            self.chk_lossless.pack(anchor="w", pady=4)
        elif choice.startswith("JPEG") or choice.startswith("AVIF"):
            self.frame_png.pack_forget()
            self.frame_quality.pack(fill="x", pady=2)
            self.chk_lossless.pack_forget()
        else:
            self.frame_png.pack_forget()
            self.frame_quality.pack_forget()
            self.chk_lossless.pack_forget()

        if self.on_options_changed:
            self.on_options_changed()

    def _on_quality_slider(self, val: float):
        q = int(val)
        self.lbl_quality_val.configure(text=str(q))
        if self.on_options_changed:
            self.on_options_changed()

    def _on_quantize_toggled(self):
        if self.png_quantize_enabled_var.get():
            self.frame_quant_colors.pack(fill="x", pady=2)
        else:
            self.frame_quant_colors.pack_forget()
        if self.on_options_changed:
            self.on_options_changed()

    def _on_quant_colors_slider(self, val: float):
        c = int(val)
        self.lbl_quant_colors_val.configure(text=f"{c} colors")
        if self.on_options_changed:
            self.on_options_changed()

    def _on_option_toggled(self):
        if self.on_options_changed:
            self.on_options_changed()

    def _prompt_target_size(self):
        dialog = ctk.CTkInputDialog(text="Enter Target Max Size (e.g. 500 KB or 1.2 MB):", title="Auto-Tune Quality")
        val = dialog.get_input()
        if not val:
            return
        val = val.strip().upper()
        target_bytes = 0
        try:
            if val.endswith("KB"):
                target_bytes = int(float(val.replace("KB", "").strip()) * 1024)
            elif val.endswith("MB"):
                target_bytes = int(float(val.replace("MB", "").strip()) * 1024 * 1024)
            elif val.endswith("B"):
                target_bytes = int(val.replace("B", "").strip())
            else:
                target_bytes = int(float(val) * 1024)  # Default assume KB
        except ValueError:
            return

        if target_bytes > 0 and self.current_info:
            options = self.get_export_options()
            # Get the actual working image from the main window
            working_img = self.get_working_image() if self.get_working_image else None
            if working_img is None:
                return
            best_q, _ = ImageOptimizer.find_best_quality_for_target_size(
                working_img, target_bytes, options.format
            )
            self.slider_quality.set(best_q)
            self.lbl_quality_val.configure(text=str(best_q))
            if self.on_options_changed:
                self.on_options_changed()

    def _trigger_export(self):
        if self.on_export:
            self.on_export(self.get_export_options())
