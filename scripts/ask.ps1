# Helper for manual testing: send a question, poll until it is no longer
# pending, and print the elapsed time plus the full job result.
function Ask-AndWait($q) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $body = @{ question = $q } | ConvertTo-Json
  $r = Invoke-RestMethod -Method Post -Uri http://localhost:8000/ask -ContentType "application/json" -Body $body
  $deadline = (Get-Date).AddSeconds(120)   # give up polling after 2 minutes
  do {
    $s = Invoke-RestMethod http://localhost:8000/status/$($r.job_id)
    if ($s.status -eq "pending") { Start-Sleep -Milliseconds 300 }
  } while ($s.status -eq "pending" -and (Get-Date) -lt $deadline)
  $sw.Stop()
  Write-Host ("{0} ms | status={1} | cached={2}" -f $sw.ElapsedMilliseconds, $s.status, $s.cached)
  $s | ConvertTo-Json
}