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
    existentes = {s["name"]: s["id"] for s in glpi.listar("SLA")}
    por_prioridade = {}
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
    """Na abertura: categoria → prioridade e tipo; "impede de vender" (urgência Muito alta) → Crítica;
    depois prioridade → prazos do SLA (também quando o TI muda a prioridade). A ordem de criação é a ordem de execução."""
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
    regra(glpi, regras_atuais, crit, acts, "Impede de vender ou trabalhar = Crítica", "AND", ao_abrir,
          [("urgency", 0, 5)], [("assign", "priority", PRIORIDADE["Crítica"])])
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


def tarefas(glpi):
    """Tarefas automáticas ativas em modo CLI: o cron do servidor roda a cada minuto (e-mails, SLA, fechamento
    automático), mesmo sem ninguém navegando no GLPI. No modo interno elas só rodam com alguém usando a tela."""
    print("Tarefas automáticas:")
    for t in glpi._pedir("GET", "/CronTask?range=0-500"):
        if t["state"] == 1 and t["mode"] == 1:
            print(f"  + {t['name']}: modo CLI")
            if APLICAR:
                glpi._pedir("PUT", f"/CronTask/{t['id']}", {"input": {"mode": 2}})


def painel(glpi):
    """Tela principal com o painel de Assistência (só chamados), não o geral com inventário e fornecedores."""
    print("Painel da tela principal:")
    atual = [c["value"] for c in glpi._pedir("GET", "/Config?range=0-3000") if c["name"] == "default_dashboard_central"]
    if atual != ["assistance"]:
        print("  + painel padrão: Assistência")
        if APLICAR:
            try:  # o GLPI grava o valor, mas responde erro porque a linha principal da configuração não muda
                glpi._pedir("PUT", "/Config/1", {"input": {"id": 1, "default_dashboard_central": "assistance"}})
            except SystemExit:
                pass


def perfis(glpi):
    """O perfil Observador (vê todos os chamados e aprova, sem alterar) passa a ver também o painel (dashboard)."""
    print("Perfis:")
    obs = next(p["id"] for p in glpi.listar("Profile") if p["name"] == "Observer")
    for direito in glpi._pedir("GET", f"/Profile/{obs}/ProfileRight?range=0-999"):
        if direito["name"] == "dashboard" and not int(direito["rights"]) & 1:
            print("  + Observador: ver o painel")
            if APLICAR:
                glpi._pedir("PUT", f"/ProfileRight/{direito['id']}", {"input": {"rights": int(direito["rights"]) | 1}})


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
        tarefas(glpi)
        painel(glpi)
        formulario(glpi)
    finally:
        glpi.sair()
    print("Pronto.")


if __name__ == "__main__":
    main()
