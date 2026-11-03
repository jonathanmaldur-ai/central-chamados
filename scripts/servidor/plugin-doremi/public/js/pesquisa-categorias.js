// Formulário "Abrir chamado": a pesquisa de "Qual o problema?" (decisão 58).
// A pesquisa do GLPI é "aproximada" (basta as letras aparecerem em ordem): "mouse" caía em Troca de equipamentos
// de pagamento, "wifi" em Periféricos, e "senha" ou "outlook" não achavam nada. Aqui cada palavra digitada precisa
// ser o começo de uma palavra (sem diferença de acento, maiúscula ou hífen: "email" acha "E-mail") do nome do grupo
// ou de um dos problemas dele; o problema que bateu aparece ao lado, e os grupos que batem pelo nome vêm primeiro.
$(function () {
    // uuid da pergunta "Qual o problema?" (uid("q-grupo") no configurar-glpi.py).
    const PERGUNTA = '1e32f6f8-e30c-5642-9449-717f17a13692';
    const bloco = document.querySelector('[data-glpi-form-renderer-uuid="' + PERGUNTA + '"]');
    if (bloco === null) {
        return;
    }

    // Palavras que a loja usa e que não estão nos nomes.
    const SINONIMOS = {
        nf: ['nota fiscal'], nfe: ['nota fiscal'], pc: ['computador'], notebook: ['computador'],
        net: ['internet'], maquina: ['maquininha'], cartao: ['maquininha', 'pinpad'], login: ['senha', 'usuario'],
        cupom: ['comprovante', 'fiscal'],
    };

    const normalizar = function (texto) {
        return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/-/g, '')
            .replace(/[^a-z0-9]+/g, ' ').trim();
    };
    const contem = function (texto, palavra) {
        return (' ' + texto).includes(' ' + palavra);
    };
    const bate = function (texto, palavras) {
        return palavras.every(function (p) {
            return [p].concat(SINONIMOS[p] || []).some(function (s) { return contem(texto, s); });
        });
    };

    let problemas = {};
    $.getJSON(CFG_GLPI.root_doc + '/plugins/doremi/ajax/categorias.php').done(function (r) {
        problemas = {};
        Object.keys(r).forEach(function (grupo) {
            problemas[grupo] = r[grupo].map(function (p) { return { nome: p, normal: normalizar(p) }; });
        });
    });

    const matcher = function (params, data) {
        query = params; // o modelo de resultado do GLPI lê a pesquisa desta variável global
        const palavras = normalizar(params.term || '').split(' ').filter(Boolean);
        if (palavras.length === 0 || !data.id) {
            return palavras.length === 0 ? data : null;
        }
        const grupo = normalizar(data.text);
        const lista = problemas[data.text] || [];
        let achou = null;
        if (bate(grupo, palavras)) {
            data.peloNome = true;
        } else {
            achou = lista.find(function (p) { return bate(grupo + ' ' + p.normal, palavras); });
            if (achou === undefined && !bate(grupo + ' ' + lista.map(function (p) { return p.normal; }).join(' '), palavras)) {
                return null;
            }
            data.peloNome = false;
        }
        data.rendered_text = _.escape(data.text)
            + (achou ? ' <small class="text-muted">· ' + _.escape(achou.nome) + '</small>' : '');
        return data;
    };

    const sorter = function (dados) {
        return dados.filter(function (d) { return d.peloNome; }).concat(dados.filter(function (d) { return !d.peloNome; }));
    };

    // O GLPI liga a pesquisa (select2) depois de montar a página: espera ela existir e troca só a regra de busca.
    let tentativas = 0;
    const trocar = window.setInterval(function () {
        const select2 = $(bloco).find('select').data('select2');
        if (select2 !== undefined) {
            select2.options.set('matcher', matcher);
            select2.options.set('sorter', sorter);
        }
        if (select2 !== undefined || ++tentativas > 50) {
            window.clearInterval(trocar);
        }
    }, 100);
});
