param(
    [string]$Region = "us-east-1",
    [string]$ClusterName = "event-ticketing",
    [string]$ImagePrefix = "078682762568.dkr.ecr.us-east-1.amazonaws.com/event-ticketing",
    [string]$ImageTag = "main"
)
Write-Host "=== Pre-flight checks ===" -ForegroundColor Cyan
if (!(Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker not found" }
if (!(Get-Command kubectl -ErrorAction SilentlyContinue)) { throw "kubectl not found" }
if (!(Get-Command aws -ErrorAction SilentlyContinue)) { throw "AWS CLI not found" }
$apiTag = "${ImagePrefix}-api:${ImageTag}"
$webTag = "${ImagePrefix}-web:${ImageTag}"
Write-Host "=== Authenticating to ECR ===" -ForegroundColor Cyan
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $( $ImagePrefix -replace '/event-ticketing.*$', '' )
if ($LASTEXITCODE -ne 0) { throw "ECR login failed" }
Write-Host "=== Building Docker images ===" -ForegroundColor Cyan
$repoRoot = Resolve-Path "$PSScriptRoot/.."
Write-Host "  Building API image..." -ForegroundColor Gray
docker build -t $apiTag --target api -f "$repoRoot/Dockerfile" $repoRoot
if ($LASTEXITCODE -ne 0) { throw "Docker build (api) failed" }
$stripeKey = $env:VITE_STRIPE_PUBLISHABLE_KEY
if ([string]::IsNullOrEmpty($stripeKey) -and (Test-Path "$repoRoot/apps/web/.env")) {
    $envLines = Get-Content "$repoRoot/apps/web/.env"
    foreach ($line in $envLines) {
        if ($line -match '^VITE_STRIPE_PUBLISHABLE_KEY=(.+)$') {
            $stripeKey = $Matches[1].Trim()
            break
        }
    }
}
if ([string]::IsNullOrEmpty($stripeKey)) {
    try {
        $ssmVal = aws ssm get-parameter --name "/event-ticketing/VITE_STRIPE_PUBLISHABLE_KEY" --query "Parameter.Value" --output text 2>$null
        if ($ssmVal -and $ssmVal -ne "None") { $stripeKey = $ssmVal }
    } catch {}
}
if ([string]::IsNullOrEmpty($stripeKey)) {
    Write-Warning "VITE_STRIPE_PUBLISHABLE_KEY not set - Stripe will be unavailable"
    docker build -t $webTag --target web -f "$repoRoot/Dockerfile" $repoRoot
} else {
    Write-Host "  Injecting VITE_STRIPE_PUBLISHABLE_KEY into web build..." -ForegroundColor Cyan
    docker build -t $webTag --target web --build-arg VITE_STRIPE_PUBLISHABLE_KEY=$stripeKey -f "$repoRoot/Dockerfile" $repoRoot
}
if ($LASTEXITCODE -ne 0) { throw "Docker build (web) failed" }
Write-Host "=== Pushing images to ECR ===" -ForegroundColor Cyan
Write-Host "  Pushing API image..." -ForegroundColor Gray
docker push $apiTag
if ($LASTEXITCODE -ne 0) { throw "Docker push (api) failed" }
Write-Host "  Pushing Web image..." -ForegroundColor Gray
docker push $webTag
if ($LASTEXITCODE -ne 0) { throw "Docker push (web) failed" }
Write-Host "=== Updating kubeconfig ===" -ForegroundColor Cyan
aws eks update-kubeconfig --name $ClusterName --region $Region
if ($LASTEXITCODE -ne 0) { throw "kubeconfig update failed" }
Write-Host "=== Applying Kustomize overlay ===" -ForegroundColor Cyan
$kustomizeDir = "$repoRoot/k8s/prod/"
kubectl apply -k $kustomizeDir
if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed" }
Write-Host "=== Restarting deployments to pick up new images ===" -ForegroundColor Cyan
kubectl -n event-ticketing rollout restart deployment/gateway-api
kubectl -n event-ticketing rollout restart deployment/gateway-web
kubectl -n event-ticketing rollout restart deployment/sweeper
kubectl -n event-ticketing rollout restart deployment/relay
kubectl -n event-ticketing rollout restart deployment/admitter
Write-Host "=== Waiting for rollout to complete ===" -ForegroundColor Cyan
kubectl -n event-ticketing rollout status deployment/gateway-api --timeout=180s
kubectl -n event-ticketing rollout status deployment/gateway-web --timeout=180s
kubectl -n event-ticketing rollout status deployment/sweeper --timeout=60s
kubectl -n event-ticketing rollout status deployment/relay --timeout=60s
kubectl -n event-ticketing rollout status deployment/admitter --timeout=60s
Write-Host "=== Deployment Complete! ===" -ForegroundColor Green
Start-Sleep -Seconds 10
$ingress = kubectl -n event-ticketing get ingress/gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>$null
if ($ingress -and $ingress -ne "") {
    Write-Host ""
    Write-Host "ALB DNS: http://${ingress}" -ForegroundColor Green
    Write-Host "Health check: http://${ingress}/health" -ForegroundColor Green
}
Write-Host ""
Write-Host "To monitor pods: kubectl get pods -n event-ticketing -w" -ForegroundColor Gray
Write-Host "To view logs:    kubectl logs -n event-ticketing deployment/gateway-api -f" -ForegroundColor Gray
Write-Host "To view web:     kubectl logs -n event-ticketing deployment/gateway-web -f" -ForegroundColor Gray
