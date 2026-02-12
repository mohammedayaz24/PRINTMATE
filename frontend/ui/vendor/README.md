# Vendor libraries (PDF.js / PDF-Lib)

Some browsers/extensions block third‑party CDN scripts (often shown as “Tracking Prevention …”), which breaks PDF.js and therefore:

- Page preview rendering
- Black & White (grayscale) conversion

This project uses self‑hosted vendor files to avoid that.

## Install vendor files

Run:

```powershell
pwsh -File PRINTMATE/scripts/vendor-download.ps1
```

This downloads:

- `frontend/ui/vendor/pdfjs/pdf.min.js`
- `frontend/ui/vendor/pdfjs/pdf.worker.min.js`
- `frontend/ui/vendor/pdf-lib/pdf-lib.min.js`

Note: PDF.js is downloaded as a classic (non-ESM) build so it works with normal `<script>` tags.

## Recommended way to open the UI

Serve the UI from FastAPI and open:

`http://127.0.0.1:8000/ui/student/order.html?shop_id=1`
