# PUBLICAR A PIPI IA NO GITHUB -- com trava de seguranca     (29/09/2026)
#
#   Rode assim, dentro da pasta Pipi IA:
#       powershell -ExecutionPolicy Bypass -File .\PUBLICAR_NO_GITHUB.ps1
#
#   O que faz:
#     1. apaga os desktop.ini que o Google Drive cria dentro da .git
#     2. garante no .gitignore: .git-antigo*/ e cloudflare.json
#     3. tira do GitHub (NAO do seu PC) a pasta .git-antigo e os arquivos de chave
#     4. TRAVA: se algum arquivo de chave ou senha for ENTRAR no envio, para tudo
#     5. commit + push

$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot
$url = "https://github.com/falecomofred-lab/Pipi-IA.git"
Write-Host "`n===== $PSScriptRoot =====" -ForegroundColor Cyan

Get-ChildItem .git -Recurse -Force -Filter desktop.ini -ErrorAction SilentlyContinue | Remove-Item -Force

foreach ($r in @(".git-antigo*/", "cloudflare.json")) {
  if (-not (Select-String -LiteralPath .gitignore -SimpleMatch -Pattern $r -Quiet)) { Add-Content -LiteralPath .gitignore -Value $r }
}

foreach ($p in @(".git-antigo-20260921-002230", "cloudflare.json", "modal.json", "ponte.txt", "usuarios.json")) {
  git rm -r --cached --quiet --ignore-unmatch -- "$p" 2>$null
}

if (-not (git remote)) { git remote add origin $url }

git add -A

# So olha o que ENTRA (A=novo, C=copiado, M=mudado, R=renomeado). O que SAI e bem-vindo.
$proibidos = git diff --cached --name-only --diff-filter=ACMR | Select-String -Pattern '(^|/)(config\.json|conexoes\.json|modal\.json|cloudflare\.json|ponte\.txt|usuarios\.json|fatos\.json)$|\.bak$|\.git-antigo'
$chaves    = git diff --cached --name-only --diff-filter=ACMR -G 'cfat_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}'
if ($proibidos -or $chaves) {
  Write-Host "PAREI: arquivo sensivel no envio. Nada foi enviado:" -ForegroundColor Red
  $proibidos; $chaves
  git reset --quiet
  exit 1
}

git commit -m "Atualizacao 29/09: reserva gratis na Cloudflare, pipi.bat corrigido, remove .git-antigo"
git push origin HEAD

Write-Host "`nPronto. Se apareceu '-> main' acima, foi enviado." -ForegroundColor Green
