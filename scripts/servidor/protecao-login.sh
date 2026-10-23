#!/bin/bash
# Proteção contra tentativas de senha no GLPI (decisão 39). Pode rodar quantas vezes quiser.
#   sudo bash ~/central-chamados/scripts/servidor/protecao-login.sh
#
# O GLPI não bloqueia senha errada sozinho, mas grava cada falha em /var/log/glpi/event.log:
#   2026-10-23 15:00:00 [0@servidor]
#   [login] 3: Failed login for fulano from IP 203.0.113.7
# O fail2ban lê esse arquivo e, com 5 falhas do mesmo IP em 10 minutos, bloqueia o IP no firewall (UFW) por 1 hora;
# quem insiste é bloqueado por mais tempo a cada vez. A rede interna e as VPNs nunca são bloqueadas.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

passo() { echo; echo "=== $1 ==="; }

passo 'Pacote'
command -v fail2ban-client >/dev/null || apt-get install -y -q fail2ban

passo 'Filtro do GLPI'
cat > /etc/fail2ban/filter.d/glpi.conf <<'EOF'
# Falhas de login do GLPI (event.log em duas linhas: data e mensagem).
[Init]
maxlines = 2

[Definition]
failregex = ^\s*\[[^\]]*\]\s*\n\[login\] \d+: Failed login for .* from IP <HOST>\s*$
ignoreregex =
datepattern = ^%%Y-%%m-%%d %%H:%%M:%%S
EOF

# Confere o filtro com uma falha de exemplo antes de ligar (não toca no log real).
amostra=$(mktemp)
trap 'rm -f "$amostra"' EXIT
printf '%s [0@teste]\n[login] 3: Failed login for teste from IP 203.0.113.7\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$amostra"
if ! fail2ban-regex "$amostra" /etc/fail2ban/filter.d/glpi.conf | grep -q '^Failregex: 1 total'; then
    echo "O filtro não reconheceu a linha de exemplo; nada foi ligado."
    exit 1
fi
echo "Filtro reconhece a falha de login de exemplo."

passo 'Regra (jail)'
cat > /etc/fail2ban/jail.d/glpi.local <<'EOF'
[glpi]
enabled  = true
port     = http,https
filter   = glpi
logpath  = /var/log/glpi/event.log
backend  = auto
maxretry = 5
findtime = 10m
bantime  = 1h
# Reincidente: o bloqueio dobra a cada vez, até 1 semana.
bantime.increment = true
bantime.maxtime   = 1w
banaction = ufw
# Rede interna, OpenVPN, Tailscale e o próprio servidor nunca são bloqueados.
ignoreip = 127.0.0.1/8 ::1 192.168.0.0/24 10.8.0.0/24 100.64.0.0/10 fd7a:115c:a1e0::/48
EOF
touch /var/log/glpi/event.log
chown www-data:www-data /var/log/glpi/event.log

systemctl enable --now fail2ban >/dev/null
fail2ban-client reload >/dev/null
sleep 2
fail2ban-client status glpi
echo
echo "Pronto. Ver bloqueados: sudo fail2ban-client status glpi · Desbloquear: sudo fail2ban-client set glpi unbanip <IP>"
