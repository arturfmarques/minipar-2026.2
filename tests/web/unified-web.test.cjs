const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const workspace = require('../../static/js/web-common.js');
const view = require('../../static/js/educacional-view.js');

function environment(route, storage = new Map()) {
    const links = ['/', '/educacional'].map(href => ({
        getAttribute: () => href,
        addEventListener: (_, handler) => { links.find(link => link.getAttribute() === href).click = handler; }
    }));
    return {location:{pathname:route}, document:{querySelectorAll:() => links}, links, storage,
        sessionStorage:{getItem:key => storage.get(key) ?? null,
            setItem:(key, value) => storage.set(key, value), removeItem:key => storage.delete(key)}};
}

for (const [from, to] of [['/', '/educacional'], ['/educacional', '/']]) {
    test(`fonte e nome atravessam ${from} -> ${to} uma unica vez`, () => {
        const env = environment(from);
        const source = 'func f(number n) -> number { return n*n; }\nvar t=fork local f(8) on core(0); print(join(t));';
        workspace.connect({read:() => ({code:source, filename:'teste11_minicompilador_armv7.minipar'}), write:() => assert.fail()}, env);
        env.links.find(link => link.getAttribute() === to).click({button:0});
        let restored = null;
        assert.equal(workspace.connect({write:draft => { restored = draft; }}, environment(to,env.storage)), true);
        assert.deepEqual(restored, {code:source, filename:'teste11_minicompilador_armv7.minipar'});
        assert.equal(env.storage.size, 0);
        assert.equal(workspace.connect({write:() => assert.fail()}, environment(to,env.storage)), false);
    });
}

test('fonte vazia e valida; nome inseguro nao entra no contrato de arquivos', () => {
    const env = environment('/');
    workspace.connect({read:() => ({code:'', filename:'../escape.minipar'})}, env);
    env.links[1].click({button:0});
    let restored;
    workspace.connect({write:draft => { restored = draft; }}, environment('/educacional',env.storage));
    assert.deepEqual(restored, {code:'', filename:'ide_temp.minipar'});
});

test('storage bloqueado nao impede a navegacao normal', () => {
    const env = environment('/');
    env.sessionStorage = {getItem:() => { throw Error('blocked'); }, removeItem:() => { throw Error('blocked'); }};
    assert.doesNotThrow(() => workspace.connect({read:() => ({code:'print(1);'})}, env));
    assert.doesNotThrow(() => env.links[1].click({button:0}));
});

test('clique no modo atual e abertura em outra aba nao criam passagem de fonte', () => {
    const env = environment('/');
    workspace.connect({read:() => ({code:'print(1);'})}, env);
    env.links[0].click({button:0});
    env.links[1].click({button:0, ctrlKey:true});
    env.links[1].click({button:1});
    assert.equal(env.storage.size, 0);
});

test('dados corrompidos, destino incorreto e fonte excessiva nao sobrescrevem o editor', () => {
    for (const raw of ['{', JSON.stringify({destination:'/',code:'wrong'}), JSON.stringify({destination:'/educacional',code:42})]) {
        const env = environment('/educacional',new Map([['minipar.web.source.v1',raw]]));
        assert.equal(workspace.connect({write:() => assert.fail()},env),false);
        assert.equal(env.storage.size,0);
    }
    const env = environment('/');
    workspace.connect({read:() => ({code:'x'.repeat(300001)})},env);
    env.links[1].click({button:0});
    assert.equal(env.storage.size,0);
});

const data = JSON.parse(fs.readFileSync(process.env.MINIPAR_UI_DATA,'utf8'));
test('filtros usam os tokens reais sem renumerar ou alterar lexemas/localizacoes', () => {
    const before = JSON.stringify(data.tokens);
    for (const token of view.filterTokens(data.tokens,'identifier')) assert.equal(token.type,'IDENTIFIER');
    assert.ok(view.filterTokens(data.tokens,'identifier').some(token => token.lexeme === 'core'));
    assert.ok(view.filterTokens(data.tokens,'operator').some(token => token.lexeme === '+'));
    assert.equal(view.filterTokens(data.tokens,'end').length,1);
    assert.equal(view.filterTokens(data.tokens,'all').length,data.tokens.length);
    assert.deepEqual(view.filterTokens(data.tokens,'literal').map(token => token.number),
        data.tokens.filter(token => ['NUMBER','STRING_LITERAL','BOOL_LITERAL'].includes(token.type)).map(token => token.number));
    assert.equal(JSON.stringify(data.tokens),before);
});

function allNodes(node) { return [node, ...node.children.flatMap(allNodes)]; }
test('AST real do Teste 11 conserva todos os nos e nao sobrepoe retangulos', () => {
    const nodes = allNodes(data.large_ast);
    assert.ok(nodes.length > 1000);
    const before = JSON.stringify(data.large_ast);
    const geometry = view.layoutTree(data.large_ast,new Set());
    assert.equal(geometry.nodes.length,nodes.length);
    assert.equal(new Set(geometry.nodes.map(item => item.node.id)).size,nodes.length);
    const columns = new Map();
    for (const item of geometry.nodes) {
        if (!columns.has(item.x)) columns.set(item.x,[]);
        columns.get(item.x).push(item);
    }
    for (const column of columns.values()) {
        column.sort((a,b) => a.y-b.y);
        for (let i=1;i<column.length;i++) assert.ok(column[i].y-column[i-1].y >= column[i].height);
    }
    assert.equal(JSON.stringify(data.large_ast),before);
});

test('recolher e expandir muda somente a geometria visivel da AST', () => {
    const collapsed = new Set();
    function fold(node, depth) { if (depth >= 2 && node.children.length) collapsed.add(node.id); node.children.forEach(child => fold(child,depth+1)); }
    fold(data.large_ast,0);
    const visible = view.layoutTree(data.large_ast,collapsed).nodes.length;
    assert.ok(visible < 350 && visible < allNodes(data.large_ast).length);
    collapsed.clear();
    assert.equal(view.layoutTree(data.large_ast,collapsed).nodes.length,allNodes(data.large_ast).length);
    assert.ok(allNodes(data.small_ast).some(node => node.edge === 'core'));
});

test('zoom preserva o ponto sob o cursor e respeita os limites', () => {
    const initial = {x:21,y:-43,k:1};
    const next = view.zoomAt(initial,1.25,300,200);
    assert.equal((300-initial.x)/initial.k,(300-next.x)/next.k);
    assert.equal((200-initial.y)/initial.k,(200-next.y)/next.k);
    assert.deepEqual(view.zoomAt(next,.8,300,200),initial);
    assert.equal(view.zoomAt(initial,100,0,0).k,3);
    assert.equal(view.zoomAt(initial,.001,0,0).k,.25);
});
