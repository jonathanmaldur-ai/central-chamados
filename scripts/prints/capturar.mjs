// Tira os prints dos manuais com os logins de exemplo do preparar.py e grava em manuais/imagens.
//   node ~/central-chamados/scripts/prints/capturar.mjs [nome-do-print ...]
// Roda no próprio servidor: o Chromium sem janela fica em ~/.local/share/central-prints (fora do projeto) e o nome
// da Central é mapeado para o IP interno, porque o modem não faz o retorno para a rede da Matriz (decisão 48).
// Cada print pode marcar onde clicar com um contorno numerado (função marcar).
import { createRequire } from 'node:module';
import { readFileSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = createRequire(join(homedir(), '.local/share/central-prints/'))('playwright');
const URL = 'https://chamados.example.com';
const SAIDA = join(dirname(fileURLToPath(import.meta.url)), '../../manuais/imagens');
const env = Object.fromEntries(readFileSync(join(homedir(), '.config/central-chamados/prints.env'), 'utf8')
    .trim().split('\n').map((l) => l.split(/=(.*)/s).slice(0, 2)));
mkdirSync(SAIDA, { recursive: true });

// Chromium completo (não o "headless shell"), que traz as traduções: o botão de anexo sai em português.
const navegador = await chromium.launch({ channel: 'chromium', env: { ...process.env, LANG: 'pt_BR.UTF-8', LANGUAGE: 'pt_BR' }, args: ['--lang=pt-BR', `--host-resolver-rules=MAP chamados.example.com 192.168.1.10`] });

async function entrar(quem, altura = 768) {
    const [login, senha] = env[quem].split(/:(.*)/s);
    const ctx = await navegador.newContext({ viewport: { width: 1366, height: altura }, locale: 'pt-BR' });
    const p = await ctx.newPage();
    await p.goto(URL + '/', { waitUntil: 'networkidle' });
    await p.getByLabel('Usuário').fill(login);
    await p.getByLabel('Senha').fill(senha);
    await p.getByRole('button', { name: 'Entrar' }).click();
    await p.waitForLoadState('networkidle');
    return p;
}

// Contorno na cor da Dorémi com um número, por cima do elemento (só na imagem; nada é clicado).
async function marcar(p, alvo, numero) {
    const caixa = await alvo.first().boundingBox();
    if (!caixa) throw new Error(`não achei o elemento para marcar ${numero}`);
    await p.evaluate(({ c, n }) => {
        const m = document.createElement('div');
        m.className = 'print-marca';
        Object.assign(m.style, {
            position: 'fixed', left: `${c.x - 5}px`, top: `${c.y - 5}px`, width: `${c.width + 10}px`,
            height: `${c.height + 10}px`, border: '3px solid #e5007e', borderRadius: '8px', zIndex: 99999,
            pointerEvents: 'none', boxShadow: '0 0 0 4px rgba(229,0,126,.15)',
        });
        if (n) {
            const b = document.createElement('div');
            b.textContent = n;
            Object.assign(b.style, {
                position: 'absolute', left: '-16px', top: '-16px', width: '26px', height: '26px', borderRadius: '50%',
                background: '#e5007e', color: '#fff', font: '700 15px/26px sans-serif', textAlign: 'center',
            });
            m.appendChild(b);
        }
        document.body.appendChild(m);
    }, { c: caixa, n: numero });
}

async function foto(p, nome, opcoes = {}) {
    await p.waitForTimeout(400);
    await p.screenshot({ path: join(SAIDA, `${nome}.png`), ...opcoes });
    await p.evaluate(() => document.querySelectorAll('.print-marca').forEach((m) => m.remove()));
    console.log(`  ${nome}.png`);
}

const chamado = (id) => `${URL}/front/ticket.form.php?id=${id}`;
const VISTA = { clip: { x: 0, y: 0, width: 1366, height: 768 } };

// Uma entrada por print, na ordem dos manuais. O nome vira manuais/imagens/<nome>.png.
const PRINTS = {
    async 'loja-login'() {
        const ctx = await navegador.newContext({ viewport: { width: 1366, height: 768 }, locale: 'pt-BR' });
        const p = await ctx.newPage();
        await p.goto(URL + '/', { waitUntil: 'networkidle' });
        await marcar(p, p.getByLabel('Usuário'), 1);
        await marcar(p, p.getByLabel('Senha'), 2);
        await marcar(p, p.getByRole('button', { name: 'Entrar' }), 3);
        await marcar(p, p.getByText('Esqueceu sua senha?'), '?');
        await foto(p, 'loja-login');
        await ctx.close();
    },

    async 'loja-inicio'() {
        const p = await entrar('LOJA', 1000);
        await marcar(p, p.locator('a, .card', { hasText: 'Problemas e pedidos de TI' }).last(), 1);
        await marcar(p, p.locator('a, .card', { hasText: 'Acompanhe os chamados' }).last(), 2);
        await foto(p, 'loja-inicio', { clip: { x: 0, y: 0, width: 1366, height: 800 } });
        await p.context().close();
    },

    async 'loja-formulario'() {
        const p = await entrar('LOJA', 1400);
        await p.getByText('Abrir chamado', { exact: true }).first().click();
        await p.waitForLoadState('networkidle');
        const pergunta = (nome) => p.getByRole('region', { name: nome, exact: true });
        await pergunta('Quem está abrindo o chamado?').locator('input').fill('Ana');
        await escolher(p, pergunta('Setor'), 'Frente de caixa');
        // Pesquisa aberta, como a loja vê ao digitar "caixa".
        await pergunta('Qual o problema?').locator('.select2').click();
        await p.keyboard.type('caixa');
        await p.waitForTimeout(800);
        await marcar(p, pergunta('Qual o problema?').locator('.select2'), 3);
        await foto(p, 'loja-pesquisa', VISTA);
        await p.locator('.select2-results__option', { hasText: 'Sistema de Frente de Caixa' }).first().dispatchEvent('mouseup');
        await p.waitForTimeout(600);
        await escolher(p, pergunta('Qual problema exatamente?'), 'Erro na emissão de NFC-e');
        const caixa = p.getByRole('spinbutton', { name: /número do caixa/i });
        await caixa.fill('3');
        await pergunta('Descreva o que aconteceu').locator('iframe').contentFrame().locator('body')
            .fill('Ao finalizar a venda aparece "Rejeição 999" e a nota não sai.');
        await p.getByText('Não, dá para continuar').click();
        await marcar(p, pergunta('Quem está abrindo o chamado?').locator('input'), 1);
        await marcar(p, pergunta('Setor').locator('.select2'), 2);
        await marcar(p, pergunta('Qual o problema?').locator('.select2'), 3);
        await marcar(p, pergunta('Qual problema exatamente?').locator('.select2'), 4);
        await marcar(p, caixa, 5);
        await marcar(p, pergunta('Descreva o que aconteceu').locator('.tox-tinymce'), 6);
        await marcar(p, pergunta('Foto ou print').locator('input[type=file]').locator('xpath=ancestor::div[1]'), 7);
        await marcar(p, pergunta('Isso está impedindo de vender ou de trabalhar?').locator('.form-check').first()
            .locator('xpath=..'), 8);
        await marcar(p, p.getByRole('button', { name: 'Enviar' }), 9);
        const fim = await p.getByRole('button', { name: 'Enviar' }).boundingBox();
        await foto(p, 'loja-formulario', { clip: { x: 150, y: 100, width: 1066, height: fim.y + fim.height + 30 - 100 } });
        await p.context().close();
    },

    async 'loja-meus-chamados'() {
        const p = await entrar('LOJA');
        await p.goto(URL + '/front/ticket.php', { waitUntil: 'networkidle' });
        await marcar(p, p.locator('a', { hasText: 'Frente de Caixa (PDV) > Sistema de Frente de Caixa' }), 1);
        await foto(p, 'loja-meus-chamados', { clip: { x: 0, y: 0, width: 1366, height: 360 } });
        await p.context().close();
    },

    async 'loja-chamado'() {
        const p = await entrar('LOJA');
        await p.goto(chamado(env.ATENDIMENTO), { waitUntil: 'networkidle' });
        await marcar(p, p.getByRole('button', { name: 'Responder' }), 1);
        await foto(p, 'loja-chamado', VISTA);
        await p.context().close();
    },

    async 'loja-solucao'() {
        const p = await entrar('LOJA');
        await p.goto(chamado(env.SOLUCIONADO), { waitUntil: 'networkidle' });
        await marcar(p, p.getByRole('button', { name: 'Aprovar' }), 2);
        await marcar(p, p.getByRole('button', { name: 'Recusar' }), 3);
        await foto(p, 'loja-solucao', VISTA);
        await p.context().close();
    },

    async 'gestao-painel'() {
        const p = await entrar('GESTAO');
        await foto(p, 'gestao-painel', VISTA);
        await p.context().close();
    },

    async 'gestao-aprovacao'() {
        const p = await entrar('GESTAO');
        await p.goto(chamado(env.APROVACAO), { waitUntil: 'networkidle' });
        await marcar(p, p.getByRole('tab', { name: /Aprovações/ }).or(p.locator('a', { hasText: 'Aprovações' })), 2);
        await marcar(p, p.getByRole('button', { name: 'Aprovar' }), 3);
        await marcar(p, p.getByRole('button', { name: 'Recusar' }), 3);
        await foto(p, 'gestao-aprovacao', VISTA);
        await p.context().close();
    },

    async 'gestao-lista'() {
        const p = await entrar('GESTAO');
        await p.goto(URL + '/front/ticket.php', { waitUntil: 'networkidle' });
        await marcar(p, p.getByText('Pesquisar', { exact: true }).first(), 1);
        await marcar(p, p.locator('[title*="xportar"], [aria-label*="xportar"], .dropdown-toggle:has(.ti-download)').first(), 2);
        await foto(p, 'gestao-lista', { clip: { x: 0, y: 0, width: 1366, height: 530 } });
        await p.context().close();
    },

    async 'tecnico-chamado'() {
        const p = await entrar('TECNICO');
        await p.goto(chamado(env.ATENDIMENTO), { waitUntil: 'networkidle' });
        await p.locator('.timeline-buttons .dropdown-toggle-split, button.dropdown-toggle-split').first().click();
        await p.waitForTimeout(400);
        await marcar(p, p.getByText('Adicionar uma solução').locator('xpath=ancestor::ul[1]'), 2);
        await marcar(p, p.getByRole('button', { name: 'Responder' }), 1);
        await foto(p, 'tecnico-chamado', VISTA);
        await p.context().close();
    },
};

// Escolhe uma opção numa lista do formulário (select2): abre, pesquisa se tiver pesquisa e clica na opção.
async function escolher(p, pergunta, opcao, pesquisa) {
    await pergunta.locator('.select2').click();
    if (pesquisa) {
        await p.keyboard.type(pesquisa);
        await p.waitForTimeout(800);
    }
    // O select2 escolhe no "mouseup"; disparar o evento direto evita clicar fora do lugar se a lista rolar.
    const item = p.locator('.select2-container--open .select2-results__option[role=option]', { hasText: opcao }).last();
    await item.waitFor();
    await item.dispatchEvent('mouseup');
    await p.waitForTimeout(500);
}

const pedidos = process.argv.slice(2);
try {
    for (const [nome, fazer] of Object.entries(PRINTS)) {
        if (!pedidos.length || pedidos.includes(nome)) await fazer();
    }
} finally {
    await navegador.close();
}
