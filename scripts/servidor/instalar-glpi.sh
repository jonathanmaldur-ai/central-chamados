#!/bin/bash
# Instala o GLPI (Central de Chamados) no servidor, isolado do SmartStock. Roda uma vez, com sudo:
#   sudo bash ~/central-chamados/scripts/servidor/instalar-glpi.sh
#
# O que faz:
#   1. MariaDB e PHP 8.3 (pool próprio "glpi" no php-fpm).
#   2. Baixa o GLPI $VERSAO do GitHub e confere o SHA-256 publicado.
#   3. Arquivos fora da pasta pública: código em /var/www/glpi, configuração em /etc/glpi,
#      anexos em /var/lib/glpi, logs em /var/log/glpi.
#   4. Cria o banco, em português, com fuso de São Paulo, e desativa os usuários de exemplo
#      (tech, normal, post-only).
#   5. Caddy: o SmartStock passa a recusar quem não está na rede interna ou na VPN (decisão 4) e o
#      chamados.example.com ganha certificado Let's Encrypt (emitido quando as portas 80/443
#      forem abertas no modem, decisão 13).
#   6. Tarefas automáticas do GLPI (cron); segurança do PHP e backup diário pelo endurecer-glpi.sh.
#   7. Renomeia o admin "glpi" para "doremi.ti" e pede a senha dele (definir-senha-glpi.sh): quem escolhe é o responsável.
#
# A senha do banco é aleatória e fica só em /etc/glpi (arquivo do GLPI).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

DOMINIO=chamados.example.com
# Série 11, já madura (a 12.0.0 saiu em 07/10/2026; atualizar quando tiver algumas correções).
VERSAO=11.0.11
CODIGO=/var/www/glpi
CONFIG=/etc/glpi
DADOS=/var/lib/glpi
LOGS=/var/log/glpi
PHPV=8.3
SOCK=/run/php/php$PHPV-fpm-glpi.sock

passo() { echo; echo "=== $1 ==="; }

[[ ! -e $CODIGO ]] || { echo "$CODIGO já existe: o GLPI parece instalado. Nada foi alterado."; exit 1; }

passo 'Pacotes (MariaDB e PHP)'
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q mariadb-server php$PHPV-fpm php$PHPV-cli php$PHPV-mysql php$PHPV-curl php$PHPV-gd \
    php$PHPV-intl php$PHPV-mbstring php$PHPV-xml php$PHPV-zip php$PHPV-bz2 php$PHPV-bcmath php$PHPV-ldap \
    php$PHPV-opcache php-apcu python3 curl rsync

passo 'PHP com a correção do PHP2Shell'
# CVE-2026-109618 e CVE-2026-109619 (PHP2Shell, execução remota sem login, explorado desde 10/2026).
# O Ubuntu corrigiu em 8.3.6-0ubuntu0.24.04.13 (USN-8948-1), mantendo o "8.3.6" no número.
corrigido=8.3.6-0ubuntu0.24.04.13
for pacote in php$PHPV-fpm php$PHPV-cli; do
    v=$(dpkg-query -W -f='${Version}' "$pacote")
    dpkg --compare-versions "$v" ge "$corrigido" || { echo "$pacote $v não tem a correção do PHP2Shell; parei."; exit 1; }
    echo "$pacote $v: corrigido."
done

passo 'Baixando o GLPI'
api=$(curl -fsSL "https://api.github.com/repos/glpi-project/glpi/releases/tags/$VERSAO")
read -r versao url digest < <(python3 -c '
import json, sys
r = json.load(sys.stdin)
a = next(a for a in r["assets"] if a["name"].endswith(".tgz"))
print(r["tag_name"], a["browser_download_url"], (a.get("digest") or "").removeprefix("sha256:"))' <<<"$api")
[[ -n $digest ]] || { echo "O GitHub não publicou o SHA-256 do pacote $versao; parei por segurança."; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$url" -o "$tmp/glpi.tgz"
echo "$digest  $tmp/glpi.tgz" | sha256sum -c -
echo "Versão: $versao"
install -d -m 755 /var/www
tar -xzf "$tmp/glpi.tgz" -C /var/www

passo 'Pastas fora da área pública'
install -d -m 750 -o www-data -g www-data "$CONFIG" "$DADOS" "$LOGS"
cp -a "$CODIGO/files/." "$DADOS/"
rm -rf "$CODIGO/files"
chown -R www-data:www-data "$DADOS"
cat > "$CODIGO/inc/downstream.php" <<'EOF'
<?php
define('GLPI_CONFIG_DIR', '/etc/glpi');
if (file_exists(GLPI_CONFIG_DIR . '/local_define.php')) {
    require_once GLPI_CONFIG_DIR . '/local_define.php';
}
EOF
cat > "$CONFIG/local_define.php" <<EOF
<?php
define('GLPI_VAR_DIR', '$DADOS');
define('GLPI_LOG_DIR', '$LOGS');
EOF
chown www-data:www-data "$CONFIG/local_define.php"
chown -R root:root "$CODIGO"
chown -R www-data:www-data "$CODIGO/marketplace" 2>/dev/null || true

passo 'Banco de dados'
senha_db=$(openssl rand -hex 24)
mariadb <<SQL
CREATE DATABASE glpi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'glpi'@'localhost' IDENTIFIED BY '$senha_db';
GRANT ALL PRIVILEGES ON glpi.* TO 'glpi'@'localhost';
GRANT SELECT ON mysql.time_zone_name TO 'glpi'@'localhost';
SQL
mariadb-tzinfo-to-sql /usr/share/zoneinfo 2>/dev/null | mariadb mysql
console() { sudo -u www-data php "$CODIGO/bin/console" "$@"; }
console db:install --db-host=localhost --db-name=glpi --db-user=glpi --db-password="$senha_db" \
    --default-language=pt_BR --no-interaction
unset senha_db
console database:enable_timezones --no-interaction || true
rm -f "$CODIGO/install/install.php"
console system:check_requirements --no-interaction || true

passo 'Usuários iniciais'
mariadb glpi <<SQL
UPDATE glpi_users SET is_active = 0 WHERE name IN ('tech', 'normal', 'post-only');
-- "glpi" é o primeiro login que um atacante tenta (decisão 23).
UPDATE glpi_users SET name = 'doremi.ti' WHERE name = 'glpi';
UPDATE glpi_configs SET value = 'https://$DOMINIO' WHERE context = 'core' AND name = 'url_base';
UPDATE glpi_configs SET value = 'America/Sao_Paulo' WHERE context = 'core' AND name = 'timezone';
SQL

passo 'Caddy'
bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/caddy-glpi.sh"

passo 'Firewall'
if ufw status | grep -q '^Status: active'; then
    ufw allow 80/tcp comment 'Central de Chamados (certificado)'
    ufw allow 443/tcp comment 'Central de Chamados'
else
    echo "UFW desligado: nada a fazer (quem decide o que entra da internet é o modem)."
fi

passo 'Tarefas automáticas'
if [[ -f $CODIGO/front/cron.php ]]; then tarefa="$CODIGO/front/cron.php"; else tarefa="$CODIGO/bin/console cron"; fi
echo "* * * * * www-data /usr/bin/php $tarefa >/dev/null 2>&1" > /etc/cron.d/glpi

passo 'Segurança e backup'
aqui=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
bash "$aqui/endurecer-glpi.sh"

passo 'Senha do administrador'
bash "$aqui/definir-senha-glpi.sh" doremi.ti

echo
echo "================================================================"
echo " GLPI $versao instalado."
echo " Endereço: https://$DOMINIO (funciona de fora depois de abrir as portas 80 e 443 no modem)"
echo " Usuário administrador: doremi.ti (senha escolhida por você agora há pouco)"
echo "================================================================"
