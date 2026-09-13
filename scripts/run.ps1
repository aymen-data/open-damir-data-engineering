param(
    [string[]]$Months = @('202501'),
    [string]$Python = 'python',
    [int]$BenchmarkRows = 1000000
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:POLARS_MAX_THREADS = '4'
& $Python -m damir.cli --root $projectRoot run --months @Months --benchmark-rows $BenchmarkRows
if ($LASTEXITCODE -ne 0) { throw "Échec du pipeline : code $LASTEXITCODE. Consulter logs/pipeline.log." }
