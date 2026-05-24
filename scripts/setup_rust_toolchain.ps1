Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Tool($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

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
  Write-Host "Temporarily added $cargoBin to PATH for this session."
}

if (-not (Test-Tool "rustup")) {
  if (Test-Tool "winget") {
    Write-Host "Installing rustup with winget..."
    winget install --id Rustlang.Rustup -e --accept-package-agreements --accept-source-agreements
  } else {
    throw "rustup is missing and winget is unavailable. Install rustup manually."
  }
}

Ensure-CargoBinInPath
if (-not (Test-Tool "rustup")) {
  throw "rustup is still unavailable in PATH. Open a new shell or add $env:USERPROFILE\.cargo\bin to PATH."
}

Write-Host "Installing stable Rust toolchain..."
rustup toolchain install stable
rustup default stable
rustup target add wasm32-unknown-unknown

if (-not (Test-Tool "cargo-contract")) {
  if (-not (Test-Tool "link")) {
    throw "MSVC linker (link.exe) not found. Install Visual Studio Build Tools with C++ build tools, then rerun this script."
  }
  Write-Host "Installing cargo-contract..."
  cargo install cargo-contract --locked
}

Write-Host "Rust toolchain ready."
