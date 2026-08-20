"""
Theme styling tokens and colors for CustomTkinter UI.
Supports dynamic Light and Dark mode using (light_color, dark_color) tuples.
"""
from typing import Tuple, Union
import customtkinter as ctk

# Color definitions: (Light Mode, Dark Mode)
COLORS = {
    "bg_dark": ("#f1f5f9", "#121418"),
    "sidebar_bg": ("#e2e8f0", "#1a1d24"),
    "card_bg": ("#ffffff", "#222732"),
    "card_border": ("#cbd5e1", "#2d3342"),
    "accent_primary": ("#2563eb", "#3b82f6"),    # Vibrant Blue
    "accent_hover": ("#1d4ed8", "#2563eb"),
    "accent_success": ("#059669", "#10b981"),    # Emerald Green
    "accent_warning": ("#d97706", "#f59e0b"),    # Amber
    "accent_danger": ("#dc2626", "#ef4444"),     # Red
    "accent_purple": ("#7c3aed", "#8b5cf6"),     # Indigo/Purple
    "text_primary": ("#0f172a", "#f8fafc"),
    "text_secondary": ("#475569", "#94a3b8"),
    "text_muted": ("#64748b", "#64748b"),
    "crop_handle": ("#0284c7", "#38bdf8"),
    "crop_box_border": ("#0284c7", "#00e5ff"),
    "canvas_bg": ("#e2e8f0", "#0f1115"),
}

FONTS = {
    "title": ("SF Pro Display", 16, "bold"),
    "subtitle": ("SF Pro Display", 13, "bold"),
    "body_bold": ("SF Pro Text", 12, "bold"),
    "body": ("SF Pro Text", 12),
    "small": ("SF Pro Text", 11),
    "mono": ("Menlo", 11),
    "badge": ("SF Pro Text", 10, "bold"),
}


def get_color(color_key: str) -> str:
    """Helper to return a single hex color string for Tkinter Canvas based on CTk appearance mode."""
    val = COLORS.get(color_key, "#ffffff")
    if isinstance(val, tuple):
        mode = ctk.get_appearance_mode().lower()
        return val[0] if mode == "light" else val[1]
    return str(val)
