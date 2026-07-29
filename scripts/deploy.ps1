#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy the event-ticketing application to EKS.
    Builds Docker image, pushes to GHCR, and applies prod Kustomize overlay.
.PARAMETER Region
    AWS region (default: us-east-1)
.PARAMETER ClusterName
    EKS cluster name (default: event-ticketing)
.PARAMETER ImageName
    GHCR image name (default: ghcr.io/nilpc/event-ticketing-system)
.PARAMETER ImageTag
    Docker image tag (default: main)
#>

param(
    [string]$Region = "us-east-1",
    [string]$ClusterName = "event-ticketing",
    [string]$ImageName = "ghcr.io/nilpc/event-ticketing-system",
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

$fullImageTag = "${ImageName}:${ImageTag}"

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
# Step 3: Build Docker image
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Building Docker image ===" -ForegroundColor Cyan
$repoRoot = Resolve-Path "$PSScriptRoot/.."
docker build -t $fullImageTag -f "$repoRoot/Dockerfile" $repoRoot
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 4: Push to GHCR
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Pushing image to GHCR ===" -ForegroundColor Cyan
docker push $fullImageTag
if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 5: Update kubeconfig
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Updating kubeconfig ===" -ForegroundColor Cyan
aws eks update-kubeconfig --name $ClusterName --region $Region
if ($LASTEXITCODE -ne 0) { throw "kubeconfig update failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 6: Apply production manifests
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Applying Kustomize overlay ===" -ForegroundColor Cyan
kubectl apply -k "$repoRoot/k8s/prod/"
if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 7: Wait for rollout
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Waiting for rollout to complete ===" -ForegroundColor Cyan
kubectl -n event-ticketing rollout status deployment/gateway --timeout=180s
kubectl -n event-ticketing rollout status deployment/sweeper --timeout=60s
kubectl -n event-ticketing rollout status deployment/relay --timeout=60s
kubectl -n event-ticketing rollout status deployment/admitter --timeout=60s

# ═══════════════════════════════════════════════════════════════════════
# Step 8: Get ALB URL
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
Write-Host "To view logs:    kubectl logs -n event-ticketing deployment/gateway -f" -ForegroundColor Gray

