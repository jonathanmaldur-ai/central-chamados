#!/usr/bin/env python3
"""Configura o GLPI a partir dos arquivos config/*.tsv, pela API do próprio servidor (decisão 32).

    python3 ~/central-chamados/scripts/servidor/configurar-glpi.py            # simulação: só mostra
    python3 ~/central-chamados/scripts/servidor/configurar-glpi.py --aplicar  # cria no GLPI

Só cria o que ainda não existe (procura pelo nome), então pode rodar quantas vezes quiser: para incluir uma
categoria nova, basta acrescentar a linha no config/categorias.tsv e rodar de novo. Não apaga nada que tenha sido
criado na tela; a única coisa que ele ajusta são as regras com nome "[Central] ...", que ele mesmo mantém.
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

    def apagar(self, tipo, ident):
        self._pedir("DELETE", f"/{tipo}/{ident}?force_purge=1")

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


PRIORIDADE = {"Baixa": 2, "Normal": 3, "Alta": 4, "Crítica": 6}  # nomes no GLPI: Baixa, Média, Alta, Crítica
TIPO = {"Incidente": 1, "Requisição": 2}
DIAS = {"Domingo": 0, "Segunda": 1, "Terça": 2, "Quarta": 3, "Quinta": 4, "Sexta": 5, "Sábado": 6}
CALENDARIO = "Horário do TI"
SLM_NOME = "Atendimento do TI"


def calendario(glpi):
    """Calendário com o horário do TI e os feriados. Devolve o id."""
    print("Horário e feriados:")
    cals = {c["name"]: c["id"] for c in glpi.listar("Calendar")}
    cal = garantir(glpi, "Calendar", cals, CALENDARIO, {"name": CALENDARIO, "entities_id": 0, "is_recursive": 1},
                   f"Calendário {CALENDARIO}")
    segs = {(s["calendars_id"], s["day"], s["begin"][:5], s["end"][:5]): s["id"] for s in glpi.listar("CalendarSegment")}
    for h in ler_tsv("horario.tsv"):
        chave = (cal, DIAS[h["Dia"]], h["Início"], h["Fim"])
        garantir(glpi, "CalendarSegment", segs, chave,
                 {"calendars_id": cal, "day": DIAS[h["Dia"]], "begin": h["Início"] + ":00", "end": h["Fim"] + ":00",
                  "entities_id": 0, "is_recursive": 1}, f"{h['Dia']} {h['Início']}–{h['Fim']}")
    feriados = {f["name"]: f["id"] for f in glpi.listar("Holiday")}
    ligados = {(l["calendars_id"], l["holidays_id"]) for l in glpi.listar("Calendar_Holiday")}
    for f in ler_tsv("feriados.tsv"):
        fid = garantir(glpi, "Holiday", feriados, f["Nome"],
                       {"name": f["Nome"], "begin_date": f["Data"], "end_date": f["Data"],
                        "is_perpetual": int(f["Anual"] == "Sim"), "entities_id": 0, "is_recursive": 1},
                       f"Feriado {f['Data']} {f['Nome']}")
        if APLICAR and (cal, fid) not in ligados:
            glpi.criar("Calendar_Holiday", {"calendars_id": cal, "holidays_id": fid})
            ligados.add((cal, fid))
    return cal


def slas(glpi, cal):
    """SLM com um prazo de 1ª resposta (TTO) e um de solução (TTR) por prioridade. Devolve {prioridade GLPI: (tto, ttr)}."""
    print("SLA:")
    slms = {s["name"]: s["id"] for s in glpi.listar("SLM")}
    slm = garantir(glpi, "SLM", slms, SLM_NOME,
                   {"name": SLM_NOME, "calendars_id": cal, "use_ticket_calendar": 0, "entities_id": 0, "is_recursive": 1},
                   f"SLM {SLM_NOME}")
    todos = glpi.listar("SLA")
    existentes = {s["name"]: s["id"] for s in todos}
    por_prioridade = {}

    def ajustar(prefixo, tipo, nome, numero, glpi_unidade):
        """Já existe o prazo desta prioridade com outro valor? Atualiza o mesmo SLA (os chamados abertos seguem com ele)."""
        for s in todos:
            if s["type"] == tipo and s["name"].startswith(prefixo) and s["name"] != nome:
                print(f"  ~ {s['name']} → {nome}")
                if APLICAR:
                    glpi._pedir("PUT", f"/SLA/{s['id']}", {"input": {"name": nome, "number_time": numero,
                                                                    "definition_time": glpi_unidade}})
                existentes[nome] = s["id"]
    # Unidade no arquivo em português; o GLPI grava em inglês. Rótulo curto para o nome do prazo.
    unidade = {"minuto": ("minute", "{} min"), "hora": ("hour", "{} h"), "dia": ("day", "{} dia(s) útil(eis)")}

    def prazo(numero, nome_unidade):
        glpi_unidade, rotulo = unidade[nome_unidade]
        return int(numero), glpi_unidade, rotulo.format(numero)

    for l in ler_tsv("sla.tsv"):
        n_tto, u_tto, r_tto = prazo(l["1ª resposta"], l["Unidade da resposta"])
        n_ttr, u_ttr, r_ttr = prazo(l["Solução"], l["Unidade da solução"])
        tto_nome = f"{l['Prioridade']}: 1ª resposta em {r_tto}"
        ttr_nome = f"{l['Prioridade']}: solução em {r_ttr}"
        base = {"slms_id": slm, "calendars_id": cal, "use_ticket_calendar": 0, "end_of_working_day": 0,
                "entities_id": 0, "is_recursive": 1}
        ajustar(f"{l['Prioridade']}: 1ª resposta", 1, tto_nome, n_tto, u_tto)
        ajustar(f"{l['Prioridade']}: solução", 0, ttr_nome, n_ttr, u_ttr)
        tto = garantir(glpi, "SLA", existentes, tto_nome,
                       {**base, "name": tto_nome, "type": 1, "number_time": n_tto, "definition_time": u_tto}, tto_nome)
        ttr = garantir(glpi, "SLA", existentes, ttr_nome,
                       {**base, "name": ttr_nome, "type": 0, "number_time": n_ttr, "definition_time": u_ttr}, ttr_nome)
        por_prioridade[int(l["Prioridade GLPI"])] = (tto, ttr)
    return por_prioridade


def regra(glpi, regras, criterios_todos, acoes_todas, nome, match, condicao, criterios, acoes):
    """Mantém a regra "[Central] nome" com exatamente estes critérios e ações (acrescenta e remove o que mudou)."""
    nome = f"[Central] {nome}"
    rid = garantir(glpi, "RuleTicket", regras, nome,
                   {"name": nome, "sub_type": "RuleTicket", "match": match, "condition": condicao, "is_active": 1,
                    "entities_id": 0, "is_recursive": 1}, f"Regra {nome}")
    if rid is None:  # simulação de regra nova
        return
    for tabela, desejados, atuais, campos in (
        ("RuleCriteria", criterios, criterios_todos, ("criteria", "condition", "pattern")),
        ("RuleAction", acoes, acoes_todas, ("action_type", "field", "value")),
    ):
        tem = {tuple(str(a[c]) for c in campos): a["id"] for a in atuais if a["rules_id"] == rid}
        quer = {tuple(str(v) for v in d) for d in desejados}
        for d in quer - tem.keys():
            print(f"    + {nome}: {tabela} {d}")
            if APLICAR:
                glpi.criar(tabela, {"rules_id": rid, **dict(zip(campos, d))})
        for d in tem.keys() - quer:
            print(f"    - {nome}: {tabela} {d}")
            if APLICAR:
                glpi.apagar(tabela, tem[d])


def regras(glpi, prazos):
    """Na abertura: categoria → prioridade e tipo; "impede de vender" (urgência Muito alta) sobe um nível;
    depois prioridade → prazos do SLA (também quando o TI muda a prioridade). Cada regra vê o resultado da anterior,
    então a ordem importa: ORDEM, no fim, fixa a sequência das regras "[Central]"."""
    print("Regras de negócio:")
    ao_abrir, ao_abrir_e_atualizar = 1, 3
    linhas = ler_tsv("categorias.tsv")
    cats = {c["completename"]: c["id"] for c in glpi.listar("ITILCategory")}
    regras_atuais = {r["name"]: r["id"] for r in glpi.listar("RuleTicket")}
    crit = glpi.listar("RuleCriteria")
    acts = glpi.listar("RuleAction")

    def caminho(l):
        return " > ".join(x for x in (l["Categoria"], l["Grupo"], l["Problema"]) if x)

    for nome_pri, valor in PRIORIDADE.items():
        ids = [cats.get(caminho(l)) for l in linhas if l["Prioridade"] == nome_pri]
        regra(glpi, regras_atuais, crit, acts, f"Prioridade padrão {nome_pri}", "OR", ao_abrir,
              [("itilcategories_id", 0, i) for i in ids if i], [("assign", "priority", valor)])
    for nome_tipo, valor in TIPO.items():
        ids = [cats.get(caminho(l)) for l in linhas if l["Tipo"] == nome_tipo]
        regra(glpi, regras_atuais, crit, acts, f"Tipo {nome_tipo}", "OR", ao_abrir,
              [("itilcategories_id", 0, i) for i in ids if i], [("assign", "type", valor)])
    # O formulário marca urgência "Muito alta" (5) quando a resposta é "impede de vender ou de trabalhar".
    # Sobe só um nível (decisão 36): Alta vira Crítica e, DEPOIS, Normal vira Alta (na ordem inversa, Normal
    # subiria dois níveis). Baixa continua Baixa: dúvida e pedido nunca viram Crítica.
    antigo = "[Central] Impede de vender ou trabalhar = Crítica"
    if antigo in regras_atuais:
        print(f"  ~ {antigo} → [Central] Impede de vender: Alta vira Crítica")
        if APLICAR:
            glpi._pedir("PUT", f"/RuleTicket/{regras_atuais[antigo]}",
                        {"input": {"name": "[Central] Impede de vender: Alta vira Crítica"}})
        regras_atuais["[Central] Impede de vender: Alta vira Crítica"] = regras_atuais.pop(antigo)
    regra(glpi, regras_atuais, crit, acts, "Impede de vender: Alta vira Crítica", "AND", ao_abrir,
          [("urgency", 0, 5), ("priority", 0, PRIORIDADE["Alta"])], [("assign", "priority", PRIORIDADE["Crítica"])])
    regra(glpi, regras_atuais, crit, acts, "Impede de vender: Normal vira Alta", "AND", ao_abrir,
          [("urgency", 0, 5), ("priority", 0, PRIORIDADE["Normal"])], [("assign", "priority", PRIORIDADE["Alta"])])
    for nome_pri, valor in PRIORIDADE.items():
        tto, ttr = prazos[valor]
        if tto is None:  # simulação: o SLA ainda não existe
            print(f"  + Regra [Central] SLA {nome_pri}")
            continue
        regra(glpi, regras_atuais, crit, acts, f"SLA {nome_pri}", "AND", ao_abrir_e_atualizar,
              [("priority", 0, valor)], [("assign", "slas_id_tto", tto), ("assign", "slas_id_ttr", ttr)])
    # A unidade vem do login da loja (cada login tem a sua Localização): a loja não precisa escolher.
    regra(glpi, regras_atuais, crit, acts, "Unidade do solicitante", "AND", ao_abrir,
          [("_locations_id_of_requester", 8, 1)], [("fromuser", "locations_id", 1)])
    # Problemas com Aprovação = Sim vão para aprovação do grupo "Aprovadores" (qualquer membro aprova).
    grupos = {g["name"]: g["id"] for g in glpi.listar("Group")}
    aprovadores = garantir(glpi, "Group", grupos, "Aprovadores",
                           {"name": "Aprovadores", "entities_id": 0, "is_recursive": 1, "is_requester": 1,
                            "is_assign": 0, "comment": "Gestão: aprova equipamentos novos, trocas e melhorias (decisão 35)."},
                           "Grupo Aprovadores")
    ids = [cats.get(caminho(l)) for l in linhas if l.get("Aprovação") == "Sim"]
    if aprovadores is None:
        print("  + Regra [Central] Aprovação da gestão")
    else:
        regra(glpi, regras_atuais, crit, acts, "Aprovação da gestão", "OR", ao_abrir,
              [("itilcategories_id", 0, i) for i in ids if i],
              [("add_validation", "groups_id_validate_any", aprovadores)])
    # A gestão acompanha todo chamado como observadora (decisão 46). Critério "título qualquer" = sempre.
    gestora = next((u["id"] for u in glpi.listar("User") if u["name"] == OBSERVADORA), None)
    if gestora is None:
        print(f"  ! usuário {OBSERVADORA} não existe; regra de observadora não criada")
    else:
        regra(glpi, regras_atuais, crit, acts, "Gestão observa todos os chamados", "AND", ao_abrir,
              [("name", 6, "/.*/")], [("append", "_users_id_observer", gestora)])
        observar_abertos(glpi, gestora)
    ordenar(glpi)


OBSERVADORA = "gestora"


def observar_abertos(glpi, gestora):
    """Coloca a gestora como observadora nos chamados ainda não fechados que não a têm (sem disparar e-mail)."""
    fechado, observador = 6, 3  # CommonITILObject::CLOSED, CommonITILActor::OBSERVER
    ja = {(a["tickets_id"]) for a in glpi._pedir("GET", "/Ticket_User?range=0-9999") or []
          if a["users_id"] == gestora and a["type"] == observador}
    for t in glpi._pedir("GET", "/Ticket?range=0-9999") or []:
        if t["status"] != fechado and t["id"] not in ja:
            print(f"  + chamado {t['id']}: {OBSERVADORA} como observadora")
            if APLICAR:
                glpi.criar("Ticket_User", {"tickets_id": t["id"], "users_id": gestora, "type": observador,
                                           "_disablenotif": True})


ORDEM = ["Prioridade padrão Baixa", "Prioridade padrão Normal", "Prioridade padrão Alta", "Prioridade padrão Crítica",
         "Tipo Incidente", "Tipo Requisição", "Impede de vender: Alta vira Crítica",
         "Impede de vender: Normal vira Alta", "SLA Baixa", "SLA Normal", "SLA Alta", "SLA Crítica",
         "Unidade do solicitante", "Aprovação da gestão", "Gestão observa todos os chamados"]


def ordenar(glpi):
    """Coloca as regras "[Central]" na sequência de ORDEM, a partir da posição da primeira delas."""
    atuais = {r["name"]: r for r in glpi.listar("RuleTicket")}
    nomes = [f"[Central] {n}" for n in ORDEM if f"[Central] {n}" in atuais]
    if not nomes:
        return
    inicio = min(atuais[n]["ranking"] for n in nomes)
    if [atuais[n]["ranking"] for n in nomes] == list(range(inicio, inicio + len(nomes))):
        return
    print("  ~ ordem das regras [Central] ajustada")
    if APLICAR:
        for i, n in enumerate(nomes):
            glpi._pedir("PUT", f"/RuleTicket/{atuais[n]['id']}", {"input": {"ranking": inicio + i}})


def tarefas(glpi):
    """Tarefas automáticas ativas em modo CLI: o cron do servidor roda a cada minuto (e-mails, SLA, fechamento
    automático), mesmo sem ninguém navegando no GLPI. No modo interno elas só rodam com alguém usando a tela."""
    print("Tarefas automáticas:")
    for t in glpi._pedir("GET", "/CronTask?range=0-500"):
        if t["state"] == 1 and t["mode"] == 1:
            print(f"  + {t['name']}: modo CLI")
            if APLICAR:
                glpi._pedir("PUT", f"/CronTask/{t['id']}", {"input": {"mode": 2}})


CONFIG_GERAL = {
    "default_dashboard_central": ("assistance", "tela principal com o painel de Assistência (só chamados)"),
    "names_format": ("1", "nomes como Nome Sobrenome"),
}


def config_geral(glpi):
    """Configurações gerais do GLPI (Configurar → Geral)."""
    print("Configurações gerais:")
    atuais = {c["name"]: c.get("value") for c in glpi._pedir("GET", "/Config?range=0-3000") if c.get("context") == "core"}
    for nome, (valor, rotulo) in CONFIG_GERAL.items():
        if atuais.get(nome) != valor:
            print(f"  ~ {rotulo}")
            if APLICAR:
                try:  # o GLPI grava o valor, mas responde erro porque a linha principal da configuração não muda
                    glpi._pedir("PUT", "/Config/1", {"input": {"id": 1, nome: valor}})
                except SystemExit:
                    pass


# Perfis do GLPI com nomes em português, pensados nos cargos da Dorémi (decisão 37). Chave: nome original do GLPI.
PERFIS = {
    "Self-Service": "Loja / Solicitante",
    "Observer": "Gestão (aprovação)",
    "Technician": "Técnico de TI",
    "Supervisor": "Supervisor de TI",
    "Super-Admin": "Administrador geral",
    "Admin": "Administrador",
    "Hotliner": "Atendente (1º nível)",
    "Read-Only": "Somente leitura",
}


def notificacoes(glpi):
    """Pesquisa de satisfação (decisão 43): o convite vai só para quem abriu o chamado (a loja avalia) e as
    respostas só para o perfil de Gestão; o TI (administrador e técnico) não recebe nenhum dos dois."""
    print("Avisos da pesquisa de satisfação:")
    usuario, perfil = 1, 2                  # Notification::USER_TYPE, Notification::PROFILE_TYPE
    autor = 3                               # Notification::AUTHOR = quem abriu o chamado
    gestao = next(p["id"] for p in glpi.listar("Profile") if p["name"] == PERFIS["Observer"])
    desejado = {"satisfaction": {(usuario, autor)}, "replysatisfaction": {(perfil, gestao)}}
    alvos = glpi.listar("NotificationTarget")
    for n in glpi.listar("Notification"):
        if n["itemtype"] != "Ticket" or n["event"] not in desejado:
            continue
        tem = {(a["type"], a["items_id"]): a["id"] for a in alvos if a["notifications_id"] == n["id"]}
        quer = desejado[n["event"]]
        for tipo, item in quer - tem.keys():
            print(f"  + {n['name']}: destinatário {tipo}/{item}")
            if APLICAR:
                glpi.criar("NotificationTarget", {"notifications_id": n["id"], "type": tipo, "items_id": item})
        for chave in tem.keys() - quer:
            print(f"  - {n['name']}: destinatário {chave[0]}/{chave[1]}")
            if APLICAR:
                glpi.apagar("NotificationTarget", tem[chave])


def entidade(glpi):
    """Pesquisa de satisfação (nota de 1 a 5, enviada ao solucionar) e fechamento automático 2 dias (48 h) depois."""
    print("Satisfação e fechamento automático:")
    desejado = {"autoclose_delay": 2, "inquest_config": 1, "inquest_rate": 100, "inquest_delay": 0,
                "inquest_max_rate": 5}
    atual = glpi._pedir("GET", "/Entity/0")
    muda = {k: v for k, v in desejado.items() if atual.get(k) != v}
    if muda:
        print(f"  ~ entidade raiz: {muda}")
        if APLICAR:
            glpi._pedir("PUT", "/Entity/0", {"input": muda})


ADD_AS_OBSERVER = 16384  # ITILFollowup::ADD_AS_OBSERVER
GESTAO_SEM = 8 | 16 | 32768  # DELETE, PURGE e Ticket::OWN


def perfis(glpi):
    """Nomes em português e o perfil de Gestão (vê todos os chamados e aprova, sem alterar) vendo também o painel."""
    print("Perfis:")
    todos = glpi.listar("Profile")
    for p in todos:
        novo = PERFIS.get(p["name"])
        if novo:
            print(f"  ~ perfil {p['name']} → {novo}")
            if APLICAR:
                glpi._pedir("PUT", f"/Profile/{p['id']}", {"input": {"name": novo}})
            p["name"] = novo
    obs = next(p["id"] for p in todos if p["name"] == PERFIS["Observer"])
    for direito in glpi._pedir("GET", f"/Profile/{obs}/ProfileRight?range=0-999"):
        if direito["name"] in ("dashboard", "logs") and not int(direito["rights"]) & 1:
            # Painel e aba Histórico (quem mudou status, prioridade ou técnico), só leitura.
            print(f"  + Observador: ver {'o painel' if direito['name'] == 'dashboard' else 'o histórico'}")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}", {"input": {"rights": int(direito["rights"]) | 1}})
        # A Gestão vê e aprova, não altera (decisão 35): sem apagar, eliminar nem assumir chamados.
        if direito["name"] == "ticket" and int(direito["rights"]) & GESTAO_SEM:
            print("  - Gestão: apagar, eliminar e assumir chamados")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}",
                            {"input": {"rights": int(direito["rights"]) & ~GESTAO_SEM}})
        # Como observadora de todos os chamados (decisão 46), a Gestão pergunta e comenta no próprio chamado.
        if direito["name"] == "followup" and not int(direito["rights"]) & ADD_AS_OBSERVER:
            print("  + Gestão: responder nos chamados em que é observadora")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}",
                            {"input": {"rights": int(direito["rights"]) | ADD_AS_OBSERVER}})
    # Quem atende não vê as avaliações (decisão 44): o Técnico de TI fica sem Estatísticas (onde está a média de
    # satisfação); a nota no fim do chamado o plugin "doremi" esconde para esse perfil.
    tecnico = next(p["id"] for p in todos if p["name"] == PERFIS["Technician"])
    mudar_prioridade = 65536  # Ticket::CHANGEPRIORITY: o TI corrige um "Crítico" que não é (decisão 36)
    for direito in glpi._pedir("GET", f"/Profile/{tecnico}/ProfileRight?range=0-999"):
        if direito["name"] == "statistic" and int(direito["rights"]) != 0:
            print("  - Técnico de TI: estatísticas")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}", {"input": {"rights": 0}})
        if direito["name"] == "dashboard" and not int(direito["rights"]) & 1:
            # O painel de Assistência não tem quadros de satisfação: o técnico pode ver (decisão 47).
            print("  + Técnico de TI: ver o painel")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}", {"input": {"rights": int(direito["rights"]) | 1}})
        if direito["name"] == "ticket" and not int(direito["rights"]) & mudar_prioridade:
            print("  + Técnico de TI: mudar a prioridade do chamado")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}",
                            {"input": {"rights": int(direito["rights"]) | mudar_prioridade}})


# Formulário de abertura das lojas (decisões 30, 31 e 34): config/campos.tsv traduzido para o formulário do GLPI 11.
FORM_NOME = "Abrir chamado"
F = "Glpi\\Form\\"
TIPOS = {
    "curto": F + "QuestionType\\QuestionTypeShortText",
    "longo": F + "QuestionType\\QuestionTypeLongText",
    "numero": F + "QuestionType\\QuestionTypeNumber",
    "lista": F + "QuestionType\\QuestionTypeDropdown",
    "opcoes": F + "QuestionType\\QuestionTypeRadio",
    "categoria": F + "QuestionType\\QuestionTypeItemDropdown",
    "anexo": F + "QuestionType\\QuestionTypeFile",
}


def uid(texto):
    """uuid estável a partir de um texto (rodar de novo gera os mesmos)."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "central-chamados/" + texto))


def tag_resposta(qid, nome):
    return ('<span data-form-tag="true" data-form-tag-value="%d" data-form-tag-provider="Glpi\\Form\\Tag\\AnswerTagProvider" '
            'class="border-teal border-start border-3 bg-dark-lt">#Resposta: %s</span>' % (qid, nome))


def formulario(glpi):
    """Cria o formulário "Abrir chamado" se ainda não existir. Para mudar depois: apagar na tela e rodar de novo."""
    import urllib.parse
    print("Formulário das lojas:")
    tipo = lambda t: urllib.parse.quote(F + t, safe="")
    if any(f["name"] == FORM_NOME for f in glpi._pedir("GET", f"/{tipo('Form')}?range=0-200")):
        print(f"  já existe \"{FORM_NOME}\" (para recriar com mudanças: apagar na tela e rodar de novo).")
        return
    linhas = ler_tsv("categorias.tsv")
    grupos = list(dict.fromkeys(l["Categoria"] + (" > " + l["Grupo"] if l["Grupo"] else "") for l in linhas))
    if not APLICAR:
        print(f"  + Formulário \"{FORM_NOME}\": {len(grupos)} grupos, {len(grupos)} listas de problema e as perguntas de config/campos.tsv")
        return
    cats = {c["completename"]: c["id"] for c in glpi.listar("ITILCategory")}

    form = glpi.criar(tipo("Form"), {
        "name": FORM_NOME, "entities_id": 0, "is_recursive": 1, "is_active": 1, "is_draft": 0, "is_pinned": 1,
        "header": "<p>Conte o que aconteceu. O TI recebe na hora e você acompanha por aqui.</p>",
        "description": "Problemas e pedidos de TI das lojas e do CD.",
        # Sem a seção e o destino padrão do GLPI: o destino padrão abriria um segundo chamado.
        "_init_sections": False, "_init_destinations": False,
    })
    sec_uuid = uid("secao-principal")
    sec = glpi.criar(tipo("Section"), {"forms_forms_id": form, "uuid": sec_uuid, "name": "Chamado", "rank": 0})
    rank = [0]
    ids = {}

    def pergunta(chave, nome, t, obrig=True, extra=None, descricao="", condicoes=None, logica="and"):
        dados = {"forms_sections_id": sec, "forms_sections_uuid": sec_uuid, "uuid": uid("q-" + chave), "name": nome,
                 "type": TIPOS[t], "is_mandatory": int(obrig), "vertical_rank": rank[0], "description": descricao,
                 "extra_data": json.dumps(extra) if extra is not None else None,
                 "visibility_strategy": "visible_if" if condicoes else "",
                 "conditions": json.dumps([{**c, "logic_operator": logica} for c in condicoes] if condicoes else [])}
        rank[0] += 1
        ids[chave] = glpi.criar(tipo("Question"), dados)
        return ids[chave]

    def se(chave, valor, op="equals"):
        return {"item": "question-" + uid("q-" + chave), "item_uuid": uid("q-" + chave), "item_type": "question",
                "value_operator": op, "value": valor}

    def lista(opcoes):
        return {"options": {uid("op-" + o): o for o in opcoes}, "is_multiple_dropdown": False}

    pergunta("quem", "Quem está abrindo o chamado?", "curto")
    pergunta("setor", "Setor", "lista", extra=lista(["Frente de caixa", "Estoque", "Gerência", "Administrativo",
                                                     "Diretoria", "E-commerce", "CD"]))
    pergunta("grupo", "Qual o problema?", "lista", extra=lista(grupos),
             descricao="Digite para pesquisar: caixa, TEF, impressora, internet, senha…")
    for g in grupos:
        pergunta("problema-" + g, "Qual problema exatamente?", "categoria",
                 extra={"itemtype": "ITILCategory", "categories_filter": ["request", "incident", "change", "problem"],
                        "root_items_id": cats[g], "subtree_depth": 1, "selectable_tree_root": False},
                 condicoes=[se("grupo", uid("op-" + g))])

    pdv = [g for g in grupos if g.startswith("Frente de Caixa")]
    troca = next(g for g in grupos if "Troca e movimentação" in g)
    impressoras = [g for g in grupos if g.startswith("Impressoras")]
    criacao_grupo = "Acessos e Usuários > Criação e alteração de usuários"
    criacao = [p for p in ("Criação de usuário do Windows", "Criação de usuário de e-mail",
                           "Criação de usuário do PDV", "Criação de usuário do Administrativo")]
    com_cpf = criacao[2:]

    def problema_e(nome):
        return se("problema-" + criacao_grupo, {"itemtype": "ITILCategory", "items_id": cats[criacao_grupo + " > " + nome]})

    pergunta("caixa", "Qual caixa exatamente? (número do caixa)", "numero",
             condicoes=[se("grupo", uid("op-" + g)) for g in pdv], logica="or")
    pergunta("adquirente", "Adquirente", "lista",
             extra=lista(["Cielo", "Stone", "Rede", "Getnet", "PagBank", "Outra"]), condicoes=[se("grupo", uid("op-" + troca))])
    pergunta("serie", "Número de série do equipamento", "curto", condicoes=[se("grupo", uid("op-" + troca))],
             descricao="O do equipamento com defeito, devolvido ou transferido. Pedido de equipamento novo: escreva \"novo\".")
    pergunta("modelo", "Modelo da impressora", "curto",
             condicoes=[se("grupo", uid("op-" + g)) for g in impressoras], logica="or")
    pergunta("mensagem", "Aparece alguma mensagem? Qual o problema de fato?", "longo",
             condicoes=[se("grupo", uid("op-" + g)) for g in impressoras], logica="or",
             descricao="Copie a mensagem como aparece, ou conte o que a impressora faz.")
    for chave, nome in (("cnome", "Nome completo do colaborador"), ("cfuncao", "Função ou cargo"),
                        ("cunidade", "Unidade do colaborador"), ("cacesso", "Tipo de acesso")):
        pergunta(chave, nome, "curto", condicoes=[problema_e(p) for p in criacao], logica="or")
    pergunta("cpf", "CPF do colaborador (só os 11 números)", "curto", condicoes=[problema_e(p) for p in com_cpf],
             logica="or", descricao="Exigido pelo cadastro no sistema de vendas (decisão 28).")
    pergunta("descricao", "Descreva o que aconteceu", "longo",
             descricao="O que você estava fazendo, o que apareceu na tela, desde quando acontece.")
    pergunta("anexo", "Foto ou print", "anexo", obrig=False)
    impede = lista(["Sim, está parado", "Não, dá para continuar"])
    pergunta("impede", "Isso está impedindo de vender ou de trabalhar?", "opcoes", extra={"options": impede["options"]})

    # Dois destinos: o chamado nasce com urgência Muito alta (5) se impede, senão Média (3).
    # A categoria é o problema exato; prioridade, tipo, prazos e unidade vêm das regras "[Central]".
    sim = uid("op-Sim, está parado")
    for nome, cond, urg in (("Chamado (impede de vender)", "created_if", 5), ("Chamado", "created_unless", 3)):
        config = {
            "glpi-form-destination-commonitilfield-titlefield": {"value": tag_resposta(ids["grupo"], "Qual o problema?")},
            "glpi-form-destination-commonitilfield-contentfield_auto": True,
            "glpi-form-destination-commonitilfield-itilcategoryfield": {"strategy": "last_valid_answer"},
            "glpi-form-destination-commonitilfield-urgencyfield": {"strategy": "specific_value",
                                                                   "specific_urgency_value": urg},
            "glpi-form-destination-commonitilfield-requesttypefield": {"strategy": "specific_value",
                                                                       "specific_request_type": 1},
        }
        glpi.criar(tipo("Destination\\FormDestination"), {
            "forms_forms_id": form, "itemtype": F + "Destination\\FormDestinationTicket", "name": nome,
            "config": json.dumps(config), "creation_strategy": cond,
            "conditions": json.dumps([{**se("impede", sim), "logic_operator": "and"}]),
        })
    print(f"  + Formulário \"{FORM_NOME}\" (id {form}) com {rank[0]} perguntas.")

    # Os dois formulários de exemplo do GLPI ficam desligados: as lojas usam só o da Dorémi.
    for f in glpi._pedir("GET", f"/{tipo('Form')}?range=0-200"):
        if f["name"] in ("Report an issue", "Request a service") and f["is_active"]:
            glpi._pedir("PUT", f"/{tipo('Form')}/{f['id']}", {"input": {"is_active": 0}})
            print(f"  - desligado o formulário de exemplo \"{f['name']}\"")


def inicio_loja(glpi):
    """Tela inicial das lojas: só "Abrir chamado" (o formulário) e "Meus chamados", em português (decisão 41).
    Os atalhos de exemplo do GLPI (catálogo, artigos de ajuda, reserva e os formulários de exemplo) saem."""
    import urllib.parse
    print("Tela inicial das lojas:")
    q = lambda t: urllib.parse.quote("Glpi\\Helpdesk\\Tile\\" + t, safe="")
    form = next((f["id"] for f in glpi._pedir("GET", "/" + urllib.parse.quote(F + "Form", safe="") + "?range=0-200")
                 if f["name"] == FORM_NOME), None)
    if form is None:
        print("  formulário ainda não existe; rode de novo depois de criá-lo.")
        return
    paginas = {t["id"]: t for t in glpi._pedir("GET", f"/{q('GlpiPageTile')}?range=0-50")}
    formtiles = {t["id"]: t for t in glpi._pedir("GET", f"/{q('FormTile')}?range=0-50")}
    ligados = [i for i in glpi._pedir("GET", f"/{q('Item_Tile')}?range=0-50")
               if i["itemtype_item"] == "Entity" and i["items_id_item"] == 0]
    manter = {}
    for i in ligados:
        tipo = i["itemtype_tile"].split("\\")[-1]
        if tipo == "FormTile" and "form" not in manter:
            manter["form"] = i
        elif tipo == "GlpiPageTile" and paginas.get(i["items_id_tile"], {}).get("page") == "tickets":
            manter["meus"] = i
    for i in ligados:
        if i not in manter.values():
            print(f"  - atalho {i['itemtype_tile'].split(chr(92))[-1]} {i['items_id_tile']}")
            if APLICAR:
                glpi._pedir("DELETE", f"/{q('Item_Tile')}/{i['id']}?force_purge=1")
    if formtiles.get(manter.get("form", {}).get("items_id_tile"), {}).get("forms_forms_id") != form:
        # Trocar o formulário de um quadro existente a API não deixa; criar um quadro novo na entidade raiz deixa
        # (ele já entra ligado à tela), e o quadro antigo sai.
        print(f"  + quadro do formulário \"{FORM_NOME}\"")
        if APLICAR:
            glpi.criar(q("FormTile"), {"forms_forms_id": form, "_itemtype_item": "Entity", "_items_id_item": 0})
            if "form" in manter:
                glpi._pedir("DELETE", f"/{q('Item_Tile')}/{manter['form']['id']}?force_purge=1")
            ligados = [i for i in glpi._pedir("GET", f"/{q('Item_Tile')}?range=0-50")
                       if i["itemtype_item"] == "Entity" and i["items_id_item"] == 0]
            manter["form"] = next(i for i in ligados if i["itemtype_tile"].endswith("FormTile"))
    if "meus" in manter and paginas[manter["meus"]["items_id_tile"]]["title"] != "Meus chamados":
        print("  ~ atalho \"Meus chamados\"")
        if APLICAR:
            glpi._pedir("PUT", f"/{q('GlpiPageTile')}/{manter['meus']['items_id_tile']}", {"input": {
                "title": "Meus chamados",
                "description": "Acompanhe os chamados abertos pela loja e responda ao TI."}})
    for rank, chave in ((1, "form"), (2, "meus")):
        if chave in manter and manter[chave]["rank"] != rank and APLICAR:
            glpi._pedir("PUT", f"/{q('Item_Tile')}/{manter[chave]['id']}", {"input": {"rank": rank}})


SENHA_TEXTO = """Olá, ##user.firstname## ##user.realname##.

{abertura}

Seu login: ##user.name##

Para {acao}, abra o link abaixo (vale por 1 dia):
##user.{url}##

Endereço da Central: https://chamados.example.com
Dúvidas: fale com o TI."""

SENHA_HTML = """<p>Olá, <strong>##user.firstname## ##user.realname##</strong>.</p>
<p>{abertura}</p>
<p>Seu login: <strong>##user.name##</strong></p>
<p>Para {acao}, abra o link abaixo (vale por 1 dia):<br>
<a href="##user.{url}##">##user.{url}##</a></p>
<p>Endereço da Central: <a href="https://chamados.example.com">https://chamados.example.com</a><br>
Dúvidas: fale com o TI.</p>"""

SENHA_MODELOS = {
    "Password Initialization": dict(
        assunto="Central de Chamados Dorémi: crie a sua senha",
        abertura="Seu acesso à Central de Chamados de TI da Dorémi foi criado.",
        acao="criar a sua senha", url="passwordiniturl"),
    "Password Forget": dict(
        assunto="Central de Chamados Dorémi: defina a sua senha",
        abertura="Recebemos um pedido para definir a senha do seu acesso à Central de Chamados de TI da Dorémi. "
                 "Se não foi você, ignore este e-mail.",
        acao="definir a sua senha", url="passwordforgeturl"),
}


def emails_senha(glpi):
    """E-mails de criar e de redefinir a senha em português e com o login da pessoa."""
    print("E-mails de senha:")
    for t in glpi.listar("NotificationTemplate"):
        m = SENHA_MODELOS.get(t["name"]) if t["itemtype"] == "User" else None
        if not m:
            continue
        quer = {"subject": m["assunto"],
                "content_text": SENHA_TEXTO.format(**m),
                "content_html": SENHA_HTML.format(**m)}
        for tr in glpi._pedir("GET", f"/NotificationTemplate/{t['id']}/NotificationTemplateTranslation"):
            if any(tr[k] != v for k, v in quer.items()):
                print(f"  ~ {t['name']}: texto em português com o login")
                if APLICAR:
                    glpi._pedir("PUT", f"/NotificationTemplateTranslation/{tr['id']}", {"input": quer})


def main():
    print("APLICANDO no GLPI." if APLICAR else "SIMULAÇÃO: nada será gravado (use --aplicar para criar).")
    glpi = Glpi(ler_chaves())
    try:
        unidades(glpi)
        listas(glpi)
        categorias(glpi)
        cal = calendario(glpi)
        regras(glpi, slas(glpi, cal))
        perfis(glpi)
        entidade(glpi)
        notificacoes(glpi)
        emails_senha(glpi)
        tarefas(glpi)
        config_geral(glpi)
        formulario(glpi)
        inicio_loja(glpi)
    finally:
        glpi.sair()
    print("Pronto.")


if __name__ == "__main__":
    main()
