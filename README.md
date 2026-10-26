# 



## Layout

- `spec.md` — the frozen contract
- `paper/` — draft (.tex + .pdf), figures, and the claim map (datapoints + semantic map + two-way verifier)
- `experiments/` — frozen corpora, run logs, and the spine that recomputes every headline number
- `litreview/` — the layer systematic review
- code: see the prototype directory (`view-renderer/` or `prototype/`)

## Reproduce

Run the experiment spine in `experiments/` and the claim-map verifier in `paper/claim_map/` (or `paper/`). Every number in the paper is recomputed from frozen artifacts; a failed check blocks publication.

## Substrate

Qafiya spec v1.1 + hash-chained history v1.3: github.com/DeeWaanAI/qafiya (tag v0.2.0).

## License

AGPL-3.0 — see LICENSE.
