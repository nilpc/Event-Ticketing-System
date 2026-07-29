$ErrorActionPreference = "Stop"

Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan
foreach ($cmd in @("minikube", "kubectl", "docker")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "$cmd not found. Install it first."
        exit 1
    }
}

Write-Host "==> Starting Minikube..." -ForegroundColor Cyan
minikube start --cpus 2 --memory 3072 --driver docker 2>$null

Write-Host "==> Enabling NGINX Ingress Controller..." -ForegroundColor Cyan
minikube addons enable ingress 2>$null

Write-Host "==> Pointing Docker CLI to Minikube daemon..." -ForegroundColor Cyan
& minikube -p minikube docker-env --shell powershell | Invoke-Expression

Write-Host "==> Building Docker images inside Minikube..." -ForegroundColor Cyan
docker build -t event-ticketing-api:latest --target api .
docker build -t event-ticketing-web:latest --target web .

Write-Host "==> Deploying to Minikube..." -ForegroundColor Cyan
kubectl apply -k k8s/minikube/

Write-Host "==> Waiting for Postgres to be ready..." -ForegroundColor Cyan
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgres -n event-ticketing --timeout=60s

Write-Host "==> Waiting for Redis to be ready..." -ForegroundColor Cyan
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=redis -n event-ticketing --timeout=60s

Write-Host "==> Waiting for migration job to complete..." -ForegroundColor Cyan
kubectl wait --for=condition=complete job/migrate-setup -n event-ticketing --timeout=120s

Write-Host "==> Waiting for pods..." -ForegroundColor Cyan
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=gateway-api -n event-ticketing --timeout=120s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=gateway-web -n event-ticketing --timeout=120s

Write-Host "==> Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Get the URL:" -ForegroundColor Yellow
minikube service gateway -n event-ticketing --url
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  kubectl get pods -n event-ticketing"
Write-Host "  kubectl logs -f deployment/gateway-api -n event-ticketing"
Write-Host "  kubectl logs -f deployment/gateway-web -n event-ticketing"
Write-Host "  kubectl delete -k k8s/minikube/"
Write-Host "  minikube stop"
