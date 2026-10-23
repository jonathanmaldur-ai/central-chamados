// Botão de modo claro/escuro no topo do GLPI, ao lado do menu do usuário.
// O ícone mostra o modo para o qual o clique leva (lua no claro, sol no escuro).
$(function () {
    const menuUsuario = document.querySelector('.user-menu');
    if (!menuUsuario || document.getElementById('doremi-modo-escuro')) {
        return;
    }

    const escuro = document.documentElement.dataset.glpiThemeDark === '1';
    const botao = document.createElement('button');
    botao.type = 'button';
    botao.id = 'doremi-modo-escuro';
    botao.className = 'btn btn-ghost-secondary btn-icon me-2';
    botao.title = escuro ? 'Modo claro' : 'Modo escuro';
    botao.setAttribute('aria-label', botao.title);
    botao.innerHTML = `<i class="ti ${escuro ? 'ti-sun' : 'ti-moon'} fs-2"></i>`;

    botao.addEventListener('click', function () {
        botao.disabled = true;
        // O jQuery do GLPI envia o token CSRF em todo POST.
        $.post(CFG_GLPI.root_doc + '/plugins/doremi/ajax/modo-escuro.php')
            .done(function () { window.location.reload(); })
            .fail(function () { botao.disabled = false; });
    });

    menuUsuario.parentElement.insertBefore(botao, menuUsuario);
    menuUsuario.parentElement.classList.add('align-items-center');
});
