"""Interpolate (T, y, x) stacks from Iowa GridMET 216×192 onto arbitrary lat/lon target meshes."""
from __future__ import annotations

import os

import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import map_coordinates


def _is_rectilinear_lat_lon_mesh(lat_s: np.ndarray, lon_s: np.ndarray) -> bool:
    """True if LAT,LON come from meshgrid(lat1d, lon1d, indexing='ij')."""
    lat_s = np.asarray(lat_s, dtype=np.float64)
    lon_s = np.asarray(lon_s, dtype=np.float64)
    if lat_s.ndim != 2 or lon_s.ndim != 2 or lat_s.shape != lon_s.shape:
        return False
    return bool(
        np.allclose(lat_s, lat_s[:, :1], rtol=1e-6, atol=1e-5)
        and np.allclose(lon_s, lon_s[:1, :], rtol=1e-6, atol=1e-5)
    )


def _align_rectilinear_values(
    lat_1d: np.ndarray,
    lon_1d: np.ndarray,
    val: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """GridMET meshgrid(ij): rows follow lat_1d, cols follow lon (360°). Return ascending axes + matching values."""
    la = np.asarray(lat_1d, dtype=np.float64)
    lo = (np.asarray(lon_1d, dtype=np.float64) + 360.0) % 360.0
    v = np.asarray(val, dtype=np.float64)
    if v.ndim != 2:
        raise ValueError("val must be 2D")
    if la[0] > la[-1]:
        la = la[::-1]
        v = v[::-1, :]
    if lo[0] > lo[-1]:
        lo = lo[::-1]
        v = v[:, ::-1]
    if not (np.all(np.diff(la) > 0) and np.all(np.diff(lo) > 0)):
        raise ValueError("lat/lon 1D axes must be strictly monotonic after orientation fix")
    return la, lo, v


def _frac_index_1d(axis_asc: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Fractional indices into a 1D ascending axis for bilinear (map_coordinates order=1)."""
    a = np.asarray(axis_asc, dtype=np.float64)
    x = np.asarray(q, dtype=np.float64)
    flat = x.ravel()
    idx = np.searchsorted(a, flat, side="right")
    idx = np.clip(idx, 1, len(a) - 1)
    t = (flat - a[idx - 1]) / (a[idx] - a[idx - 1] + 1e-30)
    frac = (idx - 1) + t
    return frac.reshape(x.shape)


def interp_gridmet_stack_to_target(
    arr_tyx: np.ndarray,
    lat_src_1d: np.ndarray,
    lon_src_1d: np.ndarray,
    lat_tgt_2d: np.ndarray,
    lon_tgt_2d: np.ndarray,
    *,
    time_chunk: int | None = None,
) -> np.ndarray:
    """
    Bilinear interpolation of a stack on the GridMET rectilinear (lat_1d × lon) mesh onto target (y', x').

    Uses scipy RegularGridInterpolator (avoids xarray interp API changes for 2D non-dimensional coords).
    """
    arr_tyx = np.asarray(arr_tyx, dtype=np.float32)
    nt = int(arr_tyx.shape[0])
    lat_1d = np.asarray(lat_src_1d, dtype=np.float64)
    lon_1d = np.asarray(lon_src_1d, dtype=np.float64)

    out = np.empty((nt,) + lat_tgt_2d.shape, dtype=np.float32)
    chunk = time_chunk or int(os.environ.get("DOR_INTERP_TIME_CHUNK", "48"))
    chunk = max(8, chunk)

    lon_tgt_q = (np.asarray(lon_tgt_2d, dtype=np.float64) + 360.0) % 360.0
    lat_tgt_q = np.asarray(lat_tgt_2d, dtype=np.float64)

    h, w = int(arr_tyx.shape[1]), int(arr_tyx.shape[2])
    la, lo, _ = _align_rectilinear_values(lat_1d, lon_1d, np.zeros((h, w), dtype=np.float64))
    fr = _frac_index_1d(la, lat_tgt_q)
    fc = _frac_index_1d(lo, lon_tgt_q)

    for t0 in range(0, nt, chunk):
        t1 = min(t0 + chunk, nt)
        for ti in range(t0, t1):
            _, _, v = _align_rectilinear_values(lat_1d, lon_1d, arr_tyx[ti])
            z = map_coordinates(
                v,
                [fr, fc],
                order=1,
                mode="constant",
                cval=np.nan,
                prefilter=False,
            )
            out[ti] = z.astype(np.float32, copy=False)

    return out


def interp_curvilinear_stack_to_target(
    arr_tyx: np.ndarray,
    lat_src_2d: np.ndarray,
    lon_src_2d: np.ndarray,
    lat_tgt_2d: np.ndarray,
    lon_tgt_2d: np.ndarray,
    *,
    time_chunk: int | None = None,
) -> np.ndarray:
    """
    Interpolate a stack on a source lat/lon mesh onto a target (y', x') lat/lon grid.

    LOCA2 / NEX Iowa crops are **rectilinear** (meshgrid of 1D lat/lon); use the same fast
    map_coordinates path as GridMET. Unstructured meshes fall back to scipy griddata (slow).
    """
    arr_tyx = np.asarray(arr_tyx, dtype=np.float32)
    LAT_S = np.asarray(lat_src_2d, dtype=np.float64)
    LON_S = np.asarray(lon_src_2d, dtype=np.float64)

    if _is_rectilinear_lat_lon_mesh(LAT_S, LON_S):
        lat_1d = LAT_S[:, 0]
        lon_1d = LON_S[0, :]
        return interp_gridmet_stack_to_target(
            arr_tyx,
            lat_1d,
            lon_1d,
            lat_tgt_2d,
            lon_tgt_2d,
            time_chunk=time_chunk,
        )

    LON_S = (LON_S + 360.0) % 360.0
    lon_tgt_q = (np.asarray(lon_tgt_2d, dtype=np.float64) + 360.0) % 360.0
    lat_tgt_q = np.asarray(lat_tgt_2d, dtype=np.float64)

    nt = int(arr_tyx.shape[0])
    points = np.column_stack([LAT_S.ravel(), LON_S.ravel()])
    xi = np.column_stack([lat_tgt_q.ravel(), lon_tgt_q.ravel()])
    out = np.empty((nt,) + lat_tgt_2d.shape, dtype=np.float32)
    chunk = time_chunk or int(os.environ.get("DOR_INTERP_TIME_CHUNK", "48"))
    chunk = max(8, chunk)

    for t0 in range(0, nt, chunk):
        t1 = min(t0 + chunk, nt)
        for ti in range(t0, t1):
            vals = np.asarray(arr_tyx[ti], dtype=np.float64).ravel()
            flat = griddata(points, vals, xi, method="linear", fill_value=np.nan)
            out[ti] = flat.reshape(lat_tgt_2d.shape).astype(np.float32, copy=False)

    return out


def interp_geo_mask_to_target(
    mask_hw: np.ndarray,
    lat_src_1d: np.ndarray,
    lon_src_1d: np.ndarray,
    lat_tgt_2d: np.ndarray,
    lon_tgt_2d: np.ndarray,
) -> np.ndarray:
    """Nearest-neighbor then threshold > 0.5 for boolean land mask on target grid."""
    m = np.asarray(mask_hw, dtype=np.float32)
    if m.ndim != 2:
        raise ValueError("mask_hw must be 2D")
    z = interp_gridmet_stack_to_target(
        m[np.newaxis, ...],
        lat_src_1d,
        lon_src_1d,
        lat_tgt_2d,
        lon_tgt_2d,
        time_chunk=1,
    )
    z0 = z[0]
    return (z0 > 0.5) & np.isfinite(z0)
