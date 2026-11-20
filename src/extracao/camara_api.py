"""Cliente da API de Dados Abertos da Câmara, com cache em data/raw/api."""
import hashlib
import json
import time
import zipfile
from pathlib import Path

import requests

from src import config

_sessao = requests.Session()
_sessao.headers.update({"Accept": "application/json"})


def _caminho_cache(endpoint: str, params: dict | None) -> Path:
    chave = endpoint.strip("/").replace("/", "_")
    if params:
        sufixo = json.dumps(params, sort_keys=True)
        chave += "_" + hashlib.md5(sufixo.encode()).hexdigest()[:10]
    return config.DATA_RAW / "api" / f"{chave}.json"


def get(endpoint: str, params: dict | None = None, usar_cache: bool = True) -> dict:
    """GET em um endpoint da API, com cache em disco e retentativas."""
    destino = _caminho_cache(endpoint, params)
    if usar_cache and destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))

    url = f"{config.API_CAMARA}/{endpoint.lstrip('/')}"
    # A API devolve 504 com frequência: tenta de novo com espera crescente.
    for tentativa in range(8):
        try:
            resp = _sessao.get(url, params=params, timeout=90)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(min(2 ** tentativa, 60))
            continue
        time.sleep(config.INTERVALO_REQUISICOES)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(min(2 ** tentativa, 60))
            continue
        resp.raise_for_status()
        break
    else:
        raise RuntimeError(f"Falha persistente em {url} {params}")

    dados = resp.json()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def get_paginado(endpoint: str, params: dict | None = None) -> list[dict]:
    """Percorre todas as páginas de um endpoint e devolve a lista `dados`."""
    params = dict(params or {})
    params.setdefault("itens", config.ITENS_POR_PAGINA)
    pagina, resultado = 1, []
    while True:
        resp = get(endpoint, {**params, "pagina": pagina})
        resultado.extend(resp.get("dados", []))
        if not any(link["rel"] == "next" for link in resp.get("links", [])):
            return resultado
        pagina += 1


def _tamanho_total(resp: requests.Response) -> int | None:
    """Tamanho completo do arquivo segundo o servidor, se ele informar."""
    faixa = resp.headers.get("Content-Range", "")  # "bytes 100-999/1000"
    if "/" in faixa and faixa.rsplit("/", 1)[1].isdigit():
        return int(faixa.rsplit("/", 1)[1])
    tamanho = resp.headers.get("Content-Length", "")
    return int(tamanho) if resp.status_code == 200 and tamanho.isdigit() else None


def _zip_integro(caminho: Path, completo: bool = False) -> bool:
    """O .zip abre? Com completo=True, confere também o CRC de todos os membros."""
    if caminho.suffix != ".zip":
        return True
    try:
        with zipfile.ZipFile(caminho) as z:
            return z.testzip() is None if completo else bool(z.namelist())
    except (zipfile.BadZipFile, OSError):
        return False


def baixar_arquivo(url: str, destino: Path) -> Path:
    """Baixa um arquivo em lote para data/raw, se ainda não existir.
    Retoma downloads interrompidos (Range) e confere tamanho e ZIP no fim."""
    if destino.exists():
        if _zip_integro(destino):
            return destino
        print(f"  {destino.name} no cache está corrompido; baixando de novo")
        destino.unlink()
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    esperado = None

    for tentativa in range(8):
        ja_baixado = tmp.stat().st_size if tmp.exists() else 0
        headers = {"Range": f"bytes={ja_baixado}-"} if ja_baixado else {}
        try:
            with _sessao.get(url, stream=True, timeout=300, headers=headers) as resp:
                if resp.status_code == 416:  # .part já está completo
                    break
                resp.raise_for_status()
                esperado = _tamanho_total(resp) or esperado
                modo = "ab" if resp.status_code == 206 else "wb"
                with open(tmp, modo) as f:
                    for bloco in resp.iter_content(chunk_size=1 << 20):
                        f.write(bloco)
            if esperado is not None and tmp.stat().st_size < esperado:
                raise requests.exceptions.ChunkedEncodingError(
                    f"recebidos {tmp.stat().st_size} de {esperado} bytes")
            break
        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as erro:
            espera = min(2 ** tentativa, 60)
            print(f"  conexão interrompida em {destino.name} ({erro.__class__.__name__}); "
                  f"retomando em {espera}s")
            time.sleep(espera)
    else:
        raise RuntimeError(f"Falha persistente ao baixar {url}")

    recebido = tmp.stat().st_size
    if esperado is not None and recebido != esperado:
        tmp.unlink()
        raise RuntimeError(f"{destino.name}: {recebido} bytes, diferente do informado pelo servidor ({esperado})")
    if not _zip_integro(tmp, completo=True):
        tmp.unlink()
        raise RuntimeError(f"{destino.name}: ZIP corrompido após o download; rode a coleta de novo")
    tmp.rename(destino)
    time.sleep(config.INTERVALO_REQUISICOES)
    return destino
