<?php

/**
 * Última alteração de um chamado, para a tela dele saber que chegou resposta, solução ou aprovação (decisão 55).
 * Sem id, responde pela lista de chamados: a última alteração e o total dos chamados que a pessoa vê,
 * para a lista só recarregar quando houver novidade (em vez de recarregar a cada minuto).
 * Chamado por GET a cada poucos segundos pelo js/novidades.js; só responde a quem pode ver o chamado.
 */

use Glpi\DBAL\QueryExpression;
use Glpi\DBAL\QuerySubQuery;

Session::checkLoginUser();

header('Content-Type: application/json');
$id = (int) ($_GET['id'] ?? 0);

if ($id === 0) {
    global $DB;
    $where = getEntitiesRestrictCriteria('glpi_tickets');
    if (!Session::haveRight('ticket', Ticket::READALL)) {
        $where[] = ['id' => new QuerySubQuery([
            'SELECT' => 'tickets_id',
            'FROM'   => 'glpi_tickets_users',
            'WHERE'  => ['users_id' => Session::getLoginUserID()],
        ])];
    }
    $linha = $DB->request([
        'SELECT' => [
            new QueryExpression('MAX(' . $DB->quoteName('date_mod') . ') AS ' . $DB->quoteName('alterado')),
            new QueryExpression('COUNT(*) AS ' . $DB->quoteName('total')),
        ],
        'FROM'   => 'glpi_tickets',
        'WHERE'  => $where,
    ])->current();
    echo json_encode(['alterado' => $linha['alterado'] . '|' . $linha['total']]);
    return;
}

$ticket = new Ticket();
if (!$ticket->can($id, READ)) {
    http_response_code(403);
    echo json_encode(['erro' => 'sem acesso']);
    return;
}

echo json_encode(['alterado' => $ticket->fields['date_mod']]);
