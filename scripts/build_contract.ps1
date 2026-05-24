Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$contractDir = Join-Path $repoRoot "contracts\identity-workflow-registry"
$outPath = Join-Path $contractDir "metadata.json"

function Ensure-CargoBinInPath {
  $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
  if (-not (Test-Path $cargoBin)) {
    return
  }
  $pathItems = $env:PATH -split ";" | Where-Object { $_ -and $_.Trim() -ne "" }
  if ($pathItems -contains $cargoBin) {
    return
  }
  $env:PATH = "$cargoBin;$env:PATH"
}

Ensure-CargoBinInPath

if (-not (Test-Path $contractDir)) {
  throw "Contract directory not found: $contractDir"
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  throw "cargo is not installed. Run scripts/setup_rust_toolchain.ps1 first."
}
if (-not (Get-Command cargo-contract -ErrorAction SilentlyContinue)) {
  throw "cargo-contract is not installed. Run scripts/setup_rust_toolchain.ps1 first."
}

Push-Location $contractDir
try {
  cargo contract build --release
} finally {
  Pop-Location
}

$inkDir = Join-Path $contractDir "target\ink"
if (-not (Test-Path $inkDir)) {
  throw "Expected build output folder not found: $inkDir"
}

$metadataCandidate = Get-ChildItem $inkDir -Filter "*.json" |
  Where-Object { $_.Name -notlike "*.contract" } |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $metadataCandidate) {
  throw "No metadata JSON found in $inkDir"
}

Copy-Item -LiteralPath $metadataCandidate.FullName -Destination $outPath -Force
if (-not (Test-Path $outPath)) {
  throw "Contract metadata copy failed: $outPath"
}
Write-Host "Contract metadata copied to $outPath"

