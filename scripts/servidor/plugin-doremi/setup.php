<?php

/**
 * Plugin "Dorémi" da Central de Chamados: botão de modo claro/escuro no topo do GLPI.
 * Troca a paleta do usuário entre "doremi" e "doremi_escuro" (temas em /var/lib/glpi/_themes).
 * Instalado e atualizado pelo scripts/servidor/tema-doremi.sh.
 */

use Glpi\Plugin\Hooks;

define('PLUGIN_DOREMI_VERSION', '1.0.2');

function plugin_version_doremi(): array
{
    return [
        'name'         => 'Dorémi',
        'version'      => PLUGIN_DOREMI_VERSION,
        'author'       => 'TI Dorémi',
        'license'      => 'GPLv3+',
        'homepage'     => '',
        'requirements' => [
            'glpi' => ['min' => '11.0.0', 'max' => '11.99.99'],
        ],
    ];
}

function plugin_init_doremi(): void
{
    global $PLUGIN_HOOKS;

    // Só para quem já entrou: na tela de login vale a paleta padrão.
    $PLUGIN_HOOKS[Hooks::ADD_JAVASCRIPT]['doremi'] = 'js/modo-escuro.js';
}

function plugin_doremi_check_prerequisites(): bool
{
    return true;
}

function plugin_doremi_check_config($verbose = false): bool
{
    return true;
}
