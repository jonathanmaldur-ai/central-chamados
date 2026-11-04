#!/bin/bash
# DNS dinâmico da Central (decisão 59): o IP da operadora muda e não há IP fixo. chamados.example.com é um
# CNAME para doremi-chamados.duckdns.org, e este script avisa o DuckDNS do IP atual da Matriz a cada 5 minutos.
# Roda como o usuário informatica, sem sudo. O token do DuckDNS só muda o IP desse nome (não dá acesso a cPanel,
# e-mail nem site) e fica fora do projeto e do GitHub.
#   bash ~/central-chamados/scripts/servidor/dns-dinamico.sh --guardar   # cola o token (não aparece na tela)
#   bash ~/central-chamados/scripts/servidor/dns-dinamico.sh --instalar  # roda a cada 5 minutos (cron)
#   bash ~/central-chamados/scripts/servidor/dns-dinamico.sh             # atualiza agora
set -euo pipefail

NOME=doremi-chamados
chave=$HOME/.config/central-chamados/duckdns.env
estado=$HOME/.local/state/central-chamados
registro=$estado/dns-dinamico.log
aqui=$(readlink -f "$0")

case "${1:-}" in
--guardar)
    install -d -m 700 "$(dirname "$chave")"
    read -rsp "Cole o token do DuckDNS e tecle Enter: " token; echo
    [[ $token =~ ^[0-9a-f-]{36}$ ]] || { echo "O token parece incompleto; nada foi gravado."; exit 1; }
    umask 077
    printf '# Token do DuckDNS (decisão 59). Não versionar, não copiar para fora do servidor.\nDUCKDNS_TOKEN=%s\n' "$token" > "$chave"
    unset token
    echo "Token gravado em $chave (só o usuário informatica lê)."
    exit 0
    ;;
--instalar)
    linha="*/5 * * * * bash \"$aqui\" >/dev/null 2>&1"
    { crontab -l 2>/dev/null | grep -vF "$aqui" || true; echo "$linha"; } | crontab -
    echo "Agendado a cada 5 minutos. Registro das trocas de IP: $registro"
    exit 0
    ;;
esac

[[ -r $chave ]] || { echo "Falta o token: rode com --guardar."; exit 1; }
# shellcheck source=/dev/null
source "$chave"
install -d -m 700 "$estado"

# O token vai pela entrada do curl, não pela linha de comando (que outros processos poderiam ver).
# Sem ip=, o DuckDNS grava o IP de onde veio o pedido: o da Matriz.
resposta=$(printf 'url = "https://www.duckdns.org/update?domains=%s&token=%s&verbose=true"\n' "$NOME" "$DUCKDNS_TOKEN" \
    | curl -4 -s -m 30 -K -) || resposta="sem resposta"
agora=$(date '+%d/%m/%Y %H:%M')

# Resposta com verbose: OK, IP, (vazio), UPDATED ou NOCHANGE.
mapfile -t linhas <<<"$resposta"
if [[ ${linhas[0]:-} != OK ]]; then
    echo "$agora  ERRO ao atualizar o DuckDNS: ${linhas[0]:-sem resposta}" >> "$registro"
    exit 1
fi
if [[ ${linhas[3]:-} == UPDATED || ! -s $registro ]]; then
    echo "$agora  IP da Matriz: ${linhas[1]:-?}" >> "$registro"
fi
