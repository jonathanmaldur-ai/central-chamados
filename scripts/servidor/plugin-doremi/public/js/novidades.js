// Confere a cada 15 segundos, em silêncio, se houve novidade, e só então atualiza (decisão 55).
// Na tela de um chamado (resposta, solução, aprovação): recarrega sozinho se a pessoa não está escrevendo;
// se está no meio de uma resposta ou mexeu em algum campo, só mostra um aviso com o botão de atualizar.
// Na lista de chamados: atualiza só a tabela, e só quando algum chamado mudou ou entrou um novo
// (o recarregamento fixo do GLPI, que mostrava a tela de carregamento a cada minuto, fica desligado).
// Com a aba escondida não confere (nem mantém a sessão viva à toa); ao voltar para a aba, confere na hora.
$(function () {
    const caminho = window.location.pathname;
    const id = Number(new URLSearchParams(window.location.search).get('id'));
    const naLista = caminho.endsWith('/front/ticket.php');
    if (!naLista && !(caminho.endsWith('/front/ticket.form.php') && id > 0)) {
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

    const atualizarLista = function () {
        const lista = $('div.ajax-container.search-display-data');
        if (lista.length > 0 && lista.data('js_class') !== undefined) {
            lista.data('js_class').getView().refreshResults();
        } else {
            window.location.reload();
        }
    };

    const conferir = function () {
        if (document.hidden || avisou) {
            return;
        }
        $.getJSON(CFG_GLPI.root_doc + '/plugins/doremi/ajax/novidades.php', naLista ? {} : { id: id }).done(function (r) {
            if (alteradoAntes === null) {
                alteradoAntes = r.alterado;
            } else if (r.alterado !== alteradoAntes) {
                alteradoAntes = r.alterado;
                if (naLista) {
                    atualizarLista();
                } else {
                    escrevendo() ? avisar() : window.location.reload();
                }
            }
        });
    };

    conferir();
    window.setInterval(conferir, INTERVALO);
    document.addEventListener('visibilitychange', conferir);
});
