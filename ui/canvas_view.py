"""
Interactive canvas component for image viewing, zooming, panning, and visual cropping.
"""
import math
import tkinter as tk
from typing import Callable, Optional, Tuple
import customtkinter as ctk
from PIL import Image, ImageTk
from ui.theme import COLORS, FONTS, get_color


class InteractiveImageCanvas(ctk.CTkFrame):
    """
    An interactive zoomable and panable canvas with a visual crop overlay and rule-of-thirds grid.
    """

    def __init__(
        self,
        master,
        on_crop_changed: Optional[Callable[[int, int, int, int], None]] = None,
        on_image_drop: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=COLORS["canvas_bg"], **kwargs)

        self.on_crop_changed = on_crop_changed
        self.on_image_drop = on_image_drop

        # Image state
        self.original_image: Optional[Image.Image] = None
        self.current_preview_image: Optional[Image.Image] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None

        # Transform & Viewport state
        self.zoom_level: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.fit_zoom: float = 1.0

        # Crop state
        self.crop_enabled: bool = False
        self.crop_aspect_ratio: Optional[float] = None  # None for freeform, or float (w/h)
        # Crop bounds in original image coordinates: (x1, y1, x2, y2)
        self.crop_img_coords: Tuple[int, int, int, int] = (0, 0, 0, 0)

        # Dragging state for crop box & handles
        self.active_handle: Optional[str] = None
        self.drag_start_x: float = 0
        self.drag_start_y: float = 0
        self.pan_start_x: float = 0
        self.pan_start_y: float = 0
        self.is_panning: bool = False

        # Create Tkinter Canvas
        self.canvas = tk.Canvas(
            self,
            bg=get_color("canvas_bg"),
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        # Control overlay toolbar (Zoom in/out, fit, 100%, crop toggle)
        self._build_floating_toolbar()

        # Canvas Event bindings
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonPress-3>", self._on_pan_start)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)

        # Mouse wheel zoom
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom(1.15, e.x, e.y))
        self.canvas.bind("<Button-5>", lambda e: self._zoom(1 / 1.15, e.x, e.y))

    def _build_floating_toolbar(self):
        """Constructs a glassmorphism floating bottom toolbar for zoom & fit."""
        self.toolbar_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["card_bg"],
            border_color=COLORS["card_border"],
            border_width=1,
            corner_radius=20,
            height=36,
        )
        self.toolbar_frame.place(relx=0.5, rely=0.94, anchor="center")

        btn_style = {
            "width": 32,
            "height": 28,
            "corner_radius": 14,
            "fg_color": "transparent",
            "hover_color": COLORS["card_border"],
            "text_color": COLORS["text_primary"],
            "font": FONTS["body_bold"],
        }

        self.btn_zoom_out = ctk.CTkButton(
            self.toolbar_frame, text="−", command=lambda: self._zoom(1 / 1.15), **btn_style
        )
        self.btn_zoom_out.pack(side="left", padx=(6, 2), pady=4)

        self.entry_zoom = ctk.CTkEntry(
            self.toolbar_frame,
            width=54,
            height=26,
            corner_radius=13,
            fg_color=COLORS["card_border"],
            border_width=0,
            text_color=COLORS["text_primary"],
            font=FONTS["small"],
            justify="center",
        )
        self.entry_zoom.insert(0, "100%")
        self.entry_zoom.pack(side="left", padx=2, pady=4)
        self.entry_zoom.bind("<Return>", self._on_zoom_entry_submit)
        self.entry_zoom.bind("<FocusOut>", self._on_zoom_entry_submit)

        self.btn_zoom_in = ctk.CTkButton(
            self.toolbar_frame, text="+", command=lambda: self._zoom(1.15), **btn_style
        )
        self.btn_zoom_in.pack(side="left", padx=2, pady=4)

        self.sep = ctk.CTkFrame(self.toolbar_frame, width=1, height=18, fg_color=COLORS["card_border"])
        self.sep.pack(side="left", padx=6, pady=6)

        self.btn_fit = ctk.CTkButton(
            self.toolbar_frame,
            text="Fit",
            command=self.fit_to_view,
            width=40,
            height=28,
            corner_radius=14,
            fg_color="transparent",
            hover_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            font=FONTS["small"],
        )
        self.btn_fit.pack(side="left", padx=2, pady=4)

        self.btn_actual = ctk.CTkButton(
            self.toolbar_frame,
            text="1:1",
            command=self.reset_to_100_percent,
            width=36,
            height=28,
            corner_radius=14,
            fg_color="transparent",
            hover_color=COLORS["card_border"],
            text_color=COLORS["text_primary"],
            font=FONTS["small"],
        )
        self.btn_actual.pack(side="left", padx=(2, 6), pady=4)

    def set_image(self, img: Image.Image, reset_crop: bool = True):
        """Loads a new image onto the canvas."""
        self.original_image = img.copy()
        self.current_preview_image = img.copy()

        if reset_crop:
            self.crop_img_coords = (0, 0, img.width, img.height)
            if self.on_crop_changed:
                self.on_crop_changed(*self.crop_img_coords)

        self.fit_to_view()

    def set_crop_aspect_ratio(self, aspect_ratio: Optional[float]):
        """Sets an aspect ratio constraint for the visual crop box."""
        self.crop_aspect_ratio = aspect_ratio
        if self.original_image and aspect_ratio is not None:
            # Recompute centered crop box with new aspect ratio
            img_w, img_h = self.original_image.size
            if (img_w / img_h) > aspect_ratio:
                new_w = int(img_h * aspect_ratio)
                new_h = img_h
            else:
                new_w = img_w
                new_h = int(img_w / aspect_ratio)

            left = (img_w - new_w) // 2
            top = (img_h - new_h) // 2
            self.crop_img_coords = (left, top, left + new_w, top + new_h)

            if self.on_crop_changed:
                self.on_crop_changed(*self.crop_img_coords)

            self.redraw()

    def set_crop_box_pixels(self, left: int, top: int, right: int, bottom: int):
        """Updates the crop coordinates programmatically from sidebar inputs."""
        if not self.original_image:
            return
        img_w, img_h = self.original_image.size
        l = max(0, min(left, img_w - 1))
        t = max(0, min(top, img_h - 1))
        r = max(l + 1, min(right, img_w))
        b = max(t + 1, min(bottom, img_h))
        self.crop_img_coords = (l, t, r, b)
        self.redraw()

    def reset_crop(self):
        """Resets crop box to entire image."""
        if self.original_image:
            self.crop_img_coords = (0, 0, self.original_image.width, self.original_image.height)
            if self.on_crop_changed:
                self.on_crop_changed(*self.crop_img_coords)
            self.redraw()

    def fit_to_view(self):
        """Calculates optimal zoom and centers image within canvas dimensions."""
        if not self.original_image:
            self.redraw_empty_state()
            return

        canvas_w = max(10, self.canvas.winfo_width())
        canvas_h = max(10, self.canvas.winfo_height())
        img_w, img_h = self.original_image.size

        scale_x = (canvas_w - 40) / img_w
        scale_y = (canvas_h - 40) / img_h
        self.fit_zoom = min(scale_x, scale_y, 1.0)
        self.zoom_level = self.fit_zoom

        # Center image
        display_w = img_w * self.zoom_level
        display_h = img_h * self.zoom_level
        self.offset_x = (canvas_w - display_w) / 2.0
        self.offset_y = (canvas_h - display_h) / 2.0

        self.redraw()

    def reset_to_100_percent(self):
        """Sets zoom to 1:1 original pixel scale."""
        if not self.original_image:
            return
        canvas_w = max(10, self.canvas.winfo_width())
        canvas_h = max(10, self.canvas.winfo_height())
        img_w, img_h = self.original_image.size

        self.zoom_level = 1.0
        self.offset_x = (canvas_w - img_w) / 2.0
        self.offset_y = (canvas_h - img_h) / 2.0
        self.redraw()

    def _on_zoom_entry_submit(self, event=None):
        """Applies manual zoom percentage input from user."""
        if not self.original_image:
            return
        text = self.entry_zoom.get().strip().replace("%", "").strip()
        try:
            val = float(text)
            if val > 0:
                target_zoom = max(0.05, min(8.0, val / 100.0))
                self._set_zoom_level(target_zoom)
        except ValueError:
            self._update_zoom_entry_text()

    def _update_zoom_entry_text(self):
        """Synchronizes the zoom entry text with current zoom level."""
        if not hasattr(self, "entry_zoom"):
            return
        # Only update text if entry is not actively focused
        try:
            if self.focus_get() != self.entry_zoom:
                self.entry_zoom.delete(0, "end")
                self.entry_zoom.insert(0, f"{int(self.zoom_level * 100)}%")
        except Exception:
            self.entry_zoom.delete(0, "end")
            self.entry_zoom.insert(0, f"{int(self.zoom_level * 100)}%")

    def _set_zoom_level(self, new_zoom: float, center_x: Optional[float] = None, center_y: Optional[float] = None):
        """Sets an absolute zoom level and repositions offset around center point."""
        if not self.original_image:
            return

        new_zoom = max(0.05, min(8.0, new_zoom))
        old_zoom = self.zoom_level
        if abs(new_zoom - old_zoom) < 1e-4:
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if center_x is None:
            center_x = canvas_w / 2.0
        if center_y is None:
            center_y = canvas_h / 2.0

        # Adjust offsets so cursor remains pinned to same image coordinate
        self.offset_x = center_x - (center_x - self.offset_x) * (new_zoom / old_zoom)
        self.offset_y = center_y - (center_y - self.offset_y) * (new_zoom / old_zoom)
        self.zoom_level = new_zoom

        self.redraw()

    def _zoom(self, factor: float, center_x: Optional[float] = None, center_y: Optional[float] = None):
        """Zooms by a relative multiplier."""
        self._set_zoom_level(self.zoom_level * factor, center_x, center_y)

    def _on_mouse_wheel(self, event):
        """Handles trackpad / mousewheel scrolling with smoothed sensitivity."""
        if event.state & 0x0001:  # Shift key held -> horizontal pan
            self.offset_x += event.delta * 2
            self.redraw()
        else:
            delta = event.delta
            if abs(delta) >= 100:
                # Traditional notched mouse wheel (e.g. +/- 120)
                steps = delta / 120.0
                factor = 1.15 ** steps
            else:
                # High-frequency trackpad or smooth scroll on macOS
                factor = 1.0 + (delta * 0.015)
                factor = max(0.92, min(1.08, factor))

            self._zoom(factor, event.x, event.y)

    def _on_canvas_resize(self, event):
        if not self.original_image:
            self.redraw_empty_state()
        else:
            self.redraw()

    # --- Coordinate Transformations ---
    def img_to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        cx = self.offset_x + x * self.zoom_level
        cy = self.offset_y + y * self.zoom_level
        return cx, cy

    def canvas_to_img(self, cx: float, cy: float) -> Tuple[int, int]:
        if not self.original_image:
            return 0, 0
        ix = int((cx - self.offset_x) / self.zoom_level)
        iy = int((cy - self.offset_y) / self.zoom_level)
        return ix, iy

    def update_theme(self, mode: str):
        """Updates canvas colors when light/dark appearance mode is changed."""
        self.canvas.configure(bg=get_color("canvas_bg"))
        self.redraw()

    # --- Drawing Logic ---
    def redraw_empty_state(self):
        """Draws drag-and-drop placeholder."""
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        cx, cy = w / 2, h / 2
        self.canvas.create_text(
            cx, cy - 20,
            text="🖼️",
            font=("Arial", 48),
            fill=get_color("text_muted"),
        )
        self.canvas.create_text(
            cx, cy + 30,
            text="No Image Loaded",
            font=FONTS["subtitle"],
            fill=get_color("text_secondary"),
        )
        self.canvas.create_text(
            cx, cy + 60,
            text="Click 'Open Image' or Drag & Drop a file to get started",
            font=FONTS["body"],
            fill=get_color("text_muted"),
        )

    def redraw(self):
        """Renders the image, dark crop overlay, rule of thirds grid, and resize handles."""
        self.canvas.delete("all")

        if not self.original_image:
            self.redraw_empty_state()
            return

        # Update zoom input box
        self._update_zoom_entry_text()

        # 1. Render Scaled Image (Viewport-clipped to prevent MemoryError on high zoom / large images)
        canvas_w = max(10, self.canvas.winfo_width())
        canvas_h = max(10, self.canvas.winfo_height())
        img_w, img_h = self.original_image.size

        # Compute visible slice in image coordinates (with safety padding)
        padding = 20
        img_left = max(0, int((-self.offset_x - padding) / self.zoom_level))
        img_top = max(0, int((-self.offset_y - padding) / self.zoom_level))
        img_right = min(img_w, int((canvas_w - self.offset_x + padding) / self.zoom_level) + 1)
        img_bottom = min(img_h, int((canvas_h - self.offset_y + padding) / self.zoom_level) + 1)

        if img_right > img_left and img_bottom > img_top:
            crop_region = self.original_image.crop((img_left, img_top, img_right, img_bottom))
            disp_w = max(1, int((img_right - img_left) * self.zoom_level))
            disp_h = max(1, int((img_bottom - img_top) * self.zoom_level))

            if self.zoom_level > 2.5:
                resample = Image.Resampling.NEAREST
            elif self.zoom_level > 0.5:
                resample = Image.Resampling.BILINEAR
            else:
                resample = Image.Resampling.BOX

            scaled_img = crop_region.resize((disp_w, disp_h), resample)
            self.tk_image = ImageTk.PhotoImage(scaled_img)

            render_x = self.offset_x + img_left * self.zoom_level
            render_y = self.offset_y + img_top * self.zoom_level

            self.canvas.create_image(
                render_x, render_y,
                anchor="nw",
                image=self.tk_image,
            )

        # 2. Render Crop Box & Handles if Crop Mode is active or image loaded
        self._render_crop_overlay()

    def _render_crop_overlay(self):
        """Renders the dimmed background outside crop area, bounding box, grid, and 8 handles."""
        if not self.original_image:
            return

        img_x1, img_y1, img_x2, img_y2 = self.crop_img_coords
        cx1, cy1 = self.img_to_canvas(img_x1, img_y1)
        cx2, cy2 = self.img_to_canvas(img_x2, img_y2)

        # Image canvas boundary
        img_w, img_h = self.original_image.size
        icx1, icy1 = self.img_to_canvas(0, 0)
        icx2, icy2 = self.img_to_canvas(img_w, img_h)

        # Dimmed masks outside crop box (top, bottom, left, right)
        mask_color = "#000000"
        stipple = "gray50"  # Native Tkinter semi-transparent pattern

        # Top mask
        self.canvas.create_rectangle(icx1, icy1, icx2, cy1, fill=mask_color, stipple=stipple, outline="")
        # Bottom mask
        self.canvas.create_rectangle(icx1, cy2, icx2, icy2, fill=mask_color, stipple=stipple, outline="")
        # Left mask
        self.canvas.create_rectangle(icx1, cy1, cx1, cy2, fill=mask_color, stipple=stipple, outline="")
        # Right mask
        self.canvas.create_rectangle(cx2, cy1, icx2, cy2, fill=mask_color, stipple=stipple, outline="")

        # Crop Box Border
        self.canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline=get_color("crop_box_border"),
            width=2,
        )

        # Rule of thirds grid lines
        box_w = cx2 - cx1
        box_h = cy2 - cy1
        if box_w > 40 and box_h > 40:
            # Vertical grid lines
            self.canvas.create_line(cx1 + box_w / 3, cy1, cx1 + box_w / 3, cy2, fill="#ffffff", dash=(2, 4), width=1)
            self.canvas.create_line(cx1 + 2 * box_w / 3, cy1, cx1 + 2 * box_w / 3, cy2, fill="#ffffff", dash=(2, 4), width=1)
            # Horizontal grid lines
            self.canvas.create_line(cx1, cy1 + box_h / 3, cx2, cy1 + box_h / 3, fill="#ffffff", dash=(2, 4), width=1)
            self.canvas.create_line(cx1, cy1 + 2 * box_h / 3, cx2, cy1 + 2 * box_h / 3, fill="#ffffff", dash=(2, 4), width=1)

        # Draw 8 corner & edge handles
        handle_size = 8
        mid_x = (cx1 + cx2) / 2
        mid_y = (cy1 + cy2) / 2

        handles = {
            "nw": (cx1, cy1),
            "n": (mid_x, cy1),
            "ne": (cx2, cy1),
            "e": (cx2, mid_y),
            "se": (cx2, cy2),
            "s": (mid_x, cy2),
            "sw": (cx1, cy2),
            "w": (cx1, mid_y),
        }

        for h_name, (hx, hy) in handles.items():
            self.canvas.create_rectangle(
                hx - handle_size / 2,
                hy - handle_size / 2,
                hx + handle_size / 2,
                hy + handle_size / 2,
                fill=get_color("crop_handle"),
                outline="#ffffff",
                width=1.5,
            )

        # Display crop dimension badge
        crop_w = img_x2 - img_x1
        crop_h = img_y2 - img_y1
        badge_text = f"{crop_w} × {crop_h} px"
        self.canvas.create_text(
            mid_x, cy2 + 14,
            text=badge_text,
            font=FONTS["small"],
            fill=get_color("crop_box_border"),
        )

    # --- Mouse & Handle Interactivity ---
    def _get_hit_handle(self, mouse_x: float, mouse_y: float) -> Optional[str]:
        """Detects if cursor is hovering over a handle or inside the crop box."""
        if not self.original_image:
            return None

        img_x1, img_y1, img_x2, img_y2 = self.crop_img_coords
        cx1, cy1 = self.img_to_canvas(img_x1, img_y1)
        cx2, cy2 = self.img_to_canvas(img_x2, img_y2)

        mid_x = (cx1 + cx2) / 2
        mid_y = (cy1 + cy2) / 2
        threshold = 12

        handles = {
            "nw": (cx1, cy1),
            "n": (mid_x, cy1),
            "ne": (cx2, cy1),
            "e": (cx2, mid_y),
            "se": (cx2, cy2),
            "s": (mid_x, cy2),
            "sw": (cx1, cy2),
            "w": (cx1, mid_y),
        }

        for name, (hx, hy) in handles.items():
            if math.hypot(mouse_x - hx, mouse_y - hy) <= threshold:
                return name

        # Check if inside crop box (for moving the entire box)
        if cx1 <= mouse_x <= cx2 and cy1 <= mouse_y <= cy2:
            return "center"

        return None

    def _on_mouse_down(self, event):
        """Handle mouse click for crop handles or initiating pan."""
        hit = self._get_hit_handle(event.x, event.y)
        if hit:
            self.active_handle = hit
            self.drag_start_x = event.x
            self.drag_start_y = event.y
        else:
            self._on_pan_start(event)

    def _on_mouse_drag(self, event):
        """Handles resizing/moving the crop box."""
        if self.is_panning:
            self._on_pan_drag(event)
            return

        if not self.active_handle or not self.original_image:
            return

        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y

        img_dx = int(dx / self.zoom_level)
        img_dy = int(dy / self.zoom_level)

        if img_dx == 0 and img_dy == 0:
            return

        img_w, img_h = self.original_image.size
        x1, y1, x2, y2 = self.crop_img_coords

        if self.active_handle == "center":
            # Move entire crop box
            box_w = x2 - x1
            box_h = y2 - y1

            new_x1 = max(0, min(x1 + img_dx, img_w - box_w))
            new_y1 = max(0, min(y1 + img_dy, img_h - box_h))
            self.crop_img_coords = (new_x1, new_y1, new_x1 + box_w, new_y1 + box_h)

        elif self.active_handle == "se":
            new_x2 = max(x1 + 10, min(x2 + img_dx, img_w))
            if self.crop_aspect_ratio:
                new_h = int((new_x2 - x1) / self.crop_aspect_ratio)
                new_y2 = min(y1 + new_h, img_h)
                new_x2 = int(x1 + (new_y2 - y1) * self.crop_aspect_ratio)
            else:
                new_y2 = max(y1 + 10, min(y2 + img_dy, img_h))
            self.crop_img_coords = (x1, y1, new_x2, new_y2)

        elif self.active_handle == "nw":
            new_x1 = max(0, min(x1 + img_dx, x2 - 10))
            if self.crop_aspect_ratio:
                new_h = int((x2 - new_x1) / self.crop_aspect_ratio)
                new_y1 = max(0, y2 - new_h)
                new_x1 = int(x2 - (y2 - new_y1) * self.crop_aspect_ratio)
            else:
                new_y1 = max(0, min(y1 + img_dy, y2 - 10))
            self.crop_img_coords = (new_x1, new_y1, x2, y2)

        elif self.active_handle == "ne":
            new_x2 = max(x1 + 10, min(x2 + img_dx, img_w))
            if self.crop_aspect_ratio:
                new_h = int((new_x2 - x1) / self.crop_aspect_ratio)
                new_y1 = max(0, y2 - new_h)
                new_x2 = int(x1 + (y2 - new_y1) * self.crop_aspect_ratio)
            else:
                new_y1 = max(0, min(y1 + img_dy, y2 - 10))
            self.crop_img_coords = (x1, new_y1, new_x2, y2)

        elif self.active_handle == "sw":
            new_x1 = max(0, min(x1 + img_dx, x2 - 10))
            if self.crop_aspect_ratio:
                new_h = int((x2 - new_x1) / self.crop_aspect_ratio)
                new_y2 = min(y1 + new_h, img_h)
                new_x1 = int(x2 - (new_y2 - y1) * self.crop_aspect_ratio)
            else:
                new_y2 = max(y1 + 10, min(y2 + img_dy, img_h))
            self.crop_img_coords = (new_x1, y1, x2, new_y2)

        elif self.active_handle == "e":
            new_x2 = max(x1 + 10, min(x2 + img_dx, img_w))
            if self.crop_aspect_ratio:
                new_h = int((new_x2 - x1) / self.crop_aspect_ratio)
                mid_y = (y1 + y2) // 2
                new_y1 = max(0, mid_y - new_h // 2)
                new_y2 = min(img_h, new_y1 + new_h)
                self.crop_img_coords = (x1, new_y1, new_x2, new_y2)
            else:
                self.crop_img_coords = (x1, y1, new_x2, y2)

        elif self.active_handle == "w":
            new_x1 = max(0, min(x1 + img_dx, x2 - 10))
            if self.crop_aspect_ratio:
                new_h = int((x2 - new_x1) / self.crop_aspect_ratio)
                mid_y = (y1 + y2) // 2
                new_y1 = max(0, mid_y - new_h // 2)
                new_y2 = min(img_h, new_y1 + new_h)
                self.crop_img_coords = (new_x1, new_y1, x2, new_y2)
            else:
                self.crop_img_coords = (new_x1, y1, x2, y2)

        elif self.active_handle == "s":
            new_y2 = max(y1 + 10, min(y2 + img_dy, img_h))
            if self.crop_aspect_ratio:
                new_w = int((new_y2 - y1) * self.crop_aspect_ratio)
                mid_x = (x1 + x2) // 2
                new_x1 = max(0, mid_x - new_w // 2)
                new_x2 = min(img_w, new_x1 + new_w)
                self.crop_img_coords = (new_x1, y1, new_x2, new_y2)
            else:
                self.crop_img_coords = (x1, y1, x2, new_y2)

        elif self.active_handle == "n":
            new_y1 = max(0, min(y1 + img_dy, y2 - 10))
            if self.crop_aspect_ratio:
                new_w = int((y2 - new_y1) * self.crop_aspect_ratio)
                mid_x = (x1 + x2) // 2
                new_x1 = max(0, mid_x - new_w // 2)
                new_x2 = min(img_w, new_x1 + new_w)
                self.crop_img_coords = (new_x1, new_y1, new_x2, y2)
            else:
                self.crop_img_coords = (x1, new_y1, x2, y2)

        self.drag_start_x = event.x
        self.drag_start_y = event.y

        if self.on_crop_changed:
            self.on_crop_changed(*self.crop_img_coords)

        self.redraw()

    def _on_mouse_up(self, event):
        self.active_handle = None
        self.is_panning = False

    def _on_pan_start(self, event):
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def _on_pan_drag(self, event):
        if not self.is_panning:
            return
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.offset_x += dx
        self.offset_y += dy
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.redraw()
