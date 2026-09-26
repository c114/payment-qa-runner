# Docs — UI Reference

`docs/screenshots/` holds **UI reference** screenshots (e.g. Preply.com layout pages).

- These images are **reference only** for Page Mapping / Workflow design.
- Live automation must target **admin-configured Sandbox / Staging / Internal QA** environments with a domain allowlist.
- Do **not** point the runner at Preply.com (or any production third-party site) for live payment testing.

Optional PNGs may be added under `screenshots/` (page-1.png …). The backend Dockerfile copies this tree into the image so a fresh clone always has at least this README.
