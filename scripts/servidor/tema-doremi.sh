#!/bin/bash
# Instala ou atualiza o visual Dorémi do GLPI. Pode rodar quantas vezes quiser (e deve rodar de novo depois de
# atualizar o GLPI, que substitui a pasta de plugins do código).
#   sudo bash ~/central-chamados/scripts/servidor/tema-doremi.sh
#
# O que faz:
#   1. Paletas "Dorémi" (clara) e "Dorémi escuro" em /var/lib/glpi/_themes, com o logo embutido.
#   2. Plugin "doremi": botão de modo claro/escuro no topo, ao lado do menu do usuário.
# A paleta padrão (também a da tela de login) se escolhe no GLPI: Configurar → Geral → Valores padrão.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

CODIGO=/var/www/glpi
TEMAS=/var/lib/glpi/_themes
ADMIN=doremi.ti
aqui=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
console() { sudo -u www-data php "$CODIGO/bin/console" "$@"; }

echo "=== Paletas ==="
logo=$(base64 -w0 "$aqui/tema/doremi-brinquedos.png")
icone=$(base64 -w0 "$aqui/tema/favicon-48.png")
install -d -m 750 -o www-data -g www-data "$TEMAS"
for tema in doremi doremi_escuro; do
    sed -e "s|__LOGO__|$logo|" -e "s|__ICONE__|$icone|" "$aqui/tema/$tema.scss" > "$TEMAS/$tema.scss"
    chown www-data:www-data "$TEMAS/$tema.scss"
    chmod 640 "$TEMAS/$tema.scss"
done
echo "Dorémi e Dorémi escuro em $TEMAS."

echo "=== Plugin do botão de modo escuro ==="
# Código do plugin pertence ao root (o PHP do GLPI só lê, não altera).
rsync -a --delete --chown=root:root --chmod=D755,F644 "$aqui/plugin-doremi/" "$CODIGO/plugins/doremi/"
console plugin:install --force --username="$ADMIN" doremi --no-interaction
console plugin:activate doremi --no-interaction   # se já estiver ativo, só avisa

# O GLPI guarda o CSS compilado em cache: limpa para as paletas novas aparecerem.
console cache:clear --no-interaction >/dev/null
echo
echo "Pronto. Recarregue o GLPI com Ctrl+F5: o botão de lua/sol aparece ao lado do seu nome, no topo."
