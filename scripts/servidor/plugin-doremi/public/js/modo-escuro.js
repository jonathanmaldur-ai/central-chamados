// Botão de modo claro/escuro no topo do GLPI, ao lado do menu do usuário.
// O ícone mostra o modo para o qual o clique leva (lua no claro, sol no escuro).
// O GLPI tem um menu do usuário para celular e outro para computador (um fica escondido): o botão vai nos dois.
$(function () {
    const escuro = document.documentElement.dataset.glpiThemeDark === '1';
    const titulo = escuro ? 'Modo claro' : 'Modo escuro';

    document.querySelectorAll('.user-menu').forEach(function (menuUsuario) {
        if (menuUsuario.parentElement.querySelector('.doremi-modo-escuro')) {
            return;
        }

        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'doremi-modo-escuro btn btn-ghost-secondary btn-icon me-2';
        botao.title = titulo;
        botao.setAttribute('aria-label', titulo);
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

    // O painel (dashboard) tem modo escuro próprio (classe "theme-dark"), com a versão escura de cada quadro.
    // No modo escuro ele liga junto; o painel chega depois da página, por isso o observador.
    if (escuro) {
        const escurecerPaineis = function () {
            document.querySelectorAll('.dashboard:not(.theme-dark)').forEach(function (painel) {
                painel.classList.add('theme-dark');
            });
        };
        escurecerPaineis();
        new MutationObserver(escurecerPaineis).observe(document.body, { childList: true, subtree: true });
    }
});
