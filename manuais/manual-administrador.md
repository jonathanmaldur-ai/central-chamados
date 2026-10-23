# Manual do Administrador

## 1. Acesso

Você administra a Central com o usuário **doremi.ti** (perfil Administrador geral) e atende os chamados com a sua **conta de técnico** (perfil Técnico de TI). A conta de técnico não mostra as avaliações das lojas, que são só da Gestão; o doremi.ti vê tudo, então use-o só para configurar.

| Endereço | Quando usar |
| --- | --- |
| https://chamados.example.com | De qualquer lugar: lojas, celular, fora da empresa. É o endereço que vai nos e-mails. |
| https://192.168.1.10:8443 | Só na rede da Matriz ou pela VPN. Use se o endereço público não abrir dentro da Matriz. |

- **Esqueceu a senha do doremi.ti:** no terminal do servidor, `sudo bash ~/central-chamados/scripts/servidor/definir-senha-glpi.sh` (pede a senha nova duas vezes).
- **Verificação em duas etapas (recomendado):** em **Minhas configurações → Autenticação em duas etapas**, com um aplicativo como o Google Authenticator. Faça o mesmo no usuário da gestora.
- **5 senhas erradas seguidas** de fora da rede bloqueiam o IP por 1 hora. A rede da Matriz e as VPNs nunca são bloqueadas (seção 9).

## 2. Como a Central funciona

A loja abre o chamado pelo formulário **Abrir chamado**; prioridade, tipo, unidade, prazos e aprovação são definidos sozinhos pelas regras **[Central]**.

**O formulário da loja** pergunta: quem está abrindo, setor, "Qual o problema?" (31 grupos com pesquisa), "Qual problema exatamente?" (só os do grupo), perguntas do tipo escolhido, descrição, foto e "Isso está impedindo de vender ou de trabalhar?".

| Pergunta extra | Aparece em |
| --- | --- |
| Número do caixa | Toda a Frente de Caixa |
| Adquirente e número de série | Troca e movimentação de equipamentos de pagamento |
| Modelo da impressora e mensagem | Impressoras |
| Nome, função, unidade e tipo de acesso do colaborador | Criação de usuário |
| CPF do colaborador | Criação de usuário do PDV e do Administrativo |

**O que as regras fazem na abertura, nesta ordem:**

1. **Prioridade e tipo** pelo problema escolhido (Baixa, Normal, Alta ou Crítica; Incidente ou Requisição), conforme `config/categorias.tsv`.
2. **"Impede de vender = Sim" sobe um nível:** Normal vira Alta, Alta vira Crítica, Baixa continua Baixa.
3. **Prazos do SLA** pela prioridade final.
4. **Unidade** vem da Localização do login da loja.
5. **Aprovação** da gestão, nos 18 problemas marcados (seção 4).

**Prazos (SLA)**, contados de segunda a sexta, 08h às 18h, fora dos feriados, e pausados enquanto o chamado está Pendente:

| Prioridade | 1ª resposta | Solução |
| --- | --- | --- |
| Crítica | 30 min | 4 h |
| Alta | 2 h | 2 dias úteis |
| Normal | 1 dia útil | 3 dias úteis |
| Baixa | 2 dias úteis | 10 dias úteis |

Na lista de chamados, **"Tempo para adquirir excedido"** é o prazo de 1ª resposta (assumir o chamado) e **"Tempo para resolver excedido"** o de solução. As colunas "Tempo interno" não são usadas.

## 3. Atender chamados no dia a dia

O primeiro passo em todo chamado é **assumir**: é isso que conta o prazo de 1ª resposta.

**Onde ver a fila:** a tela principal mostra o painel de Assistência (novos, atrasados, pendentes). A lista completa fica em **Assistência → Chamados**; ordene por prioridade ou por data de abertura.

1. **Assumir:** abra o chamado e clique em **Associar a mim** (ou atribua outro técnico no painel da direita). O status vai para "Em atendimento".
2. **Conversar com a loja:** use **Acompanhamento** (a loja recebe por e-mail e responde pelo próprio chamado). Para registrar trabalho seu, com tempo gasto, use **Tarefa**.
3. **Esperando alguém:** mude o status para **Pendente** e escolha o motivo: aguardando solicitante, aguardando fornecedor ou aguardando peça ou equipamento. O prazo do SLA para de contar enquanto estiver pendente.
4. **Resolver:** clique em **Solução**, escolha o tipo (Resolvido remotamente, Resolvido no local, Troca de equipamento, Orientação ao usuário ou Cancelado) e descreva o que foi feito.
5. **Depois de solucionado:** se a loja aceitar a solução, ou depois de 2 dias (48 h) sem resposta, o chamado fecha. Se recusar, ele volta para "Em atendimento". Ao **fechar**, a loja recebe a pesquisa de satisfação (nota de 1 a 5).

**Ajustes que só o TI faz no chamado:**

- **Prioridade errada** (um "Crítico" que não é): mude a **Prioridade** no painel da direita e salve. Os prazos do SLA se ajustam sozinhos e o histórico registra quem mudou.
- **Categoria errada:** mude a **Categoria** no mesmo painel. A prioridade não muda sozinha nesse caso; ajuste-a se for preciso.
- **Cancelar** (aberto por engano ou duplicado): solucione com o tipo **Cancelado**.
- **Duração do chamado:** aba **Estatísticas** (tempo para assumir, para solucionar, para fechar e em espera).

Cada chamado recebe um número sequencial sozinho (o primeiro real não é o nº 1, porque os testes usaram alguns).

## 4. Aprovação da gestão

Equipamento novo, trocas e melhorias só são executados depois que alguém do grupo **Aprovadores** (hoje, a gestora) aprova.

**O que passa por aprovação (18 problemas):** troca de teclado, mouse e monitor; upgrade de memória e de SSD; troca de hardware; substituição de computador; instalação de equipamento novo; troca de impressora, de relógio de ponto e de aparelho telefônico; maquininha adicional ou nova; e toda a categoria Solicitações e Melhorias. Trocas de maquininha, pinpad ou TEF **com defeito** não passam, porque a venda está parada.

1. A loja abre o chamado normalmente.
2. A gestora recebe um e-mail de pedido de aprovação. No GLPI, o chamado aparece para ela na aba **Aprovações**, com **Aprovar** e **Recusar** (e um comentário opcional).
3. Você acompanha o status da aprovação no próprio chamado. Só execute depois de aprovado; se recusado, solucione como **Cancelado** explicando o motivo.

**Mudar a lista:** a coluna **Aprovação** de `config/categorias.tsv` diz Sim ou Não para cada problema (seção 8). **Outra pessoa aprovando:** inclua o usuário dela no grupo Aprovadores (Administração → Grupos → Aprovadores → Usuários); qualquer membro pode aprovar.

## 5. Usuários e lojas

Cada loja tem **um login só**, compartilhado pela equipe; quem abre o chamado escreve o próprio nome no formulário. A Matriz já tem o login **matriz**.

**Incluir uma loja nova** (Administração → Usuários → Adicionar):

| Campo | Exemplo (loja 06) |
| --- | --- |
| Usuário (login) | `loja06`, sem espaço e sem acento |
| Nome | Loja B |
| E-mails | e-mail da gerência da loja |
| Perfil | Loja / Solicitante |
| Localização | 06 Loja B (é dela que o chamado pega a unidade) |
| Ativo | Sim |

**Senha:** deixe em branco e peça para a loja clicar em **"Esqueceu sua senha?"** na tela de login, informando o e-mail cadastrado. O link chega por e-mail e vale por 1 dia. Ou defina uma senha na ficha e passe para a gerência.

**Desligar um acesso:** na ficha do usuário, **Ativo = Não**. Os chamados antigos continuam no histórico.

**Perfis disponíveis:**

| Perfil | Para quem |
| --- | --- |
| Loja / Solicitante | Logins das lojas e do CD: abrem e acompanham só os próprios chamados |
| Gestão (aprovação) | A chefe: vê todos os chamados e painéis, aprova, não altera |
| Técnico de TI | Quem atende chamados |
| Supervisor de TI | Técnico que também distribui chamados da equipe |
| Administrador geral | Você (doremi.ti): acesso total |
| Administrador | Administra sem mexer na configuração geral |
| Atendente (1º nível) e Somente leitura | Não usados hoje |

As 12 unidades já existem como Localizações (01 Matriz a 18 Loja I; 05 é o Depósito / CD). A implantação é gradual: Matriz primeiro, depois uma loja por vez.

## 6. Painel, estatísticas e satisfação

A tela principal abre no painel **Assistência**, só com chamados: novos, atrasados, pendentes, solucionados, evolução no ano e chamados por categoria.

- **Editar o painel:** lápis no canto do painel. Remova um quadro no "x", arraste para reorganizar, adicione no "+". A lua pequena da barra do painel é o modo escuro só do painel (o botão de lua/sol do topo já liga os dois juntos).
- **Estatísticas gerais:** menu **Assistência → Estatísticas**, por período, categoria, técnico ou localização (unidade).
- **Satisfação:** todo chamado fechado gera a pesquisa de 1 a 5 para a loja. As respostas chegam por e-mail **só para o perfil Gestão (aprovação)**; o TI não recebe nem o convite nem as respostas. Na tela, as notas ficam na aba **Satisfação** de cada chamado e nas estatísticas.
- **Histórico do chamado:** toda a conversa com a loja (acompanhamentos), as tarefas, a solução, as aprovações e cada mudança de status ou prioridade ficam salvos no chamado, na linha do tempo e na aba **Histórico**. A Gestão vê tudo o que é público; acompanhamentos e tarefas marcados como **privados** ela não vê.
- **Exportar:** em qualquer lista de chamados, o botão de download gera CSV, Excel ou PDF com os filtros aplicados.

O painel gerencial com SLA cumprido, tempo médio, satisfação e reincidência por loja, e o relatório mensal automático, são a fase 3 do projeto, depois do uso real.

## 7. E-mail e notificações

Os avisos saem de **ti@example.com**, que também recebe todo chamado novo.

| Configuração (Configurar → Notificações → Configuração de notificações por e-mail) | Valor |
| --- | --- |
| Modo de envio | SMTP |
| Servidor | mail.example.com |
| Porta | 465 (o SSL é automático nessa porta) |
| Usuário | ti@example.com |

- **Trocou a senha do ti@?** Troque também a **Senha SMTP** nessa tela, salve e use **Enviar um e-mail de teste**. Sem isso, nenhum aviso sai.
- **Quem recebe o quê:** Configurar → Notificações → Notificações. Cada evento (chamado novo, acompanhamento, solução, aprovação, satisfação) tem os seus destinatários.
- **Seu e-mail pessoal no doremi.ti:** cadastre em Minhas configurações para receber também os avisos de técnico.
- Os e-mails saem pela tarefa automática que roda a cada minuto; um aviso pode levar até 1 a 2 minutos.

## 8. Mudar categorias, prazos e regras

A configuração mora em arquivos do projeto (`~/central-chamados/config/`) e um script aplica no GLPI: edite o arquivo, simule, aplique.

| Arquivo | O que define |
| --- | --- |
| `categorias.tsv` | Categoria, grupo, problema, tipo, prioridade padrão e se precisa de aprovação |
| `sla.tsv` | Prazos de 1ª resposta e solução por prioridade |
| `horario.tsv` e `feriados.tsv` | Horário do TI e feriados (os móveis vão até 2028: incluir 2029 até o fim de 2028) |
| `unidades.tsv` | As 12 unidades |
| `listas.tsv` | Motivos de pendência e tipos de solução |
| `campos.tsv` | Perguntas do formulário (referência) |

1. Edite o arquivo no VS Code (uma linha por item, colunas separadas por Tab).
2. Simule: `python3 ~/central-chamados/scripts/servidor/configurar-glpi.py` (só mostra o que mudaria).
3. Aplique: o mesmo comando com `--aplicar` no final.

- O script só **cria o que falta** e mantém as regras **[Central]**; não apaga nada criado na tela. Uma categoria renomeada vira uma nova; a antiga você desativa na tela.
- **Formulário:** o script não altera um formulário que já existe. Mudança pequena (um texto, uma pergunta): faça direto em Administração → Formulários → Abrir chamado. Mudança grande: me peça para ajustar o script e recriar.
- No editor do formulário aparecem 31 perguntas "Qual problema exatamente?": é uma por grupo, e a loja vê só a do grupo escolhido. Use **Pré-visualizar** para ver como a loja vê.
- Toda mudança nos arquivos vai para o GitHub privado sozinha, e as decisões ficam em `DECISOES.md`.

## 9. Manutenção no servidor

Quase tudo roda sozinho; os scripts abaixo ficam em `~/central-chamados/scripts/servidor/` e rodam pelo terminal do VS Code, com `sudo bash` na frente, exceto onde indicado.

| Script | Para quê |
| --- | --- |
| `desbloquear.sh` | Sem nada: lista quem está bloqueado por errar a senha. Com o login (`desbloquear.sh matriz`) ou o IP: desbloqueia |
| `definir-senha-glpi.sh` | Define a senha de um usuário pelo terminal (padrão: doremi.ti) |
| `tema-doremi.sh` | Reinstala o tema Dorémi e o botão de modo escuro. **Rodar depois de toda atualização do GLPI** |
| `endurecer-glpi.sh` | Reaplica a segurança do PHP e o backup |
| `caddy-glpi.sh` | Reescreve a configuração do Caddy (site público, interno e bloqueio do SmartStock) |
| `protecao-login.sh` | Reinstala o bloqueio de tentativas de senha (fail2ban) |
| `configurar-glpi.py` | Sem sudo: aplica os arquivos de `config/` (seção 8) |

- **Backup:** todo dia às 12:45, em `/backup/glpi` (HD separado). O banco tem uma cópia por dia; anexos e configuração ficam em espelho, e o que for apagado fica 30 dias em `removidos/`.
- **Certificado:** o Caddy renova sozinho antes de vencer. Exige as portas 80 e 443 do modem abertas para 192.168.1.10.
- **Atualizações de segurança** do Ubuntu e do PHP são automáticas. A **versão do GLPI** não: atualize com calma, depois do backup do dia, e rode `tema-doremi.sh` em seguida.
- **Reiniciar o Caddy** (`sudo systemctl restart caddy`) derruba o SmartStock por 1 a 2 segundos.
- **Modem:** as regras TCP 80 e 443 → 192.168.1.10 ficam em Solicitação → Encaminhamento de Portas. Regra nova só vale depois de reiniciar o modem (Administração → Reiniciar e redefinir → Reiniciar o Sistema).

## 10. Problemas comuns

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| Loja diz que a página parou de abrir depois de errar a senha | Bloqueio por 5 tentativas erradas | `sudo bash ~/central-chamados/scripts/servidor/desbloquear.sh` e depois com o login da loja |
| Loja não lembra a senha | — | "Esqueceu sua senha?" na tela de login, com o e-mail do login |
| Nenhum e-mail chega | Senha do ti@ mudou ou SMTP fora | Seção 7: trocar a Senha SMTP e enviar o e-mail de teste |
| Site público não abre de fora | Portas do modem ou certificado | Conferir as regras 80 e 443 no modem; no servidor, `journalctl -u caddy -n 20` |
| Site público não abre dentro da Matriz | O modem não faz o retorno para a própria rede | Usar https://192.168.1.10:8443 |
| Painel escuro com quadros brancos | Plugin do tema desatualizado após atualização do GLPI | `sudo bash ~/central-chamados/scripts/servidor/tema-doremi.sh` e Ctrl+F5 |
| Chamado com prioridade ou prazo errado | Problema escolhido errado pela loja | Corrigir categoria e prioridade no chamado (seção 3) |
| Pedido de aprovação não chega à gestora | Ela fora do grupo ou sem e-mail | Administração → Grupos → Aprovadores; e-mail na ficha dela |

O histórico de tudo o que foi decidido está em `~/central-chamados/DECISOES.md`, e o que falta fazer em `PROXIMOS-PASSOS.md`.
