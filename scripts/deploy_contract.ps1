param(
  [string]$WsUrl = $env:PORTALDOT_WS,
  [string]$SignerUri = $env:DEMO_SIGNER_URI,
  [string]$Constructor = "new",
  [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Parse-InstantiationOutput {
  param([string]$Text)

  $contractAddress = $null
  $codeHash = $null
  $deployTxHash = $null

  foreach ($line in ($Text -split "`r?`n")) {
    if (-not $contractAddress -and $line -match "\b5[1-9A-HJ-NP-Za-km-z]{46,60}\b") {
      $contractAddress = $Matches[0]
    }
    if (-not $codeHash -and $line -match "(?i)code\s*hash[^\n]*?(0x[a-fA-F0-9]{64})") {
      $codeHash = $Matches[1]
    }
    if (-not $deployTxHash -and $line -match "(?i)(extrinsic|transaction)\s*hash[^\n]*?(0x[a-fA-F0-9]{64})") {
      $deployTxHash = $Matches[2]
    }
  }

  return @{
    contract_address = $contractAddress
    code_hash = $codeHash
    deploy_tx_hash = $deployTxHash
  }
}

Ensure-CargoBinInPath

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$contractDir = Join-Path $repoRoot "contracts\identity-workflow-registry"
$manifestPath = Join-Path $contractDir "Cargo.toml"
$buildScript = Join-Path $PSScriptRoot "build_contract.ps1"

if (-not $WsUrl) {
  throw "PORTALDOT_WS is required. Set env var or pass -WsUrl."
}
if (-not $SignerUri) {
  throw "DEMO_SIGNER_URI is required. Set env var or pass -SignerUri."
}
if (-not (Test-Path $buildScript)) {
  throw "Build script not found: $buildScript"
}

if (-not $OutputPath) {
  $OutputPath = Join-Path $repoRoot "data\deploy-contract.latest.json"
}

& $buildScript

$helpOutput = (& cargo contract instantiate --help 2>&1 | Out-String)
$supportsExecuteFlag = $helpOutput -match "--execute" -or $helpOutput -match "\s-x\b"
$supportsOutputJson = $helpOutput -match "--output-json"

$cmdArgs = @(
  "contract",
  "instantiate",
  "--manifest-path", $manifestPath,
  "--constructor", $Constructor,
  "--url", $WsUrl,
  "--suri", $SignerUri,
  "--skip-confirm"
)

if ($supportsExecuteFlag) {
  $cmdArgs += "--execute"
}
if ($supportsOutputJson) {
  $cmdArgs += "--output-json"
}

Write-Host "Deploying contract via cargo-contract instantiate..."
$outputLines = & cargo @cmdArgs 2>&1
$exitCode = $LASTEXITCODE
$deployOutput = ($outputLines | Out-String).Trim()

if (-not $deployOutput) {
  throw "No output returned from contract instantiation."
}

$parsed = Parse-InstantiationOutput -Text $deployOutput
$metadataPath = Join-Path $contractDir "metadata.json"

$result = [ordered]@{
  ok = [bool]$parsed.contract_address -and $exitCode -eq 0
  ws_url = $WsUrl
  signer_uri = $SignerUri
  constructor = $Constructor
  manifest_path = $manifestPath
  metadata_path = $metadataPath
  contract_address = $parsed.contract_address
  code_hash = $parsed.code_hash
  deploy_tx_hash = $parsed.deploy_tx_hash
  timestamp_utc = [DateTime]::UtcNow.ToString("o")
  command = "cargo " + ($cmdArgs -join " ")
  raw_output = $deployOutput
}

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir -and -not (Test-Path $outputDir)) {
  New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

if ($exitCode -ne 0) {
  throw "Contract instantiation failed with exit code $exitCode. Details saved to $OutputPath"
}
if (-not $result.ok) {
  throw "Could not parse deployed contract address. Check output in $OutputPath"
}

Write-Host "Deployed contract address: $($result.contract_address)"
if ($result.code_hash) {
  Write-Host "Code hash: $($result.code_hash)"
}
if ($result.deploy_tx_hash) {
  Write-Host "Deploy tx hash: $($result.deploy_tx_hash)"
}
Write-Host "Wrote deployment details to $OutputPath"
Write-Host "Set CONTRACT_ADDRESS=$($result.contract_address) and CONTRACT_METADATA_PATH=$metadataPath for substrate mode."
