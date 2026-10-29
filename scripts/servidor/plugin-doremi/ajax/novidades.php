<?php

/**
 * Última alteração de um chamado, para a tela dele saber que chegou resposta, solução ou aprovação (decisão 55).
 * Chamado por GET a cada poucos segundos pelo js/novidades.js; só responde a quem pode ver o chamado.
 */

Session::checkLoginUser();

$ticket = new Ticket();
$id = (int) ($_GET['id'] ?? 0);

header('Content-Type: application/json');
if (!$ticket->can($id, READ)) {
    http_response_code(403);
    echo json_encode(['erro' => 'sem acesso']);
    return;
}

echo json_encode(['alterado' => $ticket->fields['date_mod']]);
