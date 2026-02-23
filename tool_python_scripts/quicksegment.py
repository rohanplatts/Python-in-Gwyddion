# -*- coding: utf-8 -*-
"""
Created on Mon Aug 11 20:28:24 2025

@author: rnpla
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from numpy.typing import NDArray
from PIL import Image
from scipy.ndimage import gaussian_filter
from skimage.filters import sobel
from skimage.measure import regionprops
from skimage.restoration import denoise_tv_chambolle
from skimage.segmentation import watershed
from sklearn.linear_model import LinearRegression


# ════════════ GENERAL PARAMETERS ════════════ 

# Output mode:
# True  -> write segmentation labels (float64) to out.npy
# False -> write terrace-flattened image (float64) to out.npy
output_segmentation_preview: bool = False

# Optional: save a colored PNG preview of the segmentation.
# Set to None to disable file writing.
preview_output_dir: Path | None = None

percentile = [1, 99]
percentile_plane = np.array([1, 99])  # outlier trimming for plane fitting

# ════════════ Anisotropic Diffusion filter (ADF) parameters
adf_weight: float = 0.25  # smoothness; larger -> stronger smoothing for easier watershed
adf_iterations: int = 500  # iterations for Chambolle TV denoise
adf_eps: float = 2.0e-5  # convergence tolerance for Chambolle algorithm


# ════════════ Gaussian filter parameters
gaussian_sigma: float | int = 4  # default = 4 pixels
gaussian_order: int = 0  # 0 = smoothing; 1 = 1st derivative. Useful to increase contrast
gaussian_mode: str = "reflect"  # padding mode

# ════════════ Watershed parameters
compactness_watershed: float = 0  # compactness penalty
watershed_line_bool: bool = False  # draw 1-px lines between segments if True


# ════════════ UTILITY FUNCTIONS ════════════

def connectivity(number: int) -> NDArray[np.bool_]:
    """
    Return a boolean structuring element (connectivity kernel) for watershed.
    """
    if number == 1:
        struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
        return struct
    if number == 2:
        struct = np.ones((3, 3), dtype=bool)
        return struct
    if number == 3:
        struct = np.array(
            [
                [0, 0, 1, 0, 0],
                [0, 1, 1, 1, 0],
                [1, 1, 1, 1, 1],
                [0, 1, 1, 1, 0],
                [0, 0, 1, 0, 0],
            ],
            dtype=bool,
        )
        return struct
    if number == 4:
        struct = np.array(
            [
                [0, 1, 1, 1, 0],
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [0, 1, 1, 1, 0],
            ],
            dtype=bool,
        )
        return struct
    if number == 5:
        struct = np.ones((3, 3), dtype=bool)
        return struct
    raise ValueError('Value error for function "connectivity", must be an integer in [1,5]')


def get_manual_markers(img: NDArray[np.uint8], num_points: int | None = None) -> NDArray[np.int_]:
    """
    Collect manual seed points from a displayed image.

    Returns array of shape (N, 2) with (row, col) integer coordinates.
    """
    matplotlib.use("TkAgg", force=True)

    fig = plt.figure()
    plt.imshow(img, cmap="gray")
    plt.title("Click to select markers, press Enter when done.")
    points = plt.ginput(n=num_points, timeout=0)
    plt.close(fig)

    # Convert (x, y) -> (row, col) == (y, x)
    return np.array([[int(y), int(x)] for (x, y) in points], dtype=int)


def reorder_labels_area(labels: NDArray[np.int_]) -> NDArray[np.int_]:
    """
    Relabel connected components by ascending area (1..K), keeping 0 as background.
    """
    new_labels = np.zeros_like(labels, dtype=np.int32)
    regions = sorted([r for r in regionprops(labels) if r.label != 0], key=lambda r: r.area)
    for new_label, region in enumerate(regions, start=1):
        coords = region.coords
        new_labels[coords[:, 0], coords[:, 1]] = new_label
    return new_labels


def equalise(data: NDArray[np.floating]) -> NDArray[np.floating]:
    """
    Shift the array so the minimum value becomes 0.
    """
    return data - np.min(data)


def plane_fit_segment(segment_array: NDArray[np.floating]) -> Tuple[NDArray[np.float64], LinearRegression]:
    """
    Fit a plane z = ax + by + c to valid pixels (!= -1) with percentile trimming.
    """
    valid_mask = segment_array != -1
    low, high = np.percentile(segment_array[valid_mask], percentile_plane)
    valid_mask_model = (segment_array != -1) & (segment_array <= high) & (segment_array >= low)

    y_model, x_model = np.where(valid_mask_model)
    z_model = segment_array[valid_mask_model]
    X_model = np.vstack((x_model, y_model)).T

    y, x = np.where(valid_mask)
    X = np.vstack((x, y)).T

    model = LinearRegression()
    model.fit(X_model, z_model)

    fitted_plane = np.full_like(segment_array, -1, dtype=np.float64)
    fitted_plane[valid_mask] = model.predict(X)
    return fitted_plane, model


def calculate_plane_angle_with_horizontal(model: LinearRegression, segment_array: NDArray[np.floating]) -> float:
    """
    Compute the tilt angle of the fitted plane relative to the XY plane (radians).
    """
    if len(model.coef_) < 2:
        return 0.0
    if len(model.coef_) == 2:
        m_x = float(model.coef_[0])
        m_y = float(model.coef_[1])
        steepness = np.sqrt(m_x**2 + m_y**2)
        angle_radians = float(np.arctan(steepness))
        return angle_radians
    return 0.0


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """
    Convert HSV (0-1 floats) to RGB (0-255 ints).
    """
    h_i = int(h * 6)
    f = h * 6 - h_i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    if h_i == 0:
        r, g, b = v, t, p
    elif h_i == 1:
        r, g, b = q, v, p
    elif h_i == 2:
        r, g, b = p, v, t
    elif h_i == 3:
        r, g, b = p, q, v
    elif h_i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


def generate_distinct_colors(n: int) -> NDArray[np.uint8]:
    """
    Generate n visually distinct RGB colors (first = black for background).
    """
    colors = np.zeros((n, 3), dtype=np.uint8)
    colors[0] = [0, 0, 0]
    for i in range(1, n):
        hue = i / (n - 1)
        sat = 0.85
        val = 0.95
        colors[i] = hsv_to_rgb(hue, sat, val)
    return colors


def labels_to_rgb(labels: NDArray[np.int_]) -> NDArray[np.uint8]:
    """
    Map integer labels to an RGB image.
    """
    max_label = int(labels.max())
    color_table = generate_distinct_colors(max_label + 1)
    return color_table[labels]


def normalize_to_uint8(img: NDArray[np.floating]) -> NDArray[np.uint8]:
    """
    Percentile clip and scale image to uint8 for display.
    """
    minp_val = float(np.percentile(img, percentile[0]))
    maxp_val = float(np.percentile(img, percentile[1]))
    img_clip = np.clip(img, minp_val, maxp_val)
    denom = img_clip.max() - img_clip.min()
    if denom == 0:
        return np.zeros_like(img_clip, dtype=np.uint8)
    return ((img_clip - img_clip.min()) / denom * 255).astype(np.uint8)


def flatten_by_labels(img: NDArray[np.floating], labels: NDArray[np.int_]) -> NDArray[np.float64]:
    """
    Fit a plane per label and subtract it, returning a terrace-flattened image.
    """
    flattened = img.astype(np.float64, copy=True)
    for label_id in np.unique(labels):
        if label_id == 0:
            continue
        mask = labels == label_id
        if not np.any(mask):
            continue
        segment = np.full_like(img, -1.0, dtype=np.float64)
        segment[mask] = img[mask]
        plane, _ = plane_fit_segment(segment)
        flattened[mask] = img[mask] - plane[mask]
    return flattened


# ════════════ EXECUTIVE FUNCTION ════════════

def seg(img_read: NDArray[np.floating]) -> Tuple[NDArray[np.float64], NDArray[np.int_], NDArray[np.uint8]]:
    """
    Segment terraces in an image via TV denoising, Gaussian smoothing,
    Sobel gradients, and watershed.
    """
    # do an initial global plane fit.
    plane, model = plane_fit_segment(img_read)

    # correct the plane fit heights
    angle = calculate_plane_angle_with_horizontal(model, img_read)
    img_flat: NDArray[np.floating] = (img_read - plane) * np.cos(angle)

    img = equalise(img_flat)

    # ADF filtering
    draft_img: NDArray[np.floating] = denoise_tv_chambolle(
        img,
        eps=adf_eps,
        weight=adf_weight,
        max_num_iter=adf_iterations,
    )

    # Gaussian smoothing
    draft_img_gaus: NDArray[np.floating] = gaussian_filter(
        draft_img,
        sigma=gaussian_sigma,
        order=gaussian_order,
        mode=gaussian_mode,
        cval=0.05,
        axes=[1],
    )

    # gradient image of the gaussian smoothed, ADF, image
    gradient2: NDArray[np.floating] = sobel(draft_img_gaus)

    # create png (percentile clip -> [0,255] uint8)
    img_png_norm = normalize_to_uint8(img)
    img_png_rgb = np.repeat(img_png_norm[:, :, None], 3, axis=2)

    # Use the PNG as the display for the user to input markers
    peak_markers = get_manual_markers(img_png_rgb)
    markers = np.zeros_like(img, dtype=np.int32)
    if peak_markers.size > 0:
        markers[tuple(peak_markers.T)] = np.arange(1, len(peak_markers) + 1)
    else:
        return img.astype(np.float64), np.zeros_like(img, dtype=np.int32), img_png_rgb

    # these markers are the seed points for watershed to work.
    labels = watershed(
        gradient2,
        markers=markers,
        connectivity=connectivity(1),
        compactness=compactness_watershed,
        watershed_line=watershed_line_bool,
    )

    # relabel by area
    labels = reorder_labels_area(labels)

    rgb_image = labels_to_rgb(labels)
    return img.astype(np.float64), labels.astype(np.int32), rgb_image


def process(img: NDArray[np.floating]) -> NDArray[np.float64]:
    """
    Entry point for the Gwyddion Python bridge.
    """
    img_base, labels, rgb = seg(img)

    if preview_output_dir is not None:
        preview_output_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_output_dir / "quicksegment_labels.png"
        Image.fromarray(rgb).save(preview_path)
        combined = np.hstack((rgb, np.repeat(normalize_to_uint8(img_base)[:, :, None], 3, axis=2)))
        combined_path = preview_output_dir / "quicksegment_labels_with_original.png"
        Image.fromarray(combined).save(combined_path)

    if output_segmentation_preview:
        return labels.astype(np.float64)
    return flatten_by_labels(img_base, labels)


def main() -> int:
    if len(sys.argv) < 3:
        return 2
    inpath, outpath = sys.argv[1], sys.argv[2]
    img = np.load(inpath)
    out = process(img)
    np.save(outpath, out.astype(np.float64))
    return 0


if __name__ == "__main__":
    sys.exit(main())
