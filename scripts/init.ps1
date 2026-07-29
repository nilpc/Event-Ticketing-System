#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Bootstrap script for Phase 7 EKS cluster.
    Run ONCE after `terraform apply` completes successfully.
.DESCRIPTION
    Configures kubectl, installs Helm add-ons (LB Controller, KEDA, ESO,
    Bitnami Redis, ArgoCD, Node Termination Handler), and writes secrets
    to AWS SSM Parameter Store.
.PARAMETER ClusterName
    EKS cluster name (default: event-ticketing)
.PARAMETER Region
    AWS region (default: us-east-1)
.PARAMETER LbControllerRoleArn
    IAM role ARN for AWS Load Balancer Controller (from Terraform output)
.PARAMETER EsoRoleArn
    IAM role ARN for External Secrets Operator (from Terraform output)
.PARAMETER RdsEndpoint
    RDS endpoint hostname:port (from Terraform output)
.PARAMETER DbUsername
    RDS master username (from Terraform output)
.PARAMETER DbPassword
    RDS master password (from Terraform output)
.PARAMETER CorsOrigins
    Comma-separated CORS origins (default: *, override for production)
.PARAMETER ClientOrigin
    Frontend URL for redirects (default: *, override for production)
.PARAMETER AutoDetect
    Read LbControllerRoleArn, EsoRoleArn, and RdsEndpoint from `terraform output`
#>

param(
    [string]$ClusterName = "event-ticketing",
    [string]$Region = "us-east-1",
    [string]$LbControllerRoleArn = "",
    [string]$EsoRoleArn = "",
    [string]$RdsEndpoint = "",
    [string]$DbUsername = "etadmin",
    [string]$DbPassword = "",
    [string]$CorsOrigins = "*",
    [string]$ClientOrigin = "*",
    [switch]$AutoDetect
)

# ═══════════════════════════════════════════════════════════════════════
# Step 0: Auto-detect Terraform outputs
# ═══════════════════════════════════════════════════════════════════════
if ($AutoDetect) {
    Write-Host "=== Auto-detecting Terraform outputs ===" -ForegroundColor Cyan
    $tfDir = Resolve-Path "$PSScriptRoot/../infra/terraform"
    Push-Location $tfDir

    if ($LbControllerRoleArn -eq "") {
        $LbControllerRoleArn = terraform output -raw lb_controller_role_arn 2>$null
        Write-Host "  LbControllerRoleArn: $LbControllerRoleArn" -ForegroundColor Green
    }
    if ($EsoRoleArn -eq "") {
        $EsoRoleArn = terraform output -raw eso_role_arn 2>$null
        Write-Host "  EsoRoleArn: $EsoRoleArn" -ForegroundColor Green
    }
    if ($RdsEndpoint -eq "") {
        $RdsEndpoint = terraform output -raw rds_endpoint 2>$null
        Write-Host "  RdsEndpoint: $RdsEndpoint" -ForegroundColor Green
    }

    Pop-Location
}

# ═══════════════════════════════════════════════════════════════════════
# Step 1: Configure kubectl
# ═══════════════════════════════════════════════════════════════════════
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Event Ticketing — EKS Bootstrap Script              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "=== Step 1: Configuring kubectl ===" -ForegroundColor Cyan
aws eks update-kubeconfig --name $ClusterName --region $Region
if ($LASTEXITCODE -ne 0) { throw "kubectl config failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 2: Create namespace
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 2: Creating namespace ===" -ForegroundColor Cyan
kubectl create namespace event-ticketing --dry-run=client -o yaml | kubectl apply -f -

# ═══════════════════════════════════════════════════════════════════════
# Step 3: Install AWS Load Balancer Controller
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 3: Installing AWS Load Balancer Controller ===" -ForegroundColor Cyan
helm repo add eks https://aws.github.io/eks-charts 2>$null | Out-Null
helm repo update

if ($LbControllerRoleArn -ne "") {
    helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller `
        -n kube-system `
        --set clusterName=$ClusterName `
        --set serviceAccount.create=true `
        --set serviceAccount.name=aws-load-balancer-controller `
        --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$LbControllerRoleArn
} else {
    Write-Warning "LbControllerRoleArn not provided. Installing without IRSA."
    helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller `
        -n kube-system `
        --set clusterName=$ClusterName
}
if ($LASTEXITCODE -ne 0) { throw "ALB Controller install failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 4: Install KEDA
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 4: Installing KEDA ===" -ForegroundColor Cyan
helm repo add kedacore https://kedacore.github.io/charts 2>$null | Out-Null
helm repo update
helm upgrade --install keda kedacore/keda -n keda --create-namespace
if ($LASTEXITCODE -ne 0) { throw "KEDA install failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 5: Install External Secrets Operator
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 5: Installing External Secrets Operator ===" -ForegroundColor Cyan
helm repo add external-secrets https://charts.external-secrets.io 2>$null | Out-Null
helm repo update

if ($EsoRoleArn -ne "") {
    helm upgrade --install external-secrets external-secrets/external-secrets `
        -n external-secrets --create-namespace `
        --set serviceAccount.create=true `
        --set serviceAccount.name=external-secrets-sa `
        --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$EsoRoleArn
} else {
    Write-Warning "EsoRoleArn not provided. Installing without IRSA."
    helm upgrade --install external-secrets external-secrets/external-secrets `
        -n external-secrets --create-namespace
}
if ($LASTEXITCODE -ne 0) { throw "ESO install failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 6: Install Bitnami Redis (self-hosted, no ElastiCache fees)
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 6: Installing Redis (Bitnami) ===" -ForegroundColor Cyan
$redisPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
Write-Host "    Generated Redis password" -ForegroundColor Green

helm repo add bitnami https://charts.bitnami.com/bitnami 2>$null | Out-Null
helm repo update
helm upgrade --install redis bitnami/redis `
    -n event-ticketing `
    --set architecture=standalone `
    --set auth.enabled=true `
    --set auth.password=$redisPassword `
    --set master.persistence.size=1Gi
if ($LASTEXITCODE -ne 0) { throw "Redis install failed" }

# Store Redis password + URL in SSM
Write-SsmParam -Name "/event-ticketing/REDIS_PASSWORD" -Value $redisPassword

# ═══════════════════════════════════════════════════════════════════════
# Step 7: Install Node Termination Handler
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 7: Installing Node Termination Handler ===" -ForegroundColor Cyan
helm upgrade --install node-termination-handler eks/node-termination-handler `
    -n kube-system `
    --set enableSpotInterruptionDraining=true
if ($LASTEXITCODE -ne 0) { throw "Node Termination Handler install failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 8: Install ArgoCD
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 8: Installing ArgoCD ===" -ForegroundColor Cyan
helm repo add argo https://argoproj.github.io/argo-helm 2>$null | Out-Null
helm repo update
helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace `
    --set server.service.type=LoadBalancer `
    --set configs.params."server\.insecure"=true
if ($LASTEXITCODE -ne 0) { throw "ArgoCD install failed" }

# ═══════════════════════════════════════════════════════════════════════
# Step 9: Write secrets to SSM Parameter Store
# ═══════════════════════════════════════════════════════════════════════
Write-Host "=== Step 9: Writing secrets to SSM Parameter Store ===" -ForegroundColor Cyan

function Write-SsmParam {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrEmpty($Value) -or $Value -eq "") {
        Write-Warning "Skipping $Name — value is empty"
        return
    }
    aws ssm put-parameter `
        --name $Name `
        --value $Value `
        --type SecureString `
        --overwrite `
        --region $Region
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Wrote $Name" -ForegroundColor Green
    }
}

# Database
if ($RdsEndpoint -ne "") {
    $dbUrl = "postgresql+asyncpg://${DbUsername}:${DbPassword}@${RdsEndpoint}/event_ticketing"
    Write-SsmParam -Name "/event-ticketing/DATABASE_URL" -Value $dbUrl
}

# Redis (self-hosted in-cluster, with auth)
$redisUrl = "redis://:${redisPassword}@redis-master.event-ticketing.svc.cluster.local:6379/0"
Write-SsmParam -Name "/event-ticketing/REDIS_URL" -Value $redisUrl

# CORS — default to wide open for demo; override via -CorsOrigins/-ClientOrigin
Write-SsmParam -Name "/event-ticketing/CORS_ORIGINS" -Value $CorsOrigins
Write-SsmParam -Name "/event-ticketing/CLIENT_ORIGIN" -Value $ClientOrigin

# Logging
Write-SsmParam -Name "/event-ticketing/LOG_LEVEL" -Value "INFO"
Write-SsmParam -Name "/event-ticketing/LOG_FORMAT" -Value "json"

# Stripe, Google OAuth2, Sentry — optional, not prompted interactively.
# Set via the SSM Parameter Store after bootstrap if needed.

# JWT keys (generate if not exist)
$jwtDir = Join-Path $PSScriptRoot ".." "certs"
if (!(Test-Path "$jwtDir/private.pem")) {
    Write-Host "Generating RSA keys for JWT..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $jwtDir | Out-Null
    openssl genrsa -out "$jwtDir/private.pem" 2048
    openssl rsa -in "$jwtDir/private.pem" -pubout -out "$jwtDir/public.pem"
}
Write-SsmParam -Name "/event-ticketing/JWT_PRIVATE_KEY" -Value (Get-Content "$jwtDir/private.pem" -Raw)
Write-SsmParam -Name "/event-ticketing/JWT_PUBLIC_KEY" -Value (Get-Content "$jwtDir/public.pem" -Raw)

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║               Bootstrap Complete!                       ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Verify ALB Controller: kubectl get pods -n kube-system"
Write-Host "  2. Apply production manifests: kubectl apply -k k8s/prod/"
Write-Host "  3. Get ALB DNS: kubectl get ingress -n event-ticketing"
Write-Host "  4. Get ArgoCD password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
Write-Host "  5. Open CloudWatch dashboard: https://console.aws.amazon.com/cloudwatch/home?region=${Region}#dashboards:name=${ClusterName}-operations"
