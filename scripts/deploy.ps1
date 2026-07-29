#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the event-ticketing application to EKS.
    Builds both Docker images (api + web), pushes to GHCR, and applies prod Kustomize overlay.
.PARAMETER Region
    AWS region (default: us-east-1)
.PARAMETER ClusterName
    EKS cluster name (default: event-ticketing)
.PARAMETER ImagePrefix
    GHCR image prefix (default: ghcr.io/nilpc/event-ticketing)
.PARAMETER ImageTag
    Docker image tag (default: main)
#>

param(
    [string]$Region = "us-east-1",
    [string]$ClusterName = "event-ticketing",
    [string]$ImagePrefix = "ghcr.io/nilpc/event-ticketing",
    [string]$ImageTag = "main"
)

# ═══════════════════════════════════════════════════════════════════════
# Step 1: Pre-flight checks
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Pre-flight checks ===" -ForegroundColor Cyan
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not in PATH"
}
if (!(Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl is not installed or not in PATH"
}

$apiTag = "${ImagePrefix}-api:${ImageTag}"
$webTag = "${ImagePrefix}-web:${ImageTag}"

# ═══════════════════════════════════════════════════════════════════════
# Step 2: Authenticate Docker to GHCR
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Authenticating to GHCR ===" -ForegroundColor Cyan
Write-Host "  Login required: echo `$env:GHCR_PAT | docker login ghcr.io -u <username> --password-stdin" -ForegroundColor Yellow
$loggedIn = docker system info 2>$null | Select-String "ghcr.io"
if (-not $loggedIn) {
    Write-Warning "Not logged into GHCR. Attempting login from environment..."
    if ($env:GHCR_PAT -and $env:GITHUB_ACTOR) {
        $env:GHCR_PAT | docker login ghcr.io -u $env:GITHUB_ACTOR --password-stdin
        if ($LASTEXITCODE -ne 0) { throw "GHCR login failed" }
    } else {
        docker login ghcr.io
        if ($LASTEXITCODE -ne 0) { throw "GHCR login failed" }
    }
}

# ═══════════════════════════════════════════════════════════════════════
# Step 3: Build Docker images
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Building Docker images ===" -ForegroundColor Cyan
$repoRoot = Resolve-Path "$PSScriptRoot/.."

Write-Host "  Building API image..." -ForegroundColor Gray
docker build -t $apiTag --target api -f "$repoRoot/Dockerfile" $repoRoot
if ($LASTEXITCODE -ne 0) { throw "Docker build (api) failed" }

Write-Host "  Building Web image..." -ForegroundColor Gray
docker build -t $webTag --target web -f "$repoRoot/Dockerfile" $repoRoot
if ($LASTEXITCODE -ne 0) { throw "Docker build (web) failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 4: Push to GHCR
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Pushing images to GHCR ===" -ForegroundColor Cyan
Write-Host "  Pushing API image..." -ForegroundColor Gray
docker push $apiTag
if ($LASTEXITCODE -ne 0) { throw "Docker push (api) failed" }

Write-Host "  Pushing Web image..." -ForegroundColor Gray
docker push $webTag
if ($LASTEXITCODE -ne 0) { throw "Docker push (web) failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 5: Update kubeconfig
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Updating kubeconfig ===" -ForegroundColor Cyan
aws eks update-kubeconfig --name $ClusterName --region $Region
if ($LASTEXITCODE -ne 0) { throw "kubeconfig update failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 6: Fetch WAF ARN from Terraform
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Fetching WAF ARN from Terraform output ===" -ForegroundColor Cyan
$wafArn = & terraform -chdir="$repoRoot/infra/terraform" output -raw waf_acl_arn 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($wafArn)) {
    Write-Warning "Could not read WAF ARN from Terraform. Deploying without WAF association."
    $wafArn = $null
} else {
    Write-Host "  WAF ARN: $wafArn" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════════════
# Step 7: Apply production manifests
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Applying Kustomize overlay ===" -ForegroundColor Cyan
$kustomizeDir = "$repoRoot/k8s/prod/"
if ($wafArn) {
    kubectl kustomize $kustomizeDir | ForEach-Object { $_ -replace '__WAF_ACL_ARN__', $wafArn } | kubectl apply -f -
} else {
    kubectl apply -k $kustomizeDir
}
if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 8: Wait for rollout
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Waiting for rollout to complete ===" -ForegroundColor Cyan
kubectl -n event-ticketing rollout status deployment/gateway-api --timeout=180s
kubectl -n event-ticketing rollout status deployment/gateway-web --timeout=180s
kubectl -n event-ticketing rollout status deployment/sweeper --timeout=60s
kubectl -n event-ticketing rollout status deployment/relay --timeout=60s
kubectl -n event-ticketing rollout status deployment/admitter --timeout=60s

# ═══════════════════════════════════════════════════════════════════════
# Step 9: Get ALB URL
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Deployment Complete! ===" -ForegroundColor Green
Start-Sleep -Seconds 30
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
