$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Download-File {
  param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$OutFile
  )

  $dir = Split-Path -Parent $OutFile
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }

  Write-Host "Downloading:" $Url
  Invoke-WebRequest -Uri $Url -OutFile $OutFile
  Write-Host "Saved:" $OutFile
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$vendorRoot = Join-Path $repoRoot "frontend\\ui\\vendor"

# PDF.js (pinned). Use a UMD build that works with classic <script> tags.
Download-File `
  -Url "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js" `
  -OutFile (Join-Path $vendorRoot "pdfjs\\pdf.min.js")

Download-File `
  -Url "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js" `
  -OutFile (Join-Path $vendorRoot "pdfjs\\pdf.worker.min.js")

# PDF-Lib (pinned)
Download-File `
  -Url "https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js" `
  -OutFile (Join-Path $vendorRoot "pdf-lib\\pdf-lib.min.js")

Write-Host ""
Write-Host "Done."
Write-Host "Now open the UI from FastAPI (recommended):"
Write-Host "  http://127.0.0.1:8000/ui/student/order.html?shop_id=1"
