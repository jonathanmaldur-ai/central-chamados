#!/bin/bash
# Mostra e desbloqueia quem o fail2ban bloqueou por errar a senha do GLPI (decisão 39).
#   sudo bash ~/central-chamados/scripts/servidor/desbloquear.sh             # lista os bloqueados e o login que errou
#   sudo bash ~/central-chamados/scripts/servidor/desbloquear.sh loja06      # desbloqueia pelo login (procura o IP)
#   sudo bash ~/central-chamados/scripts/servidor/desbloquear.sh 203.0.113.7 # desbloqueia pelo IP
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

LOG=/var/log/glpi/event.log
mapfile -t bloqueados < <(fail2ban-client status glpi | sed -n 's/.*Banned IP list:\s*//p' | tr ' ' '\n' | grep -v '^$' || true)

# Último login que errou a senha a partir de um IP.
login_do_ip() { grep -oE "Failed login for .* from IP $1\$" "$LOG" 2>/dev/null | tail -1 | sed -E 's/Failed login for (.*) from IP .*/\1/'; }

if [[ $# -eq 0 ]]; then
    if ((${#bloqueados[@]} == 0)); then echo "Ninguém bloqueado."; exit 0; fi
    echo "Bloqueados agora:"
    for ip in "${bloqueados[@]}"; do printf '  %-40s login tentado: %s\n' "$ip" "$(login_do_ip "$ip")"; done
    exit 0
fi

alvo=$1
if [[ $alvo =~ ^[0-9a-fA-F:.]+$ && $alvo == *[.:]* ]]; then
    ips=("$alvo")
else
    # Pelo login: os IPs bloqueados de onde houve falha com esse login.
    ips=()
    for ip in "${bloqueados[@]}"; do
        grep -qF "Failed login for $alvo from IP $ip" "$LOG" 2>/dev/null && ips+=("$ip")
    done
    ((${#ips[@]})) || { echo "Nenhum IP bloqueado tem falhas do login \"$alvo\". Sem argumento, o script lista os bloqueados."; exit 1; }
fi
for ip in "${ips[@]}"; do
    fail2ban-client set glpi unbanip "$ip" >/dev/null && echo "Desbloqueado: $ip"
done
