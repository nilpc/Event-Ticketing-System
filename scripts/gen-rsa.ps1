$jwtDir = "D:\Projects\Event-Ticketing-System\certs"
New-Item -ItemType Directory -Force -Path $jwtDir | Out-Null

$rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider 2048

# Export private key in PKCS#1 PEM format
$privParams = $rsa.ExportParameters($true)
$privStream = New-Object System.IO.MemoryStream
$privWriter = New-Object System.IO.BinaryWriter $privStream

# Convert to DER: RSAPrivateKey SEQUENCE
$writer = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter $writer

# PKCS#1 RSAPrivateKey fields
function Write-DER-Length {
    param($writer, $len)
    if ($len -lt 128) {
        $writer.Write([byte]$len)
    } elseif ($len -lt 256) {
        $writer.Write([byte]0x81)
        $writer.Write([byte]$len)
    } else {
        $writer.Write([byte]0x82)
        $writer.Write([byte](($len -band 0xFF00) -shr 8))
        $writer.Write([byte]($len -band 0xFF))
    }
}

function Write-DER-Integer {
    param($writer, $bytes)
    $writer.Write([byte]0x02) # INTEGER tag
    # Strip leading zero bytes, add sign byte if needed
    $trimmed = @($bytes) | Where-Object { $_ -ne 0 -or $stillGoing } | ForEach-Object { $stillGoing=$true; $_ }
    if ($trimmed[0] -band 0x80) {
        $trimmed = @(0x00) + $trimmed
    }
    if ($trimmed.Count -eq 0) { $trimmed = @(0x00) }
    Write-DER-Length $writer $trimmed.Count
    $writer.Write($trimmed)
}

# Version (0)
$writer.Write([byte]0x02)
$writer.Write([byte]0x01)
$writer.Write([byte]0x00)

Write-DER-Integer $writer $privParams.Modulus
Write-DER-Integer $writer $privParams.Exponent
Write-DER-Integer $writer $privParams.D
Write-DER-Integer $writer $privParams.P
Write-DER-Integer $writer $privParams.Q
Write-DER-Integer $writer $privParams.DP
Write-DER-Integer $writer $privParams.DQ
Write-DER-Integer $writer $privParams.InverseQ

$derData = $writer.ToArray()
$writer.Close()

# Wrap in SEQUENCE
$seqStream = New-Object System.IO.MemoryStream
$seqWriter = New-Object System.IO.BinaryWriter $seqStream
$seqWriter.Write([byte]0x30) # SEQUENCE
Write-DER-Length $seqWriter $derData.Length
$seqWriter.Write($derData)
$seqWriter.Close()
$privateDer = $seqStream.ToArray()

$privatePem = "-----BEGIN RSA PRIVATE KEY-----`n"
$privatePem += [System.Convert]::ToBase64String($privateDer, [System.Base64FormattingOptions]::InsertLineBreaks)
$privatePem += "`n-----END RSA PRIVATE KEY-----"

# Export public key in PKCS#1 PEM format
$pubParams = $rsa.ExportParameters($false)
$pubStream = New-Object System.IO.MemoryStream
$pubBw = New-Object System.IO.BinaryWriter $pubStream

$pubBw.Write([byte]0x30) # SEQUENCE
$innerStream = New-Object System.IO.MemoryStream
$innerBw = New-Object System.IO.BinaryWriter $innerStream

$innerBw.Write([byte]0x02) # INTEGER
$modBytes = $pubParams.Modulus
$trimmedMod = @($modBytes) | Where-Object { $_ -ne 0 -or $stillGoing2 } | ForEach-Object { $stillGoing2=$true; $_ }
if ($trimmedMod[0] -band 0x80) { $trimmedMod = @(0x00) + $trimmedMod }
Write-DER-Length $innerBw $trimmedMod.Count
$innerBw.Write($trimmedMod)

$innerBw.Write([byte]0x02) # INTEGER
$expBytes = $pubParams.Exponent
Write-DER-Length $innerBw $expBytes.Count
$innerBw.Write($expBytes)

$innerData = $innerStream.ToArray()
$innerStream.Close()

$pubLen = $innerData.Length
Write-DER-Length $pubBw $pubLen
$pubBw.Write($innerData)

$publicDer = $pubStream.ToArray()
$pubStream.Close()

$publicPem = "-----BEGIN RSA PUBLIC KEY-----`n"
$publicPem += [System.Convert]::ToBase64String($publicDer, [System.Base64FormattingOptions]::InsertLineBreaks)
$publicPem += "`n-----END RSA PUBLIC KEY-----"

Set-Content -Path "$jwtDir/private.pem" -Value $privatePem
Set-Content -Path "$jwtDir/public.pem" -Value $publicPem

Write-Host "JWT keys generated at $jwtDir"

# Write to SSM
aws ssm put-parameter --name "/event-ticketing/JWT_PRIVATE_KEY" --value $privatePem --type SecureString --overwrite --region us-east-1
aws ssm put-parameter --name "/event-ticketing/JWT_PUBLIC_KEY" --value $publicPem --type SecureString --overwrite --region us-east-1
Write-Host "JWT keys written to SSM"
