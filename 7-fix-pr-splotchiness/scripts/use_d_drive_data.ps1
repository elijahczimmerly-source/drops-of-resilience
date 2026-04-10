# Dot-source in PowerShell before long runs:  . .\use_d_drive_data.ps1
# Puts large test8 outputs + default memmap paths on D: (override with DROPS_LARGE_DATA_ROOT).

$ErrorActionPreference = "Stop"
$root = if ($env:DROPS_LARGE_DATA_ROOT) { $env:DROPS_LARGE_DATA_ROOT } else { "D:\drops-resilience-data" }
New-Item -ItemType Directory -Force -Path $root | Out-Null
$env:DROPS_LARGE_DATA_ROOT = $root

$env:DOR_TEST8_V2_PR_INTENSITY_ROOT = Join-Path $root "4-test8-v2-pr-intensity"
New-Item -ItemType Directory -Force -Path (Join-Path $env:DOR_TEST8_V2_PR_INTENSITY_ROOT "output") | Out-Null

# Same memmap the builder writes by default (use if you rebuilt on D:)
$cmip = Join-Path $root "ec_cmip6_build\cmip6_inputs_19810101-20141231.dat"
if (Test-Path $cmip) {
  $env:DOR_TEST8_CMIP6_HIST_DAT = $cmip
}

Write-Host "DROPS_LARGE_DATA_ROOT=$root"
Write-Host "DOR_TEST8_V2_PR_INTENSITY_ROOT=$($env:DOR_TEST8_V2_PR_INTENSITY_ROOT)"
if ($env:DOR_TEST8_CMIP6_HIST_DAT) {
  Write-Host "DOR_TEST8_CMIP6_HIST_DAT=$($env:DOR_TEST8_CMIP6_HIST_DAT)"
}
Write-Host 'Optional: set DOR_TEST8_GRIDMET_TARGETS_DAT and DOR_TEST8_GEO_MASK_NPY to UNC Regridded_Iowa paths.'
Write-Host 'Optional: TEST8_DETERMINISTIC=0 to skip Deterministic_V8_Hybrid_*.npz and save disk.'
