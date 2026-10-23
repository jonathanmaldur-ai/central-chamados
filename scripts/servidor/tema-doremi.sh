#!/bin/bash
# Instala ou atualiza o tema "Dorémi" do GLPI (cores do SmartStock e logo). Pode rodar quantas vezes quiser.
#   sudo bash ~/central-chamados/scripts/servidor/tema-doremi.sh
# Depois, no GLPI: Configurar → Geral → Valores padrão → Paleta de cores = Dorémi (vale também na tela de login).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

CODIGO=/var/www/glpi
TEMAS=/var/lib/glpi/_themes
origem=$(cd "$(dirname "${BASH_SOURCE[0]}")/tema" && pwd)

logo=$(base64 -w0 "$origem/doremi-brinquedos.png")
icone=$(base64 -w0 "$origem/favicon-48.png")
install -d -m 750 -o www-data -g www-data "$TEMAS"
sed -e "s|__LOGO__|$logo|" -e "s|__ICONE__|$icone|" "$origem/doremi.scss" > "$TEMAS/doremi.scss"
chown www-data:www-data "$TEMAS/doremi.scss"
chmod 640 "$TEMAS/doremi.scss"

# O GLPI guarda o CSS compilado em cache: limpa para o tema novo aparecer.
sudo -u www-data php "$CODIGO/bin/console" cache:clear --no-interaction >/dev/null
echo "Tema Dorémi instalado em $TEMAS/doremi.scss."
echo "No GLPI: Configurar → Geral → Valores padrão → Paleta de cores = Dorémi → Salvar."
