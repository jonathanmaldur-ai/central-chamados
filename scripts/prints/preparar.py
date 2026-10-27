#!/usr/bin/env python3
"""Logins e chamados de exemplo para tirar os prints dos manuais, sem mandar e-mail a ninguém.

    python3 ~/central-chamados/scripts/prints/preparar.py           # cria
    python3 ~/central-chamados/scripts/prints/preparar.py --limpar  # apaga tudo o que criou

Cria exemplo.loja (Loja / Solicitante, Matriz), exemplo.gestao (Gestão, no grupo Aprovadores) e exemplo.tecnico
(Técnico de TI), sem e-mail e com senha aleatória, e três chamados: um em atendimento com conversa, um esperando
aprovação e um solucionado. Os e-mails do GLPI ficam desligados só enquanto os chamados são criados ou apagados
(a aprovação aberta pelas regras não respeita o _disablenotif) e voltam a ligar mesmo se algo der errado.
Logins, senhas e números ficam em ~/.config/central-chamados/prints.env (600), apagado no --limpar.
"""

import importlib.util
import secrets
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "configurar", Path(__file__).resolve().parents[1] / "servidor/configurar-glpi.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)

ARQUIVO = Path.home() / ".config/central-chamados/prints.env"
MATRIZ = 1  # Localização da Matriz
USUARIOS = {
    "exemplo.loja": ("Loja", "Exemplo", "Loja / Solicitante"),
    "exemplo.gestao": ("Gestão", "Exemplo", "Gestão (aprovação)"),
    "exemplo.tecnico": ("Técnico", "Exemplo", "Técnico de TI"),
}


def conteudo(quem, setor, grupo, problema, extras, descricao, impede):
    """O mesmo formato que o formulário das lojas grava no chamado."""
    linhas = [("Quem está abrindo o chamado?", quem), ("Setor", setor), ("Qual o problema?", grupo),
              ("Qual problema exatamente?", f"{grupo} &gt; {problema}"), *extras,
              ("Descreva o que aconteceu", f"<p>{descricao}</p>"),
              ("Isso está impedindo de vender ou de trabalhar?", impede)]
    return "<p>" + "".join(f"<b>{i}) {p}</b>: {r}<br>" for i, (p, r) in enumerate(linhas, 1)) + "</p>"


CHAMADOS = [
    dict(chave="ATENDIMENTO", grupo="Frente de Caixa (PDV) > Sistema de Frente de Caixa",
         problema="Erro na emissão de NFC-e", tecnico=True,
         texto=conteudo("Ana", "Frente de caixa", "Frente de Caixa (PDV) &gt; Sistema de Frente de Caixa",
                        "Erro na emissão de NFC-e", [("Qual caixa exatamente? (número do caixa)", "3")],
                        "Ao finalizar a venda aparece \"Rejeição 999\" e a nota não sai.", "Não, dá para continuar"),
         conversa=[("exemplo.tecnico", "Bom dia, Ana! Já estou olhando o caixa 3. O erro aparece em todas as vendas "
                                       "ou só em algumas?"),
                   ("exemplo.loja", "Em todas as vendas desde as 9h. Os outros caixas estão vendendo normal.")]),
    dict(chave="APROVACAO", grupo="Computadores e Hardware > Periféricos", problema="Solicitação de troca de mouse",
         texto=conteudo("Carlos", "Estoque", "Computadores e Hardware &gt; Periféricos",
                        "Solicitação de troca de mouse", [],
                        "O mouse do computador do estoque está falhando no clique e o fio está gasto.",
                        "Não, dá para continuar")),
    dict(chave="SOLUCIONADO", grupo="Impressoras > Funcionamento", problema="Impressora não imprime", tecnico=True,
         texto=conteudo("Bruna", "Gerência", "Impressoras &gt; Funcionamento", "Impressora não imprime",
                        [("Modelo da impressora", "Epson L3250"),
                         ("Mensagem que aparece ou o que ela está fazendo", "Fica \"Imprimindo\" e não sai nada")],
                        "Desde ontem nenhum documento sai na impressora da gerência.", "Não, dá para continuar"),
         solucao="Reinstalei o driver da impressora e limpei a fila de impressão. Fiz uma página de teste e saiu "
                 "certinho. Pode conferir?"),
]


def notificacoes(glpi, ligar):
    try:  # o GLPI grava o valor, mas responde erro (ver config_geral em configurar-glpi.py)
        glpi._pedir("PUT", "/Config/1", {"input": {"id": 1, "use_notifications": "1" if ligar else "0"}})
    except SystemExit:
        pass
    valor = next(c["value"] for c in glpi._pedir("GET", "/Config?range=0-3000")
                 if c.get("context") == "core" and c["name"] == "use_notifications")
    if valor != ("1" if ligar else "0"):
        raise SystemExit(f"Não consegui {'ligar' if ligar else 'desligar'} os e-mails do GLPI (use_notifications={valor}).")


def senha():
    return "Ex-" + secrets.token_urlsafe(12) + "9a"


def criar(glpi):
    if ARQUIVO.exists():
        raise SystemExit(f"Já existe {ARQUIVO}: rode com --limpar antes de criar de novo.")
    perfis = {p["name"]: p["id"] for p in glpi.listar("Profile")}
    categorias = {c["completename"]: c["id"] for c in glpi.listar("ITILCategory")}
    aprovadores = next(gr["id"] for gr in glpi.listar("Group") if gr["name"] == "Aprovadores")
    env, ids = {}, {}
    for login, (nome, sobrenome, perfil) in USUARIOS.items():
        s = senha()
        uid = glpi.criar("User", {"name": login, "firstname": nome, "realname": sobrenome, "password": s,
                                  "password2": s, "locations_id": MATRIZ, "is_active": 1,
                                  "_profiles_id": perfis[perfil], "profiles_id": perfis[perfil], "_entities_id": 0, "_is_recursive": 0})
        ids[login] = uid
        env[login.split(".")[1].upper()] = f"{login}:{s}"
        env[f"ID_{login.split('.')[1].upper()}"] = str(uid)
        print(f"  + {login} ({perfil})")
    glpi.criar("Group_User", {"groups_id": aprovadores, "users_id": ids["exemplo.gestao"]})
    ARQUIVO.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
    ARQUIVO.chmod(0o600)

    notificacoes(glpi, False)
    try:
        for c in CHAMADOS:
            dados = {"name": c["grupo"], "content": c["texto"], "itilcategories_id":
                     categorias[f"{c['grupo']} > {c['problema']}"], "locations_id": MATRIZ, "urgency": 3,
                     "_users_id_requester": ids["exemplo.loja"],
                     "users_id_recipient": ids["exemplo.loja"], "_disablenotif": True}
            if c.get("tecnico"):
                dados["_users_id_assign"] = ids["exemplo.tecnico"]
            tid = glpi.criar("Ticket", dados)
            env[c["chave"]] = str(tid)
            for autor, texto in c.get("conversa", []):
                glpi.criar("ITILFollowup", {"itemtype": "Ticket", "items_id": tid, "users_id": ids[autor],
                                            "content": f"<p>{texto}</p>", "_disablenotif": True})
            if c.get("solucao"):
                glpi.criar("ITILSolution", {"itemtype": "Ticket", "items_id": tid, "users_id": ids["exemplo.tecnico"],
                                            "solutiontypes_id": 0, "content": f"<p>{c['solucao']}</p>",
                                            "_disablenotif": True})
            print(f"  + chamado {tid}: {c['problema']}")
    finally:
        ARQUIVO.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
        notificacoes(glpi, True)
    print(f"Pronto. Dados em {ARQUIVO}; depois dos prints: preparar.py --limpar")


def limpar(glpi):
    if not ARQUIVO.exists():
        raise SystemExit("Nada a limpar.")
    env = dict(linha.split("=", 1) for linha in ARQUIVO.read_text().split())
    notificacoes(glpi, False)
    try:
        for c in CHAMADOS:
            if c["chave"] in env:
                glpi._pedir("DELETE", f"/Ticket/{env[c['chave']]}?force_purge=1",
                            {"input": {"id": int(env[c["chave"]]), "_disablenotif": True}})
                print(f"  - chamado {env[c['chave']]}")
    finally:
        notificacoes(glpi, True)
    for login in USUARIOS:
        chave = f"ID_{login.split('.')[1].upper()}"
        if chave in env:
            glpi.apagar("User", env[chave])
            print(f"  - {login}")
    ARQUIVO.unlink()
    print("Pronto: exemplos apagados e e-mails do GLPI ligados.")


def main():
    glpi = cfg.Glpi(cfg.ler_chaves())
    try:
        limpar(glpi) if "--limpar" in sys.argv else criar(glpi)
    finally:
        glpi.sair()


if __name__ == "__main__":
    main()
