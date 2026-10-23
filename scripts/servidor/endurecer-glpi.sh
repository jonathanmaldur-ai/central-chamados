#!/bin/bash
# Segurança e backup da Central de Chamados (GLPI). Pode rodar quantas vezes quiser; o instalar-glpi.sh chama no final.
#   sudo bash ~/central-chamados/scripts/servidor/endurecer-glpi.sh
#
# O que faz:
#   1. Confere que o PHP tem a correção do PHP2Shell (CVE-2026-109618 e CVE-2026-109619).
#   2. Pool "glpi" do PHP endurecido: só enxerga as pastas do GLPI (open_basedir), não roda comandos do
#      sistema, não abre URLs como arquivo, só executa .php. Testa a configuração antes de reiniciar.
#   3. Backup diário: banco completo por dia + anexos em espelho incremental, 30 dias.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

CODIGO=/var/www/glpi
CONFIG=/etc/glpi
DADOS=/var/lib/glpi
LOGS=/var/log/glpi
PHPV=8.3
SOCK=/run/php/php$PHPV-fpm-glpi.sock
POOL=/etc/php/$PHPV/fpm/pool.d/glpi.conf

passo() { echo; echo "=== $1 ==="; }

[[ -d $CODIGO ]] || { echo "GLPI não encontrado em $CODIGO: rode antes o instalar-glpi.sh."; exit 1; }

passo 'PHP com a correção do PHP2Shell'
# Execução remota sem login, explorada desde 10/2026. O Ubuntu corrigiu em 8.3.6-0ubuntu0.24.04.13
# (USN-8948-1), mantendo o "8.3.6" no número; as atualizações automáticas trazem as próximas.
corrigido=8.3.6-0ubuntu0.24.04.13
for pacote in php$PHPV-fpm php$PHPV-cli; do
    v=$(dpkg-query -W -f='${Version}' "$pacote")
    dpkg --compare-versions "$v" ge "$corrigido" || { echo "$pacote $v não tem a correção do PHP2Shell; parei."; exit 1; }
    echo "$pacote $v: corrigido."
done

passo 'PHP (pool glpi)'
install -d -m 750 -o www-data -g www-data "$DADOS/_tmp" "$DADOS/_sessions"
[[ -f $POOL ]] && cp -a "$POOL" "$POOL.anterior"
cat > "$POOL" <<EOF
[glpi]
user = www-data
group = www-data
listen = $SOCK
listen.owner = caddy
listen.group = caddy
listen.mode = 0660
pm = ondemand
pm.max_children = 10
; Só executa arquivos .php (uma foto enviada com código dentro nunca roda).
security.limit_extensions = .php
php_admin_value[session.cookie_httponly] = on
php_admin_value[session.cookie_secure] = on
php_admin_value[session.cookie_samesite] = Lax
php_admin_flag[session.use_strict_mode] = on
php_admin_value[session.save_path] = $DADOS/_sessions
php_admin_value[memory_limit] = 256M
php_admin_value[upload_max_filesize] = 20M
php_admin_value[post_max_size] = 25M
php_admin_value[max_execution_time] = 60
php_admin_value[date.timezone] = America/Sao_Paulo
php_admin_flag[expose_php] = off
; Endurecimento: o PHP do GLPI só enxerga as pastas do GLPI, não roda comandos do sistema
; e não abre URLs como arquivo. Se um invasor achar uma falha no GLPI, fica preso aqui.
php_admin_value[open_basedir] = $CODIGO:$CONFIG:$DADOS:$LOGS
php_admin_value[upload_tmp_dir] = $DADOS/_tmp
php_admin_value[sys_temp_dir] = $DADOS/_tmp
php_admin_value[disable_functions] = exec,passthru,shell_exec,system,proc_open,popen,pcntl_exec,dl
php_admin_flag[allow_url_fopen] = off
php_admin_flag[allow_url_include] = off
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[error_log] = $LOGS/php-erros.log
EOF
if ! php-fpm$PHPV -t 2>/dev/null; then
    [[ -f $POOL.anterior ]] && cp -a "$POOL.anterior" "$POOL"
    echo "Configuração do PHP inválida: voltei a anterior."
    exit 1
fi
systemctl restart php$PHPV-fpm
echo "Pool glpi aplicado."

passo 'Backup diário'
command -v rsync >/dev/null || apt-get install -y -q rsync
cat > /usr/local/sbin/glpi-backup <<EOF
#!/bin/bash
# Backup diário da Central de Chamados. Guarda 30 dias.
#   Banco: um dump completo por dia (é pequeno).
#   Anexos e configuração: espelho incremental (só copia o que é novo); o que for apagado ou
#   alterado no GLPI vai para removidos/DATA e fica lá 30 dias. Assim o HD não guarda 30 cópias das fotos.
set -euo pipefail
umask 077
destino=/backup/glpi
mkdir -p "\$destino/espelho" "\$destino/removidos"
stamp=\$(date +%F_%H%M%S)
mariadb-dump --single-transaction glpi | gzip > "\$destino/glpi-banco-\$stamp.sql.gz"
rsync -a --delete --exclude=_sessions/ --exclude=_tmp/ --exclude=_cache/ \\
    --backup --backup-dir="\$destino/removidos/\$stamp" $DADOS $CONFIG "\$destino/espelho/"
find "\$destino" -maxdepth 1 -type f -name 'glpi-*' -mtime +30 -delete
find "\$destino/removidos" -mindepth 1 -maxdepth 1 -mtime +30 -exec rm -rf {} +
EOF
chmod 750 /usr/local/sbin/glpi-backup
echo "45 12 * * * root /usr/local/sbin/glpi-backup" > /etc/cron.d/glpi-backup
/usr/local/sbin/glpi-backup
echo "Backup feito: $(ls /backup/glpi | grep -c '^glpi-banco-') dump(s) do banco; anexos em /backup/glpi/espelho."

passo 'Conferência'
# O GLPI precisa responder pelo PHP endurecido (sem depender do certificado, que só sai com as portas abertas).
codigo=$(curl -sk -o /dev/null -w '%{http_code}' --resolve "chamados.example.com:443:127.0.0.1" \
    https://chamados.example.com/ || true)
resposta=$(SCRIPT_FILENAME=$CODIGO/public/index.php SCRIPT_NAME=/index.php REQUEST_URI=/ REQUEST_METHOD=GET \
    HTTPS=on SERVER_NAME=chamados.example.com cgi-fcgi -bind -connect "$SOCK" 2>&1 | head -1 || true)
echo "PHP do GLPI: ${resposta:-sem resposta}"
echo "HTTPS pelo Caddy: ${codigo/000/sem certificado ainda (normal antes de abrir as portas)}"
[[ -s $LOGS/php-erros.log ]] && { echo "Últimos erros do PHP:"; tail -5 "$LOGS/php-erros.log"; }
echo
echo "Pronto."
