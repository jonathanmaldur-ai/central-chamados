#!/bin/bash
# Escreve o Caddyfile do servidor (SmartStock só interno + GLPI público e interno), valida e aplica.
# Se a configuração nova for inválida, volta a anterior e o SmartStock não é afetado. Pode rodar quantas vezes quiser.
#   sudo bash ~/central-chamados/scripts/servidor/caddy-glpi.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

DOMINIO=chamados.example.com
CODIGO=/var/www/glpi
SOCK=/run/php/php8.3-fpm-glpi.sock
CADDYFILE=/etc/caddy/Caddyfile

# Guarda o original de antes do GLPI uma vez só; a cada execução, o anterior.
[[ -e $CADDYFILE.antes-do-glpi ]] || cp -a "$CADDYFILE" "$CADDYFILE.antes-do-glpi"
cp -a "$CADDYFILE" "$CADDYFILE.anterior"
cat > "$CADDYFILE" <<EOF
# Configuração do GLPI, usada pelo endereço público e pelo interno.
(glpi) {
	root * $CODIGO/public
	request_body {
		max_size 25MB
	}
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

# SmartStock AI: HTTPS na rede interna com certificado da autoridade local do Caddy.
# Só atende a rede interna, a VPN (OpenVPN 10.8.0.0/24 e Tailscale 100.64.0.0/10 e fd7a:115c:a1e0::/48) e o próprio servidor;
# quem vem da internet é recusado, mesmo digitando este nome (decisão 4 da Central de Chamados).
https://smartstock.internal, https://192.168.1.10 {
	tls internal
	@fora not remote_ip 192.168.0.0/24 10.8.0.0/24 100.64.0.0/10 fd7a:115c:a1e0::/48 127.0.0.0/8 ::1
	abort @fora
	encode gzip
	reverse_proxy 127.0.0.1:5080
}

# Central de Chamados pela rede interna e VPN (acesso do TI e testes antes de abrir as portas).
# A porta 8443 não é aberta no modem.
https://192.168.1.10:8443 {
	tls internal
	@fora not remote_ip 192.168.0.0/24 10.8.0.0/24 100.64.0.0/10 fd7a:115c:a1e0::/48 127.0.0.0/8 ::1
	abort @fora
	import glpi
}

# Central de Chamados (GLPI): único site aberto para a internet, com certificado Let's Encrypt automático.
$DOMINIO {
	import glpi
}
EOF
if ! caddy validate --config "$CADDYFILE" --adapter caddyfile >/dev/null 2>&1; then
    cp -a "$CADDYFILE.anterior" "$CADDYFILE"
    echo "Configuração do Caddy inválida: voltei a anterior. O SmartStock não foi afetado."
    exit 1
fi
systemctl reload caddy
echo "Caddy atualizado: GLPI em https://$DOMINIO (público) e https://192.168.1.10:8443 (interno)."
