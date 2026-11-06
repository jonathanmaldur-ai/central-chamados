// Ctrl+V anexa o que está na área de transferência: um print recém-tirado (sem salvar arquivo) ou um arquivo copiado
// no Windows (decisão 60). O campo de anexo do GLPI só aceita escolher ou arrastar; aqui o colar vale na página toda
// e cai no campo de anexo que estiver à vista. Dentro do editor de texto nada muda: ele já cola a imagem no próprio
// texto (fica num iframe, então o colar de lá nem chega aqui).
$(function () {
    const AVISO = 'Ou cole aqui com Ctrl+V: um print, mesmo sem salvar, ou um arquivo copiado.';
    let colados = 0;

    const camposDeAnexo = function () {
        return Array.from(document.querySelectorAll('input[type="file"]')).filter(function (campo) {
            return $(campo).data('blueimp-fileupload') !== undefined;
        });
    };

    // Print não tem nome (o navegador chama de image.png): dá um nome que não se repete no mesmo chamado.
    const nomear = function (arquivo) {
        if (arquivo.name && arquivo.name !== 'image.png') {
            return arquivo;
        }
        colados += 1;
        const agora = new Date();
        const hora = [agora.getHours(), agora.getMinutes(), agora.getSeconds()]
            .map(function (n) { return String(n).padStart(2, '0'); }).join('-');
        const extensao = (arquivo.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
        return new File([arquivo], 'print-' + hora + '-' + colados + '.' + extensao, { type: arquivo.type });
    };

    document.addEventListener('paste', function (e) {
        const dados = e.clipboardData;
        if (!dados || dados.files.length === 0) {
            return;
        }
        // Copiar do Excel traz texto e imagem juntos: num campo de texto, vale o texto.
        const escrevendo = e.target instanceof Element && e.target.closest('input, textarea, [contenteditable="true"]') !== null;
        if (escrevendo && dados.types.includes('text/plain')) {
            return;
        }
        // Primeiro um campo de anexo à vista; senão, o do editor aberto (o das respostas do chamado fica sempre oculto).
        const campos = camposDeAnexo();
        const campo = campos.find(function (c) { return c.offsetParent !== null; })
            || campos.find(function (c) { return c.parentElement.offsetParent !== null; });
        if (campo === undefined) {
            if (window.location.pathname.endsWith('/front/ticket.form.php')) {
                glpi_toast_info('Para anexar, clique em Responder e cole de novo.');
            }
            return;
        }
        e.preventDefault();
        $(campo).fileupload('add', { files: Array.from(dados.files).map(nomear) });
    });

    // A dica fica ao lado do campo. Os campos ocultos dos editores ficam sem ela: sobraria um texto solto na tela.
    camposDeAnexo().forEach(function (campo) {
        if (campo.closest('.only-uploaded-files') !== null) {
            return;
        }
        const dica = document.createElement('div');
        dica.className = 'form-text';
        dica.textContent = AVISO;
        campo.after(dica);
    });
});
