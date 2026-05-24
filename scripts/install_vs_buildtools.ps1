param(
  [switch]$ForceInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Tool($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Resolve-VsWherePath {
  $candidate = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  if (Test-Path $candidate) {
    return $candidate
  }
  return $null
}

function Resolve-MsvcBinPath {
  $vswhere = Resolve-VsWherePath
  if (-not $vswhere) {
    return $null
  }

  $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
  if (-not $installPath) {
    return $null
  }

  $toolsRoot = Join-Path $installPath "VC\Tools\MSVC"
  if (-not (Test-Path $toolsRoot)) {
    return $null
  }

  $versionDir = Get-ChildItem $toolsRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
  if (-not $versionDir) {
    return $null
  }

  $binPath = Join-Path $versionDir.FullName "bin\Hostx64\x64"
  if (-not (Test-Path $binPath)) {
    return $null
  }
  return $binPath
}

function Ensure-PathItem($pathItem) {
  if (-not $pathItem) {
    return
  }
  $pathItems = $env:PATH -split ";" | Where-Object { $_ -and $_.Trim() -ne "" }
  if ($pathItems -contains $pathItem) {
    return
  }
  $env:PATH = "$pathItem;$env:PATH"
  Write-Host "Temporarily added $pathItem to PATH for this session."
}

if ((Test-Tool "link") -and -not $ForceInstall) {
  $linkPath = (Get-Command link).Path
  Write-Host "MSVC linker already available at $linkPath"
  exit 0
}

if (-not (Test-Tool "winget")) {
  throw "winget is required to install Visual Studio Build Tools."
}

$overrideArgs = "--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --includeRecommended"
$packageIds = @(
  "Microsoft.VisualStudio.2022.BuildTools",
  "Microsoft.VisualStudio.BuildTools"
)

$installed = $false
foreach ($packageId in $packageIds) {
  Write-Host "Attempting Build Tools install via winget package: $packageId"
  try {
    winget install --id $packageId -e --accept-package-agreements --accept-source-agreements --override $overrideArgs
    $rawExitCode = [int]$LASTEXITCODE
    $normalizedExitCode = if ($rawExitCode -lt 0) { $rawExitCode + 4294967296 } else { $rawExitCode }
    if ($normalizedExitCode -eq 0) {
      $installed = $true
      break
    }
    Write-Warning "Install attempt failed for ${packageId} with exit code ${normalizedExitCode}."
  } catch {
    Write-Warning "Install attempt failed for ${packageId}: $($_.Exception.Message)"
  }
}

if (-not $installed) {
  throw "Failed to install Visual Studio Build Tools with winget. Check installer output for failure details."
}

$msvcBinPath = Resolve-MsvcBinPath
Ensure-PathItem $msvcBinPath

if (-not (Test-Tool "link")) {
  throw "MSVC linker (link.exe) is still unavailable after Build Tools install."
}

$resolvedLink = (Get-Command link).Path
Write-Host "MSVC linker ready at $resolvedLink"
