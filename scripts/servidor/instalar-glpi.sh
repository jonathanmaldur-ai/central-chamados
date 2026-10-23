#!/bin/bash
# Instala o GLPI (Central de Chamados) no servidor, isolado do SmartStock. Roda uma vez, com sudo:
#   sudo bash ~/central-chamados/scripts/servidor/instalar-glpi.sh
#
# O que faz:
#   1. MariaDB e PHP 8.3 (pool próprio "glpi" no php-fpm).
#   2. Baixa o GLPI $VERSAO do GitHub e confere o SHA-256 publicado.
#   3. Arquivos fora da pasta pública: código em /var/www/glpi, configuração em /etc/glpi,
#      anexos em /var/lib/glpi, logs em /var/log/glpi.
#   4. Cria o banco, em português, com fuso de São Paulo; troca a senha do admin "glpi" e
#      desativa os usuários de exemplo (tech, normal, post-only).
#   5. Caddy: o SmartStock passa a recusar quem não está na rede interna ou na VPN (decisão 4) e o
#      chamados.example.com ganha certificado Let's Encrypt (emitido quando as portas 80/443
#      forem abertas no modem, decisão 13).
#   6. Tarefas automáticas do GLPI (cron) e backup diário em /backup/glpi (banco + anexos, 30 dias).
#
# Senhas: geradas aqui. A do banco fica só em /etc/glpi (arquivo do GLPI); a do admin aparece UMA vez no final.
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
CADDYFILE=/etc/caddy/Caddyfile

passo() { echo; echo "=== $1 ==="; }

[[ ! -e $CODIGO ]] || { echo "$CODIGO já existe: o GLPI parece instalado. Nada foi alterado."; exit 1; }

passo 'Pacotes (MariaDB e PHP)'
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q mariadb-server php$PHPV-fpm php$PHPV-cli php$PHPV-mysql php$PHPV-curl php$PHPV-gd \
    php$PHPV-intl php$PHPV-mbstring php$PHPV-xml php$PHPV-zip php$PHPV-bz2 php$PHPV-bcmath php$PHPV-ldap \
    php$PHPV-opcache php-apcu python3 curl

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

passo 'PHP (pool glpi)'
cat > /etc/php/$PHPV/fpm/pool.d/glpi.conf <<EOF
[glpi]
user = www-data
group = www-data
listen = $SOCK
listen.owner = caddy
listen.group = caddy
pm = ondemand
pm.max_children = 10
php_admin_value[session.cookie_httponly] = on
php_admin_value[session.cookie_secure] = on
php_admin_value[session.cookie_samesite] = Lax
php_admin_value[memory_limit] = 256M
php_admin_value[upload_max_filesize] = 20M
php_admin_value[post_max_size] = 25M
php_admin_value[date.timezone] = America/Sao_Paulo
php_admin_flag[expose_php] = off
EOF
systemctl restart php$PHPV-fpm

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
senha_admin=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
hash=$(php -r 'echo password_hash($argv[1], PASSWORD_DEFAULT);' -- "$senha_admin")
mariadb glpi <<SQL
UPDATE glpi_users SET password = '$hash' WHERE name = 'glpi';
UPDATE glpi_users SET is_active = 0 WHERE name IN ('tech', 'normal', 'post-only');
UPDATE glpi_configs SET value = 'https://$DOMINIO' WHERE context = 'core' AND name = 'url_base';
UPDATE glpi_configs SET value = 'America/Sao_Paulo' WHERE context = 'core' AND name = 'timezone';
SQL

passo 'Caddy'
cp -a "$CADDYFILE" "$CADDYFILE.antes-do-glpi"
cat > "$CADDYFILE" <<EOF
# SmartStock AI: HTTPS na rede interna com certificado da autoridade local do Caddy.
# Só atende a rede interna, a VPN (OpenVPN 10.8.0.0/24 e Tailscale 100.64.0.0/10) e o próprio servidor;
# quem vem da internet é recusado, mesmo digitando este nome (decisão 4 da Central de Chamados).
https://smartstock.internal, https://192.168.1.10 {
	tls internal
	@fora not remote_ip 192.168.0.0/24 10.8.0.0/24 100.64.0.0/10 127.0.0.0/8
	abort @fora
	encode gzip
	reverse_proxy 127.0.0.1:5080
}

# Central de Chamados (GLPI): único site aberto para a internet, com certificado Let's Encrypt automático.
$DOMINIO {
	root * $CODIGO/public
	encode gzip
	php_fastcgi unix/$SOCK
	file_server
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		Referrer-Policy same-origin
		-Server
	}
}
EOF
if ! caddy validate --config "$CADDYFILE" --adapter caddyfile >/dev/null 2>&1; then
    cp -a "$CADDYFILE.antes-do-glpi" "$CADDYFILE"
    echo "Configuração do Caddy inválida: voltei a anterior. O SmartStock não foi afetado."
    exit 1
fi
systemctl reload caddy

passo 'Firewall'
if ufw status | grep -q '^Status: active'; then
    ufw allow 80/tcp comment 'Central de Chamados (certificado)'
    ufw allow 443/tcp comment 'Central de Chamados'
else
    echo "UFW desligado: nada a fazer (quem decide o que entra da internet é o modem)."
fi

passo 'Tarefas automáticas e backup'
if [[ -f $CODIGO/front/cron.php ]]; then tarefa="$CODIGO/front/cron.php"; else tarefa="$CODIGO/bin/console cron"; fi
echo "* * * * * www-data /usr/bin/php $tarefa >/dev/null 2>&1" > /etc/cron.d/glpi
cat > /usr/local/sbin/glpi-backup <<EOF
#!/bin/bash
# Backup diário da Central de Chamados: banco (mariadb-dump) + anexos e configuração. Guarda 30 dias.
set -euo pipefail
umask 077
destino=/backup/glpi
mkdir -p "\$destino"
stamp=\$(date +%F_%H%M%S)
mariadb-dump --single-transaction glpi | gzip > "\$destino/glpi-banco-\$stamp.sql.gz"
tar -czf "\$destino/glpi-arquivos-\$stamp.tar.gz" $DADOS $CONFIG
find "\$destino" -name 'glpi-*' -mtime +30 -delete
EOF
chmod 750 /usr/local/sbin/glpi-backup
echo "45 12 * * * root /usr/local/sbin/glpi-backup" > /etc/cron.d/glpi-backup
/usr/local/sbin/glpi-backup

echo
echo "================================================================"
echo " GLPI $versao instalado."
echo " Endereço: https://$DOMINIO (funciona de fora depois de abrir as portas 80 e 443 no modem)"
echo " Usuário administrador: glpi"
echo " Senha: $senha_admin"
echo " Guarde esta senha agora: ela não fica gravada em lugar nenhum."
echo "================================================================"
