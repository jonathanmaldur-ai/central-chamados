<?php

/**
 * Alterna a paleta do usuário logado entre o modo claro ("doremi") e o escuro ("doremi_escuro").
 * Chamado por POST pelo botão do topo; o GLPI confere a sessão e o token CSRF antes de chegar aqui.
 */

Session::checkLoginUser();

$escuro = ($_SESSION['glpipalette'] ?? '') === 'doremi_escuro';
$nova = $escuro ? 'doremi' : 'doremi_escuro';

$user = new User();
$user->update([
    'id'      => Session::getLoginUserID(),
    'palette' => $nova,
]);
$_SESSION['glpipalette'] = $nova;

header('Content-Type: application/json');
echo json_encode(['palette' => $nova]);
