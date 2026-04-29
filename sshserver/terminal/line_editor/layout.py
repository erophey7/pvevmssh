# layout.py — backward compatibility redirect
from .display.builder import build_layout, build_screen, compute_completion_grid_dims
from .display.adapter import screen_to_layout

__all__ = [
    "build_layout",
    "build_screen",
    "compute_completion_grid_dims",
    "screen_to_layout",
]