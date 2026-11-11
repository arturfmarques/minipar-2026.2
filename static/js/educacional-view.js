/* Apenas apresentacao de dados recebidos do compilador; nao analisa codigo-fonte. */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.MiniParView = factory();
}(globalThis, function () {
    'use strict';
    const groups = {all:'Todos', keyword:'Palavras-chave', type:'Tipos', identifier:'Identificadores',
        literal:'Literais', operator:'Operadores', delimiter:'Delimitadores', end:'Fim do arquivo', other:'Outros'};
    function tokenCategory(type) {
        if (type === 'TYPE') return 'type';
        if (type === 'IDENTIFIER') return 'identifier';
        if (['NUMBER','STRING_LITERAL','BOOL_LITERAL'].includes(type)) return 'literal';
        if (type === 'END_OF_FILE') return 'end';
        if (['PLUS','MINUS','STAR','SLASH','MOD','ASSIGN','EQ','NEQ','LT','GT','LTE','GTE','AND','OR','NOT','ARROW'].includes(type)) return 'operator';
        if (['LPAREN','RPAREN','LBRACE','RBRACE','LBRACKET','RBRACKET','SEMICOLON','COMMA','DOT'].includes(type)) return 'delimiter';
        return !type || type === 'UNKNOWN' ? 'other' : 'keyword';
    }
    function filterTokens(tokens, category) {
        return tokens.filter(token => category === 'all' || tokenCategory(token.type) === category);
    }
    function layoutTree(root, collapsed) {
        const nodes = []; let leaf = 0, maxDepth = 0;
        function layout(node, depth) {
            maxDepth = Math.max(maxDepth, depth);
            const children = collapsed.has(node.id) ? [] : node.children.map(child => layout(child, depth + 1));
            const y = children.length ? (children[0].y + children[children.length - 1].y)/2 : leaf++ * 80 + 40;
            const record = {node, x:depth * 280 + 16, y, children, width:224, height:44};
            nodes.push(record); return record;
        }
        const focus = layout(root, 0);
        return {nodes, focus, width:maxDepth * 280 + 256, height:Math.max(300, leaf * 80 + 40)};
    }
    function zoomAt(transform, factor, x, y) {
        const k = Math.max(.25, Math.min(3, transform.k * factor));
        return {k, x:x - (x - transform.x) * k / transform.k,
            y:y - (y - transform.y) * k / transform.k};
    }
    return {groups, tokenCategory, filterTokens, layoutTree, zoomAt};
}));
