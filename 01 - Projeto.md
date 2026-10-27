# Central de Chamados de TI · Dorémi

> Status: **proposta para aprovação**. Nada é instalado antes do "ok" do responsável (TI).
> Itens marcados com **[DECIDIR]** precisam de resposta.

---

## 1. Objetivo

Organizar os pedidos de TI que hoje chegam soltos (WhatsApp, telefone, corredor):

- Toda solicitação vira um **chamado numerado**, com loja, categoria, prioridade e prazo.
- As lojas abrem e acompanham os chamados num **portal web**, pelo PC ou pelo celular.
- O TI atende por um **painel**: fila organizada, histórico e respostas.
- A diretoria recebe **relatórios**: volume, prazos (SLA), satisfação e problemas que se repetem.

---

## 2. Como funciona

```
Loja (navegador)                          TI (painel)
┌────────────────────────┐                ┌──────────────────────────┐
│ Login da loja          │                │ Fila de chamados         │
│ Novo chamado:          │  ───────────►  │ Prioridade e prazo (SLA) │
│ categoria, descrição,  │                │ Responde, muda status    │
│ foto                   │  ◄───────────  │ Painéis e relatórios     │
│ Acompanha o status     │   resposta     └──────────────────────────┘
│ Dá a nota no final     │   + e-mail
└────────────────────────┘
```

- **Endereço:** https://chamados.example.com (decisão 3).
- **Onde roda:** no servidor da matriz, isolado do SmartStock.
- **Opcional:** abrir chamado também **por e-mail** (`suporte@...`), que vira chamado sozinho.

**[DECIDIR]** Ferramenta:

| | GLPI | Sistema próprio |
|---|---|---|
| O que é | Sistema de chamados livre e grátis, que o TI já conhece | Feito sob medida, na mesma base técnica do SmartStock |
| Portal da loja, SLA, satisfação, relatórios | Já vêm prontos | Construídos por nós |
| Prazo | Dias | Semanas |
| Do nosso jeito | Limitado ao que o GLPI permite | Total |

---

## 3. Quem abre chamado

| Grupo | Exemplos |
|---|---|
| **Lojas** | Cada loja tem o seu login (Matriz, Loja B, Loja I, Loja E, Loja H…) |
| **Diretoria** | Diretores e gerência geral |
| **Administrativo** | Financeiro, RH, Compras, Fiscal |
| **Depósito** | Depósito central / logística |
| **E-commerce** | Equipe da loja virtual |

**[DECIDIR]** Um login por **loja** (compartilhado pela equipe da loja) ou um login por **pessoa**? Por pessoa dá mais rastreabilidade; por loja é mais simples.

---

## 4. Tipos de chamado (categorias)

Estrutura definida pelo responsável em 23/10/2026 (decisões 26 a 29): **14 categorias e 253 problemas**, iguais para as 12 lojas e o CD. A lista completa, com tipo e prioridade padrão de cada problema, fica em [`config/categorias.tsv`](config/categorias.tsv), que é também a fonte usada para criar as categorias no GLPI.

| Categoria | Grupos |
|---|---|
| Geral / Outros | — |
| Computadores e Hardware | Computador · Periféricos · Manutenção e equipamentos |
| Impressoras | Funcionamento · Qualidade e configuração · Rede e manutenção |
| E-mail | — |
| Relógio de Ponto | Equipamento e funcionamento · Sistema e documentos |
| Frente de Caixa (PDV) | Sistema de Frente de Caixa · TEF · POS · Pinpad · Troca e movimentação de equipamentos de pagamento · Periféricos do Caixa · Sincronização de Dados |
| Administrativo | Sistema · Notas Fiscais e Faturamento · Estoque e Produtos · Etiquetas · Relatórios · Cadastros e Permissões |
| Rede e Internet | — |
| Acessos e Usuários | Criação e alteração de usuários · Bloqueio e recuperação |
| SmartStock | — |
| Sistemas e Aplicativos | — |
| Telefonia | — |
| Solicitações e Melhorias | — |
| Segurança da Informação | — |

- A **unidade** (loja ou CD) é um campo separado da categoria.
- No formulário, a loja responde: *"Isso está impedindo de vender ou de trabalhar?"*. Se sim, o chamado vira **Crítico**. O TI pode mudar a prioridade a qualquer momento, e a mudança fica registrada.
- Perguntas de todos os chamados e as de cada tipo (número do caixa na Frente de Caixa, modelo e mensagem nas Impressoras, dados do colaborador na criação de usuário) ficam em [`config/campos.tsv`](config/campos.tsv) (decisão 30).

---

## 5. SLA (prazos)

Prazos ajustados em 23/10/2026 (decisões 36 e 45); arquivo `config/sla.tsv`.

| Prioridade | Quando | 1ª resposta | Solução |
|---|---|---|---|
| **Crítica** | Venda ou trabalho parado | 30 min | 4 h |
| **Alta** | Caixa, ERP ou internet com problema, sem parar tudo | 2 h | 2 dias úteis |
| **Normal** | Computador, impressora, e-mail, acessos | 1 dia útil | 3 dias úteis |
| **Baixa** | Pedidos, instalações, dúvidas | 2 dias úteis | 10 dias úteis |

- O prazo conta **só no horário de atendimento do TI**. **[DECIDIR]** Horário (sugestão: seg–sex 08:00–18:00, sáb 08:00–12:00).
- Chamado **Pendente** (esperando a loja ou um fornecedor) **pausa o prazo**.
- Com **80% do prazo** gasto, o TI recebe um aviso. Prazo estourado fica destacado e entra no relatório.

---

## 6. Ciclo do chamado

```
Novo ──► Em atendimento ──► Pendente (pausa o SLA) ──► Solucionado ──► Fechado
               ▲                    │                       │
               └────────────────────┘                       └─ loja diz "não resolveu" → reabre
```

- A cada mudança, a loja vê no portal e recebe **e-mail**.
- Ao solucionar, a loja confirma e dá uma **nota de 1 a 5**, com comentário opcional.
- Se a loja não responder em 48 h, o chamado fecha sozinho.

---

## 7. Relatórios e painéis

**Painel do TI:** abertos por prioridade, SLA perto de estourar ou estourado, pendentes há mais de 24 h, fila do dia.

**Painel gerencial (diretoria):**

| Indicador | Detalhe |
|---|---|
| Abertos × fechados | Por dia, semana e mês |
| **SLA cumprido (%)** | 1ª resposta e solução, por prioridade |
| Tempo médio | De 1ª resposta e de solução |
| **Satisfação** | Nota média e % de notas 4–5 |
| Por loja e por categoria | Quem mais abre chamado e de quê |
| **Reincidência** | Mesmo problema na mesma loja mais de 3 vezes em 30 dias |
| Reabertos | Chamados que voltaram depois de solucionados |

**Relatório mensal automático** por e-mail no dia 1º, com PDF e Excel. **[DECIDIR]** Quem recebe.

---

## 8. Segurança

- **Na internet, só o portal.** O servidor só responde a `chamados.example.com` para quem vem de fora; o SmartStock continua só pela rede interna e pela VPN.
- **HTTPS** com certificado válido e renovação automática.
- **Login** de cada loja ou pessoa, senha forte e bloqueio após tentativas erradas. O painel do TI pode ficar restrito à rede interna e à VPN.
- **Backup diário** do banco de chamados no HD de backup do servidor.
- **LGPD:** só dados de trabalho (loja, pessoa, descrição do problema). Senhas trocadas nunca são escritas no chamado.

---

## 9. O que é preciso

| # | Item | Responsável |
|---|---|---|
| 1 | Registro **A `chamados` → 203.0.113.10** (era 203.0.113.10 até a troca do modem, decisão 49) no Editor de Zona do cPanel | TI |
| 2 | Confirmar com a operadora que o IP é **fixo** | TI |
| 3 | No modem: portas **80 e 443** → 192.168.1.10 | TI |
| 4 | Decisões da seção 10 | TI |
| 5 | Instalação e configuração no servidor | Claude (scripts) + TI (rodar) |
| 6 | Memória RAM do servidor (recomendado) | TI |

---

## 10. Fases

| Fase | Entrega |
|---|---|
| **1. Portal no ar** | Ferramenta instalada, endereço com HTTPS, categorias, SLA, horário e logins das lojas |
| **2. Uso real** | Duas semanas com as lojas abrindo chamados; ajuste de categorias, prazos e textos |
| **3. Relatórios** | Painel gerencial e relatório mensal automático |

## 11. Decisões pendentes

1. Ferramenta: **GLPI** ou **sistema próprio**?
2. Login por **loja** ou por **pessoa**?
3. Categorias e prazos (seções 4 e 5) estão bons?
4. Horário de atendimento do TI.
5. Quem recebe o relatório mensal.
6. Lista das lojas e setores (e das pessoas, se for login por pessoa).
