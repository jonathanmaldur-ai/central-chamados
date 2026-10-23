# Decisões do projeto

| # | Tema | Decisão |
|---|---|---|
| 1 | Projeto separado | Em 22/10/2026 o responsável pediu uma pasta própria, sem misturar com o SmartStock AI. A central de chamados tem documentos, código e scripts próprios. |
| 2 | Canal das lojas | Em 22/10/2026 o responsável preferiu um **portal web** de chamados, em vez de WhatsApp. A loja abre o navegador (PC ou celular), entra com login, abre e acompanha o chamado. |
| 3 | Endereço | Subdomínio do domínio que a empresa já tem: **chamados.example.com**, com um registro A apontando para o IP fixo da matriz (203.0.113.10). O DNS fica na hospedagem (cPanel); o site (Nuvemshop) e os e-mails não mudam. Certificado HTTPS válido e automático: as lojas não instalam nada. |
| 4 | O que fica exposto | Só o portal de chamados responde para a internet (portas 80 e 443 liberadas no modem para o servidor). O SmartStock AI continua acessível só pela rede interna e pela VPN. |
| 5 | Onde fica | Em 22/10/2026 o responsável pediu que **tudo fique no servidor**: instalação, banco, anexos, backups e scripts. Nada roda nem fica guardado no PC do TI. |
| 6 | Ferramenta | **GLPI**. |
| 7 | Login | Um login **por loja**. O chamado ganha um campo obrigatório com o **nome de quem está abrindo** (responsável pelo chamado na loja). |
| 8 | Categorias e prazos | Aprovados como estão na proposta (seções 4 e 5 de 01 - Projeto.md). |
| 9 | Horário do TI | Segunda a sexta, 08:00 às 18:00. O SLA só conta nesse horário (sem sábado). |
| 10 | Relatório mensal | Enviado no dia 1º para financeiro@example.com e ti@example.com. |
| 11 | IP da matriz | Confirmado como fixo: 203.0.113.10. |

| 12 | Logins das lojas | Mesmas unidades ativas do SmartStock: 01 Matriz, 04 Loja A, 05 Depósito, 06 Loja B, 07 Loja C, 08 Loja D, 09 Loja E, 10 Loja F, 11 Loja G, 12 E-commerce, 17 Loja H, 18 Loja I. |
| 13 | Ordem das portas | As portas TCP 80 e 443 do modem só são abertas **no dia da instalação**, depois que o servidor estiver configurado para responder de fora só ao portal de chamados. Abrir antes deixaria o SmartStock (que já usa a 443) visível na internet. A UDP 1194 da VPN continua como está. |
| 14 | Versão do GLPI | **11.0.11** (série 11, com 11 correções). A 12.0.0 saiu em 07/10/2026 e fica para depois de algumas correções. Instalado por `scripts/servidor/instalar-glpi.sh`: código em /var/www/glpi, configuração em /etc/glpi, anexos em /var/lib/glpi, banco MariaDB local, backup diário em /backup/glpi. |
| 15 | SmartStock só para a rede interna | O Caddy escolhe o site pelo nome pedido, então abrir a 443 deixaria o SmartStock acessível de fora para quem digitasse o nome interno. Na instalação do GLPI, o site do SmartStock passa a **recusar quem não vem da rede interna (192.168.0.0/24), da VPN (10.8.0.0/24 e Tailscale) ou do próprio servidor**. |
| 16 | DNS | Em 23/10/2026 o registro A `chamados` → 203.0.113.10 está publicado. |
| 17 | E-mail de envio | Os avisos às lojas e o relatório mensal saem de **ti@example.com**, a mesma conta que o SmartStock já usa. |
| 18 | Logins | **Lojas:** um login por loja, com o **e-mail da gerência** da loja (os colaboradores não têm e-mail próprio); quem abre o chamado informa o nome no campo "responsável" (decisão 7). **Diretoria** e **Administrativo** têm login próprio. |
| 19 | Portfólio público | Cópias limpas em `jonathanmaldur-ai/central-chamados` e `jonathanmaldur-ai/smartstock-ai`, geradas por `portfolio/exportar-portfolio.sh` e **publicadas sozinhas a cada commit** (gancho `post-commit`, depois do push do privado), só se a verificação não achar nada sensível. Na Central, lojas e cidades viram "Loja A…I" e passam a ser padrão proibido; o histórico público dela foi recriado sem os nomes. No SmartStock os nomes das lojas continuam (estão no código e nos testes). |
| 20 | Segurança do PHP e backup | PHP com a correção do PHP2Shell (CVE-2026-109618/109619, pacote Ubuntu 8.3.6-0ubuntu0.24.04.13) e atualizações de segurança automáticas. Pool do GLPI endurecido (`open_basedir`, sem funções de comando, sem URL como arquivo, só `.php`). Backup: banco completo por dia e anexos em espelho incremental, 30 dias, para não encher o HD de backup. Tudo em `scripts/servidor/endurecer-glpi.sh`. |
| 21 | Senha do admin do GLPI | Escolhida pelo responsável, digitada no terminal (`scripts/servidor/definir-senha-glpi.sh`); o Claude não gera nem vê a senha. |
| 22 | Acesso interno ao GLPI | `https://192.168.1.10:8443`, só rede interna e VPN (certificado interno do Caddy), para o TI e para testar antes de abrir as portas. A 8443 não é aberta no modem. Caddyfile gerado por `scripts/servidor/caddy-glpi.sh` (valida antes de aplicar). |
| 23 | Login do administrador | O admin padrão `glpi` foi renomeado para **`doremi.ti`** (o `glpi` é o primeiro nome que um atacante tenta). Dados de demonstração do painel desabilitados. |
| 24 | Visual da Dorémi | Tema "Dorémi" do GLPI com os tokens do SmartStock (azul `#1273ba`, menu lateral branco, item ativo `#e7f1fa`) e o logo Dorémi no menu e no login, sem alterar proporção nem cores. Fica em `/var/lib/glpi/_themes` (sobrevive às atualizações do GLPI), instalado por `scripts/servidor/tema-doremi.sh` e escolhido como paleta padrão. |

## Pendentes

- Portas TCP 80 e 443 no modem → 192.168.1.10, no dia da instalação (decisão 13).
- E-mail da gerência de cada loja e lista de quem da Diretoria e do Administrativo terá login.
