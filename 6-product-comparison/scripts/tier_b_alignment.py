"""Tier B: bilinear upsample coarse Δ maps to GridMET 216×192 for comparison to S3 (plan grid alignment)."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import zoom


def upsample_coarse_delta_bilinear(delta_coarse: np.ndarray, h_tgt: int, w_tgt: int) -> np.ndarray:
    """Resize coarse (Hc,Wc) field to (h_tgt,w_tgt) with bilinear interpolation (order=1)."""
    arr = np.asarray(delta_coarse, dtype=np.float64)
    hc, wc = arr.shape
    if hc < 1 or wc < 1:
        raise ValueError("empty coarse grid")
    zf = (h_tgt / hc, w_tgt / wc)
    clean = np.where(np.isfinite(arr), arr, np.nanmedian(arr) if np.any(np.isfinite(arr)) else 0.0)
    out = zoom(np.nan_to_num(clean, nan=0.0), zf, order=1)
    oh, ow = int(out.shape[0]), int(out.shape[1])
    if oh != h_tgt or ow != w_tgt:
        tmp = np.full((h_tgt, w_tgt), np.nan, dtype=np.float64)
        tmp[: min(oh, h_tgt), : min(ow, w_tgt)] = out[: min(oh, h_tgt), : min(ow, w_tgt)]
        out = tmp
    return out.astype(np.float64, copy=False)
