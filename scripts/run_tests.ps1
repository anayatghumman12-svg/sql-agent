# Sends every test question through the real API (not the agent function)
# and prints the full job result for each. The pause between questions keeps
# us inside the free-tier rate limit.
. "$PSScriptRoot\ask.ps1"

$questions = @(
  "What is the total revenue?",
  "How many orders were cancelled?",
  "How many customers have never placed an order?",
  "Which city has the most customers?",
  "What is the average order value?",
  "Which product category generated the most revenue?",
  "Who are the top 5 customers by total spend?",
  "What was the total revenue in 2025?",
  "What is the total amount of payments received for delivered orders?",
  "How many orders used a discount code?"
)

foreach ($q in $questions) {
  Write-Host "`n=== $q"
  Ask-AndWait $q
  Start-Sleep -Seconds 5
}