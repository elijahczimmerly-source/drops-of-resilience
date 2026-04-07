# Start Here — AI Agent Onboarding

Follow these steps in order before doing any work in this repository.

## Step 1: Read the core documents

Read these three files, in this order:

1. **`dor-info.md`** — Project overview, pipeline architecture, script inventory, data locations, research context, and findings to date. This is the most important file.
2. **`bhuwan-info.txt`** — Raw Teams conversation history with the supervisor (Bhuwan Shah). Gives you the decision-making context behind the pipeline: what was tried, what failed, what was confirmed, and what was deferred.
3. **`Priorities.txt`** — Current active priorities and open questions. This is what Elijah should be working on right now.

## Step 2: Explore the rest of the repository

Browse the remaining contents of `drops-of-resilience/` to fill in gaps — scripts, reports, logs, and data artifacts that the core documents reference. Pay attention to:

- `bilinear-vs-nn-regridding/` — completed comparison study (pipeline scripts, metric outputs, reports)
- `validate_tas_convergence/` — completed convergence check
- `chatSummaries/` — weekly summaries of prior agent conversations
- `week1/` — early-stage orientation materials
- `environment.yml` — conda environment spec

## Step 3: Explore the server

Browse `\\abe-cylo\modelsdev\Projects\WRC_DOR\` to understand the live data and script layout. Key areas:

- `Data/` — the reorganized data tree (Cropped_Iowa, Cropped_Colorado, Regridded_Iowa, Gridmet-CONUS, 100km-ScenarioMIP)
- `Spatial_Downscaling/Scripts/` — the canonical pipeline scripts (test8.py, regrid_to_gridmet.py, etc.)
- `Bias_Correction/` — BC analysis and plotting scripts

## Step 4: Update dor-info.md

Compare what you found on the server (Step 3) against what `dor-info.md` documents. If there are new scripts, renamed folders, new data directories, or other changes on the server that `dor-info.md` doesn't reflect, update it now. `dor-info.md` is the single source of truth for AI agents — keeping it current prevents future agents from working with stale information.

## Step 5: Resolve open questions

After completing steps 1–4, think about what you still don't understand or what seems inconsistent. Go back to the repository or server and look it up. The goal is to have a solid working understanding of the project before taking any action.
