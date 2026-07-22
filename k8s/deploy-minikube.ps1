# Minikube deploy script
# Usage: .\k8s\deploy-minikube.ps1

$ErrorActionPreference = "Stop"

Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan
foreach ($cmd in @("minikube", "kubectl", "docker")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "$cmd not found. Install it first."
        exit 1
    }
}

Write-Host "==> Starting Minikube..." -ForegroundColor Cyan
minikube start --cpus 2 --memory 4096 --driver docker 2>$null

Write-Host "==> Pointing Docker CLI to Minikube daemon..." -ForegroundColor Cyan
minikube docker --shell powershell | Invoke-Expression

Write-Host "==> Building Docker image inside Minikube..." -ForegroundColor Cyan
docker build -t event-ticketing:latest .

Write-Host "==> Deploying to Minikube..." -ForegroundColor Cyan
kubectl apply -k k8s/minikube/

Write-Host "==> Waiting for Postgres to be ready..." -ForegroundColor Cyan
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgres -n event-ticketing --timeout=60s

Write-Host "==> Waiting for Redis to be ready..." -ForegroundColor Cyan
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=redis -n event-ticketing --timeout=60s

Write-Host "==> Waiting for migration job to complete..." -ForegroundColor Cyan
kubectl wait --for=condition=complete job/migrate-setup -n event-ticketing --timeout=120s

Write-Host "==> Waiting for gateway pods..." -ForegroundColor Cyan
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=gateway -n event-ticketing --timeout=120s

Write-Host "==> Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Get the URL:" -ForegroundColor Yellow
minikube service gateway -n event-ticketing --url
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  kubectl get pods -n event-ticketing"
Write-Host "  kubectl logs -f deployment/gateway -n event-ticketing"
Write-Host "  kubectl delete -k k8s/minikube/"
Write-Host "  minikube stop"
