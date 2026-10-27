#!/bin/bash
# DNS local da matriz (decisão 48): o modem da operadora não faz "NAT loopback", então de dentro da matriz o nome
# chamados.example.com (IP público) não abre. Este DNS responde esse nome com o IP interno do servidor
# e repassa todo o resto para o DNS da operadora. O modem entrega este servidor como DNS primário e o da operadora como
# secundário: se o servidor cair, a internet da matriz continua resolvendo pelo secundário.
#   sudo bash ~/central-chamados/scripts/servidor/dns-local.sh
# Pode rodar quantas vezes quiser.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Rode com sudo."; exit 1; }

IP_SERVIDOR=192.168.1.10
REDE=192.168.0.0/24
DNS_CLARO=(181.213.132.4 181.213.132.5)
NOMES_INTERNOS=(chamados.example.com)

passo() { echo; echo "=== $1 ==="; }

passo 'Pacote'
command -v dnsmasq >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q dnsmasq-base dnsmasq

passo 'Configuração'
# Só no IP da rede interna: não disputa a porta 53 com o systemd-resolved (127.0.0.53) nem com a VPN.
{
    echo "# Gerado por ~/central-chamados/scripts/servidor/dns-local.sh (decisão 48). Não editar à mão."
    echo "listen-address=$IP_SERVIDOR"
    echo "bind-interfaces"
    echo "no-resolv"
    echo "no-hosts"
    echo "domain-needed"
    echo "bogus-priv"
    echo "cache-size=2000"
    for s in "${DNS_CLARO[@]}"; do echo "server=$s"; done
    for n in "${NOMES_INTERNOS[@]}"; do echo "address=/$n/$IP_SERVIDOR"; done
} > /etc/dnsmasq.d/matriz.conf
# O pacote do Ubuntu lê /etc/dnsmasq.d; o resto da configuração fica no padrão (sem DHCP: o DHCP continua no modem).
dnsmasq --test --conf-file=/etc/dnsmasq.conf
systemctl enable dnsmasq >/dev/null
systemctl restart dnsmasq

passo 'Firewall'
if ufw status | grep -q '^Status: active'; then
    ufw allow proto udp from "$REDE" to "$IP_SERVIDOR" port 53 comment 'DNS local da matriz' >/dev/null
    ufw allow proto tcp from "$REDE" to "$IP_SERVIDOR" port 53 comment 'DNS local da matriz' >/dev/null
    echo "Porta 53 liberada só para a rede da matriz."
fi

passo 'Conferência'
interno=$(dig +short @"$IP_SERVIDOR" chamados.example.com A || true)
externo=$(dig +short @"$IP_SERVIDOR" www.google.com A | head -1 || true)
echo "chamados.example.com → ${interno:-sem resposta} (esperado $IP_SERVIDOR)"
echo "www.google.com → ${externo:-sem resposta} (qualquer IP = repasse funcionando)"
[[ $interno == "$IP_SERVIDOR" && -n $externo ]] || { echo "Algo não respondeu como esperado."; exit 1; }
echo
echo "Pronto. Agora, no modem (Rede → DNSv4): primário $IP_SERVIDOR, secundário ${DNS_CLARO[0]}, marcar a caixa, Aplicar ajustes."
