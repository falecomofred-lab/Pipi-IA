"""APONTAR A PIPI PARA O COMFYUI DO COLAB

Rode NO SEU WINDOWS, na pasta da Pipi IA:

    python usar_desenhista_do_colab.py

Ele pede o endereco que a celula 8-C do Colab imprimiu, confere se o
ComfyUI responde de verdade, e so entao grava em motor_remoto.txt.

POR QUE ARQUIVO E NAO VARIAVEL DE AMBIENTE
    `set PIPI_COMFYUI_URL=...` morre quando a janela fecha, e o endereco do
    Colab muda a cada sessao. Guardar em arquivo faz o pipi.bat achar
    sozinho na proxima vez.

POR QUE CONFERIR ANTES DE GRAVAR
    Endereco errado nao falha na hora: a Pipi sobe, parece bem, e so quebra
    quando voce pede a primeira imagem -- com um erro de rede que nao diz
    que o culpado foi um caractere trocado.

PARA VOLTAR AO COMFYUI DESTA MAQUINA

    python usar_desenhista_do_colab.py --local

Venure - venure.com.br
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "motor_remoto.txt"


def testar(url):
    """`/system_stats` e o "voce esta ai?" do ComfyUI."""
    try:
        with urllib.request.urlopen(url + "/system_stats", timeout=20) as r:
            bruto = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, "o servidor respondeu %d." % e.code, {}
    except urllib.error.URLError as e:
        return False, ("nao cheguei no endereco (%s). O Colab ainda esta "
                       "ligado? O link muda a cada sessao." % e.reason), {}
    except Exception as e:
        return False, str(e), {}

    try:
        dados = json.loads(bruto)
    except Exception:
        return False, ("o endereco respondeu, mas nao parece um ComfyUI "
                       "(devolveu algo que nao e JSON)."), {}
    return True, "", dados


def descrever(dados):
    """Mostra a placa que vai desenhar. Ver 'Tesla T4' na tela e a prova de
    que o tunel chegou no Colab certo, e nao em outra coisa."""
    linhas = []
    for d in (dados.get("devices") or []):
        nome = d.get("name", "")
        total = d.get("vram_total")
        if nome and total:
            linhas.append("    placa ... %s (%.1f GB)" % (nome, total / 1e9))
        elif nome:
            linhas.append("    placa ... %s" % nome)
    return linhas


def main():
    if "--local" in sys.argv:
        if ARQUIVO.is_file():
            ARQUIVO.unlink()
        print("\n  Pronto. A Pipi volta a procurar o ComfyUI desta maquina")
        print("  em http://127.0.0.1:8188.\n")
        return

    print()
    print("=" * 68)
    print("  USAR O DESENHISTA DO COLAB")
    print("=" * 68)
    print()
    print("  Cole o endereco que a celula 8-C imprimiu e de Enter.")
    print("  Ele se parece com https://alguma-coisa.trycloudflare.com")
    print()
    url = input("  > ").strip().rstrip("/")

    if not url.startswith("http"):
        raise SystemExit("\n  Isso nao e um endereco. Comece com https://\n")

    print()
    print("  Testando...")
    ok, porque, dados = testar(url)

    if not ok:
        print()
        print("  NAO GRAVEI NADA -- %s" % porque)
        print()
        print("  A Pipi continua como estava.")
        print("=" * 68)
        print()
        return

    ARQUIVO.write_text(url, encoding="utf-8")

    print()
    print("  FUNCIONOU. Gravado em motor_remoto.txt.")
    print()
    print("    motor ... %s" % url)
    for linha in descrever(dados):
        print(linha)
    print()
    print("  Agora inicie a Pipi:   pipi.bat")
    print()
    print("  Quando o Colab desligar, rode:")
    print("    python usar_desenhista_do_colab.py --local")
    print("=" * 68)
    print()


if __name__ == "__main__":
    main()
