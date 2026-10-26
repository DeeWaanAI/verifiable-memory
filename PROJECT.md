# DeeWaanAI OS — Master Project Instructions

**Read this first. It governs every layer, every agent, every paper.**

## What this project is

DeeWaanAI OS is a multi-year build toward a real AI operating system, delivered as a
series of layers — each layer is simultaneously **a software module** and **an
academic paper**. When all layers exist, they are combined onto a Linux distro to
form the AI OS.

Layer 1 (data substrate, **Qafiya**) is done: spec, engine, experiments, draft —
see `01-data-layer-qafiya/` and the code at github.com/DeeWaanAI/qafiya.

## Roles

- **Owner (Youssef Hariri)** — decides. No phase, publication, or external push
  happens without his explicit go.
- **Monitor agent** — keeps the whole picture: watches all layers, checks they obey
  these instructions, audits claims against frozen artifacts, flags drift.
- **Layer agents** — one agent (one chat) per layer folder. Each owns its layer's
  code + paper. Layer agents do not edit other layers' folders.

## The six layers

| # | Layer | Folder | Status |
|---|---|---|---|
| 1 | Data substrate (Qafiya) | `01-data-layer-qafiya/` | ✅ built; paper in revision |
| 2 | View renderer | `02-view-renderer/` | not started |
| 3 | Action layer | `03-action-layer/` | not started |
| 4 | Memory & continuity | `04-memory/` | not started |
| 5 | Model router | `05-model-router/` | not started |
| 6 | Shell / integration | `06-shell/` | design only until 2–4 exist |

## Non-negotiable rules for every layer

1. **Each layer is an academic paper project.** It must produce: a design brief, a
   formal spec, a running prototype, frozen reproducible experiments, and a paper
   draft — in that order. No paper claims without a frozen artifact behind them.
2. **The Qafiya discipline applies everywhere.** Every result, log, or claim a layer
   produces is a provenance-carrying record. Frozen data before runs; a spine script
   recomputes every headline number from raw artifacts; if the script fails, the
   number does not go in the paper. Negative and "uncatchable" results are reported
   as results, never hidden.
3. **Interfaces are contracts.** Layers integrate only through the frozen spec of
   the layers beneath them (starting with Qafiya spec v1.1). Never code against
   another layer's work-in-progress.
4. **Plain English, business-academic style** in all papers (HBR register: short
   direct sentences, no oral wording). Every experiment section carries concrete
   before/after examples so readers can see the system operating.
5. **Honesty as architecture.** Each paper must state what its system provably
   cannot do, measured where possible — the Qafiya paper's 0%-recall classes are
   the template.
6. **Attribution.** Author: Youssef Hariri. Product/brand: DeeWaanAI. Code under
   the DeeWaanAI GitHub org (AGPL-3.0). Artifact DOIs via the owner's Zenodo.
   Method lineage always cites the data-map paper (DOI placeholder until published).

## How a layer starts

1. Monitor + owner agree the layer opens (owner says go).
2. A layer agent gets: this file, its layer's `INSTRUCTIONS.md`, and the frozen
   specs of the layers it builds on.
3. The agent produces a design brief and **stops for owner confirmation** before
   building.

## How the monitor audits

- On request or at milestones: check that every number in a layer's paper traces to
  a frozen artifact; that claims match evidence; that interfaces still match the
  specs; and that this file's rules were followed. Report findings plainly.
