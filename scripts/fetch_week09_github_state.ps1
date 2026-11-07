param([string]$OutputPath = '')
$ErrorActionPreference = 'Stop'
if (-not $OutputPath) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $OutputPath = Join-Path $repoRoot ('reports/baseline/github_state_' + (Get-Date -Format 'yyyyMMdd') + '.json')
}
$headers = @{Accept='application/vnd.github+json'; 'User-Agent'='D1-baseline-audit'}
$apiRoot = 'https://api.github.com/repos/Loistarva/Vietnam-Legal-RAG-Assistant'
$pulls = Invoke-RestMethod -Uri "$apiRoot/pulls?state=all&per_page=100" -Headers $headers
$runs = Invoke-RestMethod -Uri "$apiRoot/actions/runs?per_page=100" -Headers $headers
$details = @()
foreach ($number in @(25,26,27,28,29,32)) {
    $pr = Invoke-RestMethod -Uri "$apiRoot/pulls/$number" -Headers $headers
    $details += $pr | Select-Object number,title,state,merged,merged_at,merge_commit_sha,mergeable_state,html_url,
        @{n='head_sha';e={$_.head.sha}},@{n='head_ref';e={$_.head.ref}},@{n='base_ref';e={$_.base.ref}}
}
$snapshot = @{
    observed_at = [DateTime]::UtcNow.ToString('o')
    source = $apiRoot
    details = $details
    pulls = @($pulls | Select-Object number,title,state,merged_at,html_url,
        @{n='head_sha';e={$_.head.sha}},@{n='head_ref';e={$_.head.ref}},@{n='base_ref';e={$_.base.ref}})
    workflow_runs = @($runs.workflow_runs | Select-Object id,run_number,name,event,status,conclusion,head_sha,head_branch,html_url,created_at,updated_at)
}
$outputDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))
[IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
[IO.File]::WriteAllText([IO.Path]::GetFullPath($OutputPath), ($snapshot | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
Write-Output $OutputPath
