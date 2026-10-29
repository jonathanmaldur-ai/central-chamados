// Na tela de um chamado, confere a cada 15 segundos se ele mudou (resposta, solução, aprovação) (decisão 55).
// Mudou e a pessoa não está escrevendo: recarrega sozinho. Está no meio de uma resposta ou mexeu em algum
// campo: só mostra um aviso com o botão de atualizar, para não perder o que foi digitado.
// Com a aba escondida não confere (nem mantém a sessão viva à toa); ao voltar para a aba, confere na hora.
$(function () {
    const id = Number(new URLSearchParams(window.location.search).get('id'));
    if (!window.location.pathname.endsWith('/front/ticket.form.php') || !(id > 0)) {
        return;
    }

    const INTERVALO = 15000;
    let alteradoAntes = null;
    let mexeu = false;
    let avisou = false;

    // Só conta o que a pessoa faz: o GLPI também dispara "change" sozinho ao montar a página.
    ['input', 'keydown', 'paste'].forEach(function (evento) {
        document.addEventListener(evento, function (e) {
            if (e.isTrusted) {
                mexeu = true;
            }
        }, true);
    });

    const escrevendo = function () {
        return mexeu
            || document.querySelector('#new-itilobject-form > .collapse.show, .edit-content.collapse.show') !== null;
    };

    const avisar = function () {
        if (avisou) {
            return;
        }
        avisou = true;
        const aviso = document.createElement('div');
        aviso.className = 'alert alert-info d-flex align-items-center shadow position-fixed bottom-0 end-0 m-3';
        aviso.style.zIndex = 1080;
        aviso.setAttribute('role', 'status');
        aviso.innerHTML = '<i class="ti ti-bell-ringing fs-2 me-2"></i><span class="me-3">Há novidades neste chamado.</span>'
            + '<button type="button" class="btn btn-sm btn-primary">Atualizar</button>';
        aviso.querySelector('button').addEventListener('click', function () { window.location.reload(); });
        document.body.appendChild(aviso);
    };

    const conferir = function () {
        if (document.hidden || avisou) {
            return;
        }
        $.getJSON(CFG_GLPI.root_doc + '/plugins/doremi/ajax/novidades.php', { id: id }).done(function (r) {
            if (alteradoAntes === null) {
                alteradoAntes = r.alterado;
            } else if (r.alterado !== alteradoAntes) {
                escrevendo() ? avisar() : window.location.reload();
            }
        });
    };

    conferir();
    window.setInterval(conferir, INTERVALO);
    document.addEventListener('visibilitychange', conferir);
});
