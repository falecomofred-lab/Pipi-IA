<#
    LIMPAR_PIPI.ps1 — deixa a pasta da Pipi 100% Modal
    Venure · venure.com.br · 17/09/2026

    Rode NA PASTA DA PIPI:

        powershell -ExecutionPolicy Bypass -File .\LIMPAR_PIPI.ps1 -Ensaio
        powershell -ExecutionPolicy Bypass -File .\LIMPAR_PIPI.ps1

    O primeiro so MOSTRA o que sairia. O segundo move.

    NADA E APAGADO
        Tudo vai para _quarentena-pipi, com um manifesto dizendo o que foi
        e de onde veio. Quando voce tiver certeza, apague a pasta inteira
        de uma vez. Ate la, voltar atras e arrastar de volta.

    A QUARENTENA MORA FORA DA PASTA VARRIDA, E ISSO NAO E DETALHE   (13/09)
        A primeira versao deste script criava a quarentena DENTRO da pasta
        que estava limpando, e movia com -Recurse. O resultado foi um
        caminho aninhado cerca de cem niveis fundo -- quarentena dentro de
        quarentena dentro de quarentena -- que o proprio Windows nao
        conseguia mais apagar, porque passou do limite de 260 caracteres.
        Levou um segundo script so para desfazer.

        Por isso: a quarentena fica no PAI, a lista de alvos e materializada
        com @() ANTES de mover (senao a enumeracao muda embaixo dos pes), e
        nada com "_quarentena" no nome entra na lista.
#>

[CmdletBinding()]
param(
    [switch]$Ensaio
)

$ErrorActionPreference = 'Stop'

$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pai  = Split-Path -Parent $Raiz
$Selo = Get-Date -Format 'yyyy-MM-dd_HHmm'
$Quar = Join-Path $Pai ("_quarentena-pipi_" + $Selo)

# ------------------------------------------------------------------
# O QUE SAI, E POR QUE
# ------------------------------------------------------------------
$Alvos = @(
    @{ n = 'huggingface_cliente.py'
       p = 'Backend Hugging Face. A Pipi agora usa so a Modal.' }
    @{ n = 'usar_desenhista_do_colab.py'
       p = 'Apontava a Pipi para o ComfyUI do Colab. Sem Colab, sem uso.' }
    @{ n = 'motor_remoto.txt'
       p = 'Guardava o endereco do tunel do Colab. Ja estava vazio.' }
    @{ n = 'workflow.json'
       p = 'Receita de nos do ComfyUI. A Modal nao usa workflow.' }
    @{ n = 'motores.json'
       p = 'Catalogo dos .gguf do pendrive. O modelo agora e um so, na Modal.' }
    @{ n = 'verificar_gguf.py'
       p = 'Conferia .gguf locais.' }
    @{ n = 'verificar_gguf.bat'
       p = 'Atalho do verificar_gguf.py.' }
    @{ n = 'comfyui.log'
       p = 'Log de um servidor que nao sobe mais.' }
    @{ n = 'pipi_server_external_models.py'
       p = 'Variante antiga do servidor, substituida pelo pipi_server.py.' }
    @{ n = 'PIPI_INDEPENDENTE.md'
       p = 'Documento antigo. O TUTORIAL.md e a versao viva.' }
    @{ n = 'PIPI_INDEPENDENTE_EXTERNAL_MODELS.md'
       p = 'Documento antigo, sobre modelos externos que sairam.' }
    @{ n = 'REFERENCIAS_MOTORES.md'
       p = 'Lista de .gguf e licencas. Nao ha mais escolha de motor.' }
    @{ n = 'COMO_INICIAR.md'
       p = 'Instrucoes antigas, com o caminho do ComfyUI.' }
)

Write-Host ''
Write-Host '======================================================================'
Write-Host '  LIMPAR A PIPI  --  deixar so o caminho da Modal'
Write-Host '======================================================================'
Write-Host ''
Write-Host ("  pasta      : " + $Raiz)
Write-Host ("  quarentena : " + $Quar)
if ($Ensaio) { Write-Host '  modo       : ENSAIO (nada sai do lugar)' }
Write-Host ''

# ------------------------------------------------------------------
# Lista materializada ANTES de mexer em nada. Ver o cabecalho.
# ------------------------------------------------------------------
$Achados = @()
$Ausentes = @()
foreach ($a in $Alvos) {
    $caminho = Join-Path $Raiz $a.n
    if ($a.n -like '*_quarentena*') { continue }
    if (Test-Path -LiteralPath $caminho) {
        $Achados += [pscustomobject]@{ Nome = $a.n; Porque = $a.p; Caminho = $caminho }
    } else {
        $Ausentes += $a.n
    }
}

# O __pycache__ e regenerado pelo Python a cada execucao. Nao vai para a
# quarentena: guardar cache nao protege ninguem de nada.
$Cache = Join-Path $Raiz '__pycache__'
$TemCache = Test-Path -LiteralPath $Cache

Write-Host '  SAEM DE CENA'
Write-Host '  ---------------------------------------------------------------'
foreach ($x in $Achados) {
    Write-Host ("  - {0,-38} {1}" -f $x.Nome, $x.Porque)
}
if ($TemCache) {
    Write-Host ("  - {0,-38} {1}" -f '__pycache__\', 'Cache do Python, refeito sozinho. Apagado, nao guardado.')
}
if ($Achados.Count -eq 0 -and -not $TemCache) {
    Write-Host '  (nada a fazer -- a pasta ja esta limpa)'
    Write-Host ''
    exit 0
}

if ($Ausentes.Count) {
    Write-Host ''
    Write-Host ('  ja nao estavam aqui: ' + ($Ausentes -join ', '))
}

Write-Host ''
Write-Host '  FICAM'
Write-Host '  ---------------------------------------------------------------'
@(
    'pipi.bat                     abre a Pipi'
    'pipi_server.py               a tela, o login e a fila'
    'modal_cliente.py             conversa com a Modal'
    'modal_pipi.py                o desenhista, que roda NA Modal'
    'usar_modal.py                aponta a Pipi para a Modal'
    'login_venure.py              login, com a conta do Bigode'
    'modal.json                   endereco e token (fora do Git)'
    'web\                         a tela e as imagens da marca'
    'producao\                    as suas criacoes'
    'manifest.json                para instalar como aplicativo'
    'requirements.txt             o que instalar'
    'TUTORIAL.md  README.md       como usar'
) | ForEach-Object { Write-Host ('  . ' + $_) }

if ($Ensaio) {
    Write-Host ''
    Write-Host '  ENSAIO. Para valer, rode sem -Ensaio.'
    Write-Host '======================================================================'
    Write-Host ''
    exit 0
}

Write-Host ''
$resp = Read-Host '  Mover para a quarentena? (s/N)'
if ($resp -notmatch '^[sS]') {
    Write-Host '  Cancelado. Nada saiu do lugar.'
    Write-Host ''
    exit 0
}

New-Item -ItemType Directory -Path $Quar -Force | Out-Null

$linhas = @()
$linhas += 'QUARENTENA DA PIPI IA -- ' + (Get-Date -Format 'dd/MM/yyyy HH:mm')
$linhas += 'Origem: ' + $Raiz
$linhas += ''
$linhas += 'Estes arquivos sairam porque a Pipi passou a usar SO a Modal.'
$linhas += 'Para desfazer, mova o arquivo de volta para a pasta de origem.'
$linhas += ''

$movidos = 0
foreach ($x in $Achados) {
    try {
        Move-Item -LiteralPath $x.Caminho -Destination (Join-Path $Quar $x.Nome) -Force
        Write-Host ('  movido   ' + $x.Nome)
        $linhas += ('{0,-40} {1}' -f $x.Nome, $x.Porque)
        $movidos++
    } catch {
        Write-Host ('  FALHOU   ' + $x.Nome + '  --  ' + $_.Exception.Message)
        $linhas += ('{0,-40} FALHOU AO MOVER: {1}' -f $x.Nome, $_.Exception.Message)
    }
}

if ($TemCache) {
    try {
        Remove-Item -LiteralPath $Cache -Recurse -Force
        Write-Host '  apagado  __pycache__\'
    } catch {
        Write-Host ('  FALHOU   __pycache__\  --  ' + $_.Exception.Message)
    }
}

$linhas | Set-Content -LiteralPath (Join-Path $Quar 'LEIA-ME.txt') -Encoding UTF8

Write-Host ''
Write-Host ('  ' + $movidos + ' arquivo(s) na quarentena, com o LEIA-ME.txt do que foi cada um.')
Write-Host ''
Write-Host '  CONFIRA ANTES DE APAGAR A QUARENTENA:'
Write-Host '    1. .\pipi.bat            a Pipi abre?'
Write-Host '    2. gere uma imagem       ela sai?'
Write-Host ''
Write-Host '  Se sim, apague a pasta da quarentena. Se nao, arraste de volta.'
Write-Host '======================================================================'
Write-Host ''
