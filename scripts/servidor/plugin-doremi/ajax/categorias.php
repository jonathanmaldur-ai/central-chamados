<?php

/**
 * Problemas de cada grupo do formulário "Abrir chamado", para a pesquisa de "Qual o problema?" achar o grupo
 * também pelo nome dos problemas (ex.: "outlook" acha E-mail, "senha" acha Acessos e Usuários) (decisão 58).
 * Responde { "nome completo do grupo": ["problema", ...] }; chamado uma vez pelo js/pesquisa-categorias.js.
 */

Session::checkLoginUser();

global $DB;
$nomes = [];
$pais = [];
foreach ($DB->request(['SELECT' => ['id', 'itilcategories_id', 'completename', 'name'], 'FROM' => 'glpi_itilcategories']) as $c) {
    $nomes[$c['id']] = $c['completename'];
    $pais[$c['id']] = [$c['itilcategories_id'], $c['name']];
}

$problemas = [];
foreach ($pais as [$pai, $nome]) {
    if (isset($nomes[$pai])) {
        $problemas[$nomes[$pai]][] = $nome;
    }
}

header('Content-Type: application/json');
echo json_encode($problemas);
