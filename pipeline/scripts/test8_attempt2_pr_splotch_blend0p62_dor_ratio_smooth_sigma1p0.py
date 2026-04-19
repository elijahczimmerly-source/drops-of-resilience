"""
Archived one-off experiment (not part of the production downscaling line).

**Change vs test8 v4:** ``PR_INTENSITY_BLEND=0.62`` (v4 default 0.65), ``DOR_RATIO_SMOOTH_SIGMA=1.0``
(Gaussian smooth on calibrated spatial ratios). **WDF** default **1.65** (same as v4).

**Outcome:** Multipanel **pr** maps looked **indistinguishable** from v4 in human review; numeric
differences were tiny. See ``9-fix-pr-splotchiness-attempt-2/`` (FINDINGS, NEGATIVE_RESULT_ATTEMPT2.md).

``DOR_PIPELINE_ID`` is ``test8_pr_tex_att2_b062_rs1`` (distinct ``pipeline/output/...`` tree).
"""
from __future__ import annotations

import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["DOR_PIPELINE_ID"] = "test8_pr_tex_att2_b062_rs1"
os.environ.setdefault("PR_USE_INTENSITY_RATIO", "1")
os.environ.setdefault("PR_INTENSITY_BLEND", "0.62")
os.environ.setdefault("DOR_RATIO_SMOOTH_SIGMA", "1.0")
os.environ.setdefault("PR_INTENSITY_OUT_TAG", "blend0p62_ratio_smooth1p0")

_d_cache = os.environ.get("DOR_LOCAL_WRC_CACHE", r"D:\drops-resilience-data\WRC_DOR_cache")
_regridded = os.path.join(_d_cache, "Spatial_Downscaling", "test8_v2", "Regridded_Iowa")
_mv_otbc = os.path.join(_regridded, "MPI", "mv_otbc")
if os.path.isdir(_mv_otbc):
    os.environ.setdefault("DOR_TEST8_PR_DATA_DIR", _mv_otbc)
    os.environ.setdefault(
        "DOR_TEST8_GRIDMET_TARGETS_DAT",
        os.path.join(_regridded, "gridmet_targets_19810101-20141231.dat"),
    )
    os.environ.setdefault("DOR_TEST8_GEO_MASK_NPY", os.path.join(_regridded, "geo_mask.npy"))

runpy.run_path(os.path.join(_HERE, "_test8_sd_impl.py"), run_name="__main__")
