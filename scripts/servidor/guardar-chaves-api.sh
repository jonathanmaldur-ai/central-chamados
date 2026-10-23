#!/bin/bash
# Guarda as chaves da API do GLPI (app token do cliente "Scripts do servidor" e token do usuário doremi.ti)
# num arquivo só do usuário informatica, fora do projeto e do GitHub. Sem sudo.
#   bash ~/central-chamados/scripts/servidor/guardar-chaves-api.sh
# As chaves são coladas no terminal, não aparecem na tela e não passam pelo chat.
set -euo pipefail

destino=$HOME/.config/central-chamados/glpi-api.env
install -d -m 700 "$(dirname "$destino")"

read -rsp "Cole o App token (cliente 'Scripts do servidor') e tecle Enter: " app; echo
read -rsp "Cole o Token de API do usuário doremi.ti e tecle Enter: " usuario; echo
[[ ${#app} -ge 20 && ${#usuario} -ge 20 ]] || { echo "Alguma chave parece incompleta; nada foi gravado."; exit 1; }

umask 077
cat > "$destino" <<EOF
# Chaves da API do GLPI (decisão 32). Não versionar, não copiar para fora do servidor.
GLPI_URL=https://192.168.1.10:8443/apirest.php
GLPI_APP_TOKEN=$app
GLPI_USER_TOKEN=$usuario
EOF
unset app usuario
echo "Chaves gravadas em $destino (só o usuário informatica lê)."
