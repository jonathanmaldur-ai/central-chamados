#!/usr/bin/env python3
"""Gera os manuais em HTML com o visual Dorémi (o mesmo do SmartStock), prontos para salvar em PDF.

    python3 ~/central-chamados/scripts/gerar-manuais.py

Lê manuais/*.md e grava manuais/*.html ao lado, com o logo embutido. Para o PDF: abrir o .html no Chrome,
Ctrl+P → Salvar como PDF, papel A4, com "Gráficos de plano de fundo" marcado.
O conversor entende só o que os manuais usam: títulos, parágrafos, negrito, `código`, links, listas
(numeradas e com marcadores, um nível de sub-itens), tabelas e imagens numa linha só (`![legenda](imagens/x.png)`,
embutidas no HTML). Os prints de manuais/imagens saem de scripts/prints (capturar.mjs).
"""

import base64
import html
import re
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "manuais"
LOGO = RAIZ / "scripts/servidor/tema/doremi-brinquedos.png"

MANUAIS = {
    "manual-administrador.md": ("Manual do Administrador", "Para o TI: administração completa da Central"),
    "guia-da-loja.md": ("Guia da Loja", "Do primeiro acesso à avaliação do chamado"),
    "manual-gestao.md": ("Manual da Gestão", "Aprovações, acompanhamento e avaliações"),
}


def inline(texto):
    """Negrito, código e links dentro de uma linha (o texto é escapado antes)."""
    partes = re.split(r"(`[^`]+`)", texto)
    saida = []
    for p in partes:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            saida.append(f"<code>{html.escape(p[1:-1])}</code>")
            continue
        p = html.escape(p.replace("\\[", "[").replace("\\]", "]").replace("\\*", "*"))
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(https?://[^\s<),]+[^\s<),.])", r'<a href="\1">\1</a>', p)
        saida.append(p)
    return "".join(saida)


def converter(md):
    linhas = md.splitlines()
    corpo, i = [], 0
    while i < len(linhas):
        linha = linhas[i]
        if not linha.strip():
            i += 1
            continue
        if linha.startswith("# "):  # o título vai no cabeçalho
            i += 1
            continue
        if linha.startswith("## "):
            corpo.append(f"<h2>{inline(linha[3:])}</h2>")
            i += 1
            continue
        imagem = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", linha)
        if imagem:
            dados = base64.b64encode((PASTA / imagem[2]).read_bytes()).decode()
            corpo.append(f'<figure><img src="data:image/png;base64,{dados}" alt="{html.escape(imagem[1])}">'
                         f"<figcaption>{inline(imagem[1])}</figcaption></figure>")
            i += 1
            continue
        if linha.startswith("|"):
            tabela = []
            while i < len(linhas) and linhas[i].startswith("|"):
                tabela.append([c.strip() for c in linhas[i].strip().strip("|").split("|")])
                i += 1
            cab, linhas_t = tabela[0], [t for t in tabela[2:]]
            corpo.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cab) + "</tr></thead><tbody>"
                         + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in t) + "</tr>" for t in linhas_t)
                         + "</tbody></table>")
            continue
        if re.match(r"^(\d+\.|-) ", linha):
            ordenada = linha[0].isdigit()
            itens = []
            while i < len(linhas) and (re.match(r"^(\d+\.|-) ", linhas[i]) or linhas[i].startswith("    ")):
                atual = linhas[i]
                if atual.startswith("    "):
                    itens[-1][1].append(inline(re.sub(r"^\s*- ", "", atual)))
                else:
                    itens.append([inline(re.sub(r"^(\d+\.|-) ", "", atual)), []])
                i += 1
            tag = "ol" if ordenada else "ul"
            corpo.append(f"<{tag}>" + "".join(
                f"<li>{t}" + ("<ul>" + "".join(f"<li>{s}</li>" for s in subs) + "</ul>" if subs else "") + "</li>"
                for t, subs in itens) + f"</{tag}>")
            continue
        paragrafo = [linha]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not re.match(r"^(#|\||\d+\. |- |!\[)", linhas[i]):
            paragrafo.append(linhas[i])
            i += 1
        corpo.append(f"<p>{inline(' '.join(paragrafo))}</p>")
    return "\n".join(corpo)


ESTILO = """
:root{--primary:#1273ba;--primary-active:#0c4c7a;--primary-soft:#e7f1fa;--secondary:#3b55a0;
--bg:#f5f7fb;--surface:#fff;--muted:#eef2f8;--border:#dce2ec;--text:#1b2438;--text-muted:#5a6478}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;font-family:Inter,system-ui,sans-serif;font-size:10.5pt;line-height:1.55;color:var(--text);background:var(--bg)}
.folha{max-width:820px;margin:24px auto;background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
header{display:flex;align-items:center;gap:20px;padding:24px 32px;border-bottom:4px solid var(--primary);background:var(--surface)}
header img{height:56px;width:auto}
header .titulo{flex:1}
header h1{margin:0;font-family:Poppins,Inter,sans-serif;font-weight:600;font-size:21pt;color:var(--primary-active);line-height:1.2}
header .sub{margin:4px 0 0;color:var(--text-muted);font-size:10pt}
header .selo{font-family:Poppins,Inter,sans-serif;font-size:9pt;font-weight:600;color:var(--primary);background:var(--primary-soft);
border-radius:999px;padding:6px 12px;white-space:nowrap}
main{padding:8px 32px 24px}
h2{font-family:Poppins,Inter,sans-serif;font-weight:600;font-size:14pt;color:var(--primary-active);margin:26px 0 8px;
padding-bottom:6px;border-bottom:1px solid var(--border);break-after:avoid}
p{margin:8px 0}
strong{font-weight:600}
a{color:var(--primary);text-decoration:none}
code{font-family:ui-monospace,Consolas,monospace;font-size:9pt;background:var(--muted);color:var(--primary-active);
border-radius:4px;padding:1px 5px;overflow-wrap:anywhere}
ol,ul{margin:8px 0;padding-left:22px}
li{margin:3px 0}
li::marker{color:var(--primary);font-weight:600}
table{width:100%;border-collapse:separate;border-spacing:0;margin:12px 0;border:1px solid var(--border);border-radius:8px;
overflow:hidden;font-size:9.5pt;break-inside:avoid}
th{background:var(--primary-soft);color:var(--primary-active);text-align:left;font-weight:600;padding:7px 10px}
td{padding:7px 10px;border-top:1px solid var(--border);vertical-align:top}
tr:nth-child(even) td{background:#fafbfd}
figure{margin:14px 0 18px;break-inside:avoid}
figure img{display:block;max-width:100%;height:auto;border:1px solid var(--border);border-radius:8px}
figcaption{margin-top:6px;color:var(--text-muted);font-size:9pt}
footer{display:flex;justify-content:space-between;gap:12px;padding:12px 32px;border-top:1px solid var(--border);
background:var(--muted);color:var(--text-muted);font-size:8.5pt}
@page{size:A4;margin:14mm 14mm 16mm}
@media print{html,body{background:#fff}.folha{margin:0;border:0;border-radius:0;max-width:none}
header,main,footer{padding-left:0;padding-right:0}footer{background:none}}
"""


def pagina(titulo, subtitulo, corpo, logo_b64, data):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)} · Central de Chamados de TI</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@500;600&display=swap">
<style>{ESTILO}</style>
</head>
<body>
<div class="folha">
<header>
<img src="data:image/png;base64,{logo_b64}" alt="Dorémi Brinquedos">
<div class="titulo"><h1>{html.escape(titulo)}</h1><p class="sub">Central de Chamados de TI · {html.escape(subtitulo)}</p></div>
<span class="selo">TI Dorémi</span>
</header>
<main>
{corpo}
</main>
<footer><span>Central de Chamados de TI · Dorémi Brinquedos</span><span>Versão de {data}</span></footer>
</div>
</body>
</html>
"""


def main():
    logo = base64.b64encode(LOGO.read_bytes()).decode()
    hoje = date.today().strftime("%d/%m/%Y")
    for nome, (titulo, sub) in MANUAIS.items():
        md = (PASTA / nome).read_text(encoding="utf-8")
        destino = PASTA / nome.replace(".md", ".html")
        destino.write_text(pagina(titulo, sub, converter(md), logo, hoje), encoding="utf-8")
        print(f"Gerado: {destino}")


if __name__ == "__main__":
    main()
