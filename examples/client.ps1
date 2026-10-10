$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000'
$body = @{ query = 'sn56.11:1.1'; top_k = 5 } | ConvertTo-Json
$response = Invoke-RestMethod -Method Post -Uri "$base/v1/search" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
if ($response.results[0].segment_ids[0] -ne 'sn56.11:1.1') { throw 'Unexpected source segment' }
$response | ConvertTo-Json -Depth 10
