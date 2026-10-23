#!/usr/bin/env python3
"""Configura o GLPI a partir dos arquivos config/*.tsv, pela API do próprio servidor (decisão 32).

    python3 ~/central-chamados/scripts/servidor/configurar-glpi.py            # simulação: só mostra
    python3 ~/central-chamados/scripts/servidor/configurar-glpi.py --aplicar  # cria no GLPI

Só cria o que ainda não existe (procura pelo nome), então pode rodar quantas vezes quiser: para incluir uma
categoria nova, basta acrescentar a linha no config/categorias.tsv e rodar de novo. Não apaga nem altera nada.
Chaves em ~/.config/central-chamados/glpi-api.env (fora do projeto).
"""

import csv
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config"
CHAVES = Path.home() / ".config/central-chamados/glpi-api.env"
APLICAR = "--aplicar" in sys.argv

# O endereço interno usa o certificado da autoridade local do Caddy, que o Python não conhece.
# A conexão sai e chega no próprio servidor, então a verificação do certificado não protege nada aqui.
SSL = ssl._create_unverified_context()


def ler_tsv(nome):
    linhas = (l for l in (CONFIG / nome).read_text(encoding="utf-8").splitlines() if l and not l.startswith("#"))
    return list(csv.DictReader(linhas, delimiter="\t"))


def ler_chaves():
    chaves = {}
    for linha in CHAVES.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.startswith("#"):
            k, v = linha.split("=", 1)
            chaves[k.strip()] = v.strip()
    return chaves


class Glpi:
    def __init__(self, chaves):
        self.url = chaves["GLPI_URL"]
        self.app = chaves["GLPI_APP_TOKEN"]
        r = self._pedir("GET", "/initSession", cabecalhos={"Authorization": f"user_token {chaves['GLPI_USER_TOKEN']}"})
        self.sessao = r["session_token"]

    def _pedir(self, metodo, caminho, dados=None, cabecalhos=None):
        h = {"App-Token": self.app, "Content-Type": "application/json"}
        if getattr(self, "sessao", None):
            h["Session-Token"] = self.sessao
        h.update(cabecalhos or {})
        corpo = json.dumps(dados).encode() if dados is not None else None
        pedido = urllib.request.Request(self.url + caminho, data=corpo, headers=h, method=metodo)
        try:
            with urllib.request.urlopen(pedido, context=SSL) as resp:
                texto = resp.read().decode()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Erro da API em {metodo} {caminho}: {e.code} {e.read().decode()[:300]}")
        return json.loads(texto) if texto else None

    def listar(self, tipo):
        return self._pedir("GET", f"/{tipo}?range=0-9999&expand_dropdowns=false") or []

    def criar(self, tipo, dados):
        return self._pedir("POST", f"/{tipo}", {"input": dados})["id"]

    def sair(self):
        self._pedir("GET", "/killSession")


def garantir(glpi, tipo, existentes, chave, dados, rotulo):
    """Cria o item se não existir um com a mesma chave (nome ou caminho completo). Devolve o id (ou None na simulação)."""
    if chave in existentes:
        return existentes[chave]
    print(f"  + {rotulo}")
    if not APLICAR:
        return None
    novo = glpi.criar(tipo, dados)
    existentes[chave] = novo
    return novo


def categorias(glpi):
    print("Categorias:")
    linhas = ler_tsv("categorias.tsv")
    existentes = {c["completename"]: c["id"] for c in glpi.listar("ITILCategory")}
    # Visíveis para incidente, requisição e no portal das lojas; o tipo e a prioridade de cada problema
    # são aplicados pelas regras de negócio (próxima etapa), não pela categoria.
    base = {"entities_id": 0, "is_recursive": 1, "is_helpdeskvisible": 1, "is_incident": 1, "is_request": 1,
            "is_problem": 1, "is_change": 1}
    criadas = 0
    for l in linhas:
        caminho = []
        pai = 0
        for nome in (l["Categoria"], l["Grupo"], l["Problema"]):
            if not nome:
                continue
            caminho.append(nome)
            chave = " > ".join(caminho)
            antes = len(existentes)
            pai = garantir(glpi, "ITILCategory", existentes, chave,
                           {**base, "name": nome, "itilcategories_id": pai or 0}, chave)
            criadas += len(existentes) > antes or (not APLICAR and chave not in existentes)
            if pai is None:  # simulação: marca como "existente" para não listar de novo
                existentes[chave] = 0
                pai = 0
    print(f"  {len(linhas)} problemas no arquivo; {criadas} itens {'criados' if APLICAR else 'a criar'}.")


def unidades(glpi):
    print("Unidades:")
    existentes = {u["name"]: u["id"] for u in glpi.listar("Location")}
    for u in ler_tsv("unidades.tsv"):
        nome = f"{u['Código']} {u['Nome']}"
        garantir(glpi, "Location", existentes, nome,
                 {"name": nome, "code": u["Código"], "town": u["Cidade"], "entities_id": 0, "is_recursive": 1}, nome)


def listas(glpi):
    print("Motivos de pendência e tipos de solução:")
    tipos = {"Motivo de pendência": "PendingReason", "Tipo de solução": "SolutionType"}
    existentes = {t: {i["name"]: i["id"] for i in glpi.listar(t)} for t in tipos.values()}
    for l in ler_tsv("listas.tsv"):
        t = tipos[l["Tipo"]]
        dados = {"name": l["Nome"], "comment": l["Observação"], "entities_id": 0, "is_recursive": 1}
        garantir(glpi, t, existentes[t], l["Nome"], dados, f"{l['Tipo']}: {l['Nome']}")


def main():
    print("APLICANDO no GLPI." if APLICAR else "SIMULAÇÃO: nada será gravado (use --aplicar para criar).")
    glpi = Glpi(ler_chaves())
    try:
        unidades(glpi)
        listas(glpi)
        categorias(glpi)
    finally:
        glpi.sair()
    print("Pronto.")


if __name__ == "__main__":
    main()
