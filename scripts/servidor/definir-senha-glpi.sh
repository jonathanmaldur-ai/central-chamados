#!/bin/bash
# Define a senha de um usuário do GLPI pelo terminal (para quando o site ainda não abre, ou se perder a senha do admin).
#   sudo bash ~/central-chamados/scripts/servidor/definir-senha-glpi.sh [usuário]    (padrão: glpi)
# A senha é digitada por quem roda, não aparece na tela e não fica gravada em lugar nenhum além do GLPI (só o hash).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

usuario=${1:-glpi}
[[ $usuario =~ ^[A-Za-z0-9._@-]+$ ]] || { echo "Nome de usuário inválido: $usuario"; exit 1; }
existe=$(mariadb -N glpi -e "SELECT COUNT(*) FROM glpi_users WHERE name = '$usuario'")
[[ $existe == 1 ]] || { echo "Usuário $usuario não existe no GLPI."; exit 1; }

while true; do
    read -rsp "Nova senha para $usuario (mínimo 12 caracteres): " senha; echo
    if (( ${#senha} < 12 )); then echo "Curta demais, tente de novo."; continue; fi
    read -rsp "Repita a senha: " confirma; echo
    [[ $senha == "$confirma" ]] && break
    echo "As duas não batem, tente de novo."
done

# O hash do PHP (bcrypt) só tem letras, números e $./, então pode ir direto no SQL.
hash=$(printf '%s' "$senha" | php -r 'echo password_hash(stream_get_contents(STDIN), PASSWORD_DEFAULT);')
unset senha confirma
mariadb glpi -e "UPDATE glpi_users SET password = '$hash', password_last_update = NOW() WHERE name = '$usuario'"
echo "Senha de $usuario definida."
