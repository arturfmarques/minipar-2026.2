/* UI de apresentação. Tokens, AST, semântica, TAC e C++ vêm sempre do backend. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const source = $('source-editor');
  const gutter = $('fallback-gutter');
  const panel = $('panel-body');
  const messages = $('messages');
  const runButton = $('run-button');
  const stageButtons = [...document.querySelectorAll('[data-stage]')];
  const state = {editor: null, job: null, cpp: null, tac: null, ast: null,
    selectedStage: null, request: 0, lineMarks: [], downloads: {}, astView: null, sourceName: 'ide_temp.minipar'};

  if (window.CodeMirror) {
    CodeMirror.defineMode('minipar', () => ({token(stream) {
      if (stream.match(/#.*/)) return 'comment';
      if (stream.match(/"(?:\\.|[^"\\])*"/)) return 'string';
      if (stream.match(/\b(?:class|extends|new|func|return|var|number|int|string|bool|void|list|task|if|else|while|do|for|in|break|continue|seq|par|fork|join|local|remote|this|c_channel|send|receive|input|print|matrix)\b/)) return 'keyword';
      if (stream.match(/\b(?:true|false|\d+(?:\.\d+)?)\b/)) return 'number';
      stream.next(); return null;
    }}));
    state.editor = CodeMirror.fromTextArea(source, {mode: 'minipar', lineNumbers: true,
      indentUnit: 4, tabSize: 4, indentWithTabs: false, lineWrapping: false,
      extraKeys: {'Ctrl-Enter': () => compile(), 'Tab': cm => cm.replaceSelection('    '),
        'Enter': cm => {
          const line = cm.getLine(cm.getCursor().line).slice(0, cm.getCursor().ch);
          const indent = (line.match(/^\s*/) || [''])[0] + (/\{\s*$/.test(line) ? '    ' : '');
          cm.replaceSelection('\n' + indent, 'end');
        }}});
    gutter.hidden = true;
    state.editor.on('change', changed);
  } else {
    source.addEventListener('input', changed);
    source.addEventListener('scroll', () => { gutter.scrollTop = source.scrollTop; });
    source.addEventListener('keydown', event => {
      if (event.key === 'Tab') {
        event.preventDefault(); const start = source.selectionStart;
        source.setRangeText('    ', start, source.selectionEnd, 'end'); changed();
      }
      if (event.key === 'Enter' && !event.ctrlKey) {
        event.preventDefault();
        const before = source.value.slice(0, source.selectionStart).split('\n').at(-1);
        const indent = (before.match(/^\s*/) || [''])[0] + (/\{\s*$/.test(before) ? '    ' : '');
        source.setRangeText('\n' + indent, source.selectionStart, source.selectionEnd, 'end'); changed();
      }
      if (event.key === 'Enter' && event.ctrlKey) { event.preventDefault(); compile(); }
    });
  }

  function code() { return state.editor ? state.editor.getValue() : source.value; }
  function setCode(value) { if (state.editor) state.editor.setValue(value); else { source.value = value; changed(); } }
  function status(text, type='idle') { const badge = $('state-badge'); badge.textContent = text; badge.className = 'state-badge ' + type; }
  function clearMarks() {
    if (state.editor) {
      for (const line of state.lineMarks) state.editor.removeLineClass(line, 'background', 'error-line');
      state.lineMarks = [];
    }
  }
  function goTo(line, column=1) {
    const index = Math.max(0, line - 1);
    const ch = Math.max(0, column - 1);
    if (state.editor) { state.editor.focus(); state.editor.setCursor(index, ch); state.editor.scrollIntoView({line: index, ch}, 60); }
    else {
      const offset = Math.min(code().length, code().split('\n').slice(0, index).reduce((n, text) => n + text.length + 1, 0) + ch);
      source.focus(); source.setSelectionRange(offset, offset);
    }
  }
  function changed() {
    state.astView?.dispose(); state.astView = null;
    state.request++;
    state.job = null; state.ast = null; state.cpp = null; state.tac = null;
    state.downloads = {}; state.artifacts = []; runButton.disabled = true; $('downloads').hidden = true;
    state.selectedStage = null;
    stageButtons.forEach(button => button.classList.remove('active'));
    panel.replaceChildren(element('div', 'empty-state', 'Fonte alterada. Selecione uma etapa para analisar o código atual.'));
    phases();
    clearMarks(); messages.replaceChildren();
    const count = code().split('\n').length;
    $('source-lines').textContent = count + (count === 1 ? ' linha' : ' linhas');
    if (!state.editor) gutter.textContent = Array.from({length: count}, (_, i) => i + 1).join('\n');
    status('Fonte alterada');
    $('execution-console').open = false;
    $('console-status').textContent = 'Fonte alterada';
    $('console-output').textContent = 'Compile novamente para executar o código atual.';
  }
  changed();

  async function post(url, data) {
    const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const payload = await response.json();
    if (!response.ok && !payload.analysis && !payload.execution && !payload.compilation) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function intro(text) { panel.replaceChildren(element('p', 'panel-intro', text)); }
  function errors(items=[]) {
    messages.replaceChildren(); clearMarks();
    for (const item of items) {
      const row = element('div', 'message');
      const place = element('button', '', `Linha ${item.line}, coluna ${item.column}`);
      place.type = 'button'; place.addEventListener('click', () => goTo(item.line, item.column));
      row.append(place, document.createTextNode(` · ${item.phase}: ${item.message}`));
      messages.append(row);
      if (state.editor && item.line > 0 && item.line <= state.editor.lineCount()) {
        const line = state.editor.getLineHandle(item.line - 1);
        state.editor.addLineClass(line, 'background', 'error-line'); state.lineMarks.push(line);
      }
    }
  }
  function phases(values={}) {
    const strip = $('phase-strip'); strip.replaceChildren();
    for (const [name, label] of [['tokens','Lexer'],['ast','Parser / AST'],['semantic','Semântica'],['tac','TAC'],['cpp','C++'],['compile','G++']]) {
      const phase = values[name];
      if (!phase || phase === 'não executada') continue;
      const pill = element('span', 'phase-pill ' + phase, `${label} ${phase === 'aprovada' ? '✓' : '×'}`);
      pill.setAttribute('aria-label', `${label}: ${phase}`); strip.append(pill);
    }
    strip.hidden = !strip.childNodes.length;
  }
  phases();
  function chooseStage(stage) {
    state.selectedStage = stage;
    for (const button of stageButtons) button.classList.toggle('active', button.dataset.stage === stage);
  }
  function table(headers, rows, onRow) {
    const container = element('div'); container.style.overflowX = 'auto';
    const table = element('table', 'data-table'); const thead = element('thead'); const tr = element('tr');
    for (const h of headers) tr.append(element('th', '', h));
    thead.append(tr); table.append(thead);
    const body = element('tbody');
    rows.forEach((row, index) => {
      const tr = element('tr');
      for (const value of row) tr.append(element('td', '', String(value ?? '')));
      if (onRow) {
        tr.tabIndex = 0;
        tr.addEventListener('click', () => onRow(index));
        tr.addEventListener('keydown', event => { if (event.key === 'Enter') onRow(index); });
      }
      body.append(tr);
    });
    table.append(body); container.append(table); return container;
  }
  function showTokens(result) {
    intro('Tokens do programa MiniPar. Selecione uma linha para localizar no fonte.');
    const bar = element('div', 'token-filter');
    const label = element('label', '', 'Categoria'); label.htmlFor = 'token-category';
    const select = element('select'); select.id = 'token-category';
    for (const [value, name] of Object.entries(MiniParView.groups)) {
      const option = element('option', '', name); option.value = value; select.append(option);
    }
    const count = element('output'); const rows = element('div');
    bar.append(label, select, count); panel.append(bar, rows);
    function render() {
      const tokens = MiniParView.filterTokens(result.tokens, select.value);
      count.textContent = `${tokens.length} / ${result.tokens.length} tokens`;
      rows.replaceChildren(table(['Nº','Tipo','Lexema','Linha:coluna'], tokens.map(t =>
        [t.number, t.type, t.lexeme || '∅', `${t.line}:${t.column}`]), index => goTo(tokens[index].line, tokens[index].column)));
    }
    select.addEventListener('change', render); render();
  }
  function showSemantic(result) {
    intro(result.success ? 'Tabela de símbolos · análise aprovada.' : 'Tabela parcial · veja os diagnósticos.');
    const rows = (result.symbols || []).map(s => [s.name, s.category, s.type, s.scope,
      Object.entries(s.details || {}).map(([k,v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join(' · ') || '—']);
    panel.append(table(['Nome','Categoria','Tipo','Escopo','Informações'], rows));
  }
  function escapeHTML(value) { return value.replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
  function highlight(line, language) {
    const regex = language === 'cpp'
      ? /("(?:\\.|[^"\\])*"|\/\/.*|\b(?:auto|class|const|double|else|for|if|int|return|std|struct|template|void|while|public|private|try|catch)\b|\b\d+(?:\.\d+)?\b)/g
      : /(#.*|\b(?:func|endfunc|scope_begin|scope_end|class|endclass|fork|join|goto|call|param|spawn|return|if)\b|\b\d+(?:\.\d+)?\b)/g;
    let html = '', last = 0, match;
    while ((match = regex.exec(line))) {
      html += escapeHTML(line.slice(last, match.index));
      const token = match[0]; const kind = token.startsWith('#') || token.startsWith('//') ? 'comment' : token.startsWith('"') ? 'string' : /^\d/.test(token) ? 'literal' : 'keyword';
      html += `<span class="${kind}">${escapeHTML(token)}</span>`; last = regex.lastIndex;
    }
    return html + escapeHTML(line.slice(last));
  }
  function showCode(text, language, title) {
    intro(title);
    const bar = element('div', 'code-toolbar');
    const copy = element('button', 'utility-button', 'Copiar código'); copy.type = 'button';
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(text); copy.textContent = 'Copiado'; }
      catch (_) { status('Cópia indisponível; selecione o código para copiar.', 'error'); }
    });
    bar.append(copy);
    if (language === 'cpp' || language === 'tac') {
      const save = element('button', 'utility-button', 'Baixar .' + language); save.type = 'button';
      save.addEventListener('click', () => {
        if (state.downloads[language]) { window.location.href = state.downloads[language]; return; }
        const url = URL.createObjectURL(new Blob([text], {type:language === 'cpp' ? 'text/x-c++src' : 'text/plain'}));
        const link = element('a'); link.href = url; link.download = state.sourceName.replace(/\.minipar$/, '.' + language); link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }); bar.append(save);
    }
    panel.append(bar);
    const codePanel = element('div', 'code-display');
    text.replace(/\n$/, '').split('\n').forEach((line, index) => {
      const row = element('div', 'code-line');
      row.append(element('span', 'line-number', String(index + 1)));
      const content = element('code'); content.innerHTML = highlight(line, language); row.append(content);
      codePanel.append(row);
    });
    panel.append(codePanel);
  }

  const svgNS = 'http://www.w3.org/2000/svg';
  function svg(tag, attributes={}) {
    const node = document.createElementNS(svgNS, tag);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
    return node;
  }
  function createTree(root, count) {
    const byId = new Map(), parents = new Map(), collapsed = new Set();
    function index(node, depth, parent) {
      byId.set(node.id, node); if (parent) parents.set(node.id, parent);
      if (depth >= 2 && node.children.length) collapsed.add(node.id);
      node.children.forEach(child => index(child, depth + 1, node.id));
    }
    index(root, 0, null);
    const view = {root, focus: root.id, byId, parents, collapsed, selected: root.id,
      transform: {x:25,y:30,k:1}, count, nodes: []};
    const toolbar = element('div', 'tree-toolbar');
    for (const [label, action, description] of [['＋','in','Ampliar árvore'], ['－','out','Reduzir árvore'], ['Centralizar','center','Centralizar árvore'], ['Voltar','back','Voltar à árvore pai'], ['Recolher','collapse','Recolher subárvore']]) {
      const button = element('button', '', label); button.type = 'button'; button.setAttribute('aria-label', description);
      button.addEventListener('click', () => {
        if (action === 'in' || action === 'out') view.transform = MiniParView.zoomAt(view.transform, action === 'in' ? 1.25 : .8, canvas.clientWidth/2, canvas.clientHeight/2);
        if (action === 'back') { view.focus = view.parents.get(view.focus) || view.root.id; view.selected = view.focus; view.collapsed.delete(view.focus); render(true); return; }
        if (action === 'collapse') {
          function fold(node, depth) { if (depth && node.children.length) view.collapsed.add(node.id); node.children.forEach(child => fold(child, depth + 1)); }
          fold(view.byId.get(view.focus), 0); view.collapsed.delete(view.focus); render(true); return;
        }
        if (action === 'center') { fit(); return; }
        applyTransform();
      }); toolbar.append(button);
    }
    const focusChoice = element('select'); focusChoice.setAttribute('aria-label', 'Navegar por declarações da AST');
    const placeholder = element('option', '', 'Ir para declaração…'); placeholder.value = ''; focusChoice.append(placeholder);
    for (const node of [root, ...root.children]) {
      const option = element('option', '', node.type + (node.details.name ? ' · ' + node.details.name : ''));
      option.value = node.id; focusChoice.append(option);
    }
    focusChoice.addEventListener('change', () => {
      if (!focusChoice.value) return;
      view.focus = focusChoice.value; view.selected = view.focus; view.collapsed.delete(view.focus); render(true);
    });
    const summary = element('span', 'tree-summary'); toolbar.append(focusChoice, summary);
    panel.append(toolbar);
    const wrap = element('div', 'tree-wrap'); const canvas = element('div', 'tree-canvas');
    const graphic = svg('svg', {'aria-label':'Árvore sintática interativa', role:'group'});
    const layer = svg('g'); graphic.append(layer); canvas.append(graphic);
    const details = element('aside', 'node-details'); wrap.append(canvas, details); panel.append(wrap);
    let dimension = {width:500,height:340}, geometry = null;
    function visibleCount(node, remaining=351) {
      let used = 1;
      if (!view.collapsed.has(node.id)) for (const child of node.children) {
        used += visibleCount(child, remaining - used); if (used > remaining) break;
      }
      return used;
    }
    function applyTransform() { layer.setAttribute('transform', `translate(${view.transform.x} ${view.transform.y}) scale(${view.transform.k})`); }
    function fit() {
      const width = Math.max(canvas.clientWidth, 300), height = Math.max(canvas.clientHeight, 300);
      const ideal = Math.min(1, (width - 40) / dimension.width, (height - 40) / dimension.height);
      view.transform.k = Math.max(.8, ideal);
      view.transform.x = ideal >= .8 ? (width - dimension.width * view.transform.k)/2 : 20;
      view.transform.y = ideal >= .8 ? (height - dimension.height * view.transform.k)/2 : height/2 - geometry.focus.y * view.transform.k;
      applyTransform();
    }
    function detail(node) {
      details.replaceChildren(element('h4', '', node.type));
      const dl = element('dl');
      const pairs = [['Aresta',node.edge],['Linha',node.line],['Coluna',node.column],
        ['Filhos',node.children.length], ...Object.entries(node.details)];
      for (const [key,value] of pairs) {
        dl.append(element('dt', '', key), element('dd', '', typeof value === 'string' ? value : JSON.stringify(value)));
      }
      details.append(dl);
      const locate = element('button', 'utility-button', 'Ir para o fonte'); locate.type = 'button';
      locate.addEventListener('click', () => goTo(node.line, node.column)); details.append(locate);
      if (node.children.length) {
        const enter = element('button', 'utility-button', 'Entrar na subárvore');
        enter.type = 'button'; enter.style.marginTop = '12px';
        enter.addEventListener('click', () => { view.focus = node.id; view.collapsed.delete(node.id); render(true); });
        details.append(enter);
      }
    }
    function render(center=false, anchor=null) {
      const before = geometry?.nodes.find(item => item.node.id === anchor);
      layer.replaceChildren();
      geometry = MiniParView.layoutTree(view.byId.get(view.focus), view.collapsed);
      const nodes = geometry.nodes; dimension = geometry;
      summary.textContent = `${nodes.length} visíveis / ${count.toLocaleString('pt-BR')} nós`;
      focusChoice.value = [...focusChoice.options].some(option => option.value === view.focus) ? view.focus : '';
      for (const item of nodes) for (const child of item.children) {
        layer.append(svg('path', {class:'edge', d:`M ${item.x+item.width} ${item.y} C ${item.x+item.width+28} ${item.y}, ${child.x-28} ${child.y}, ${child.x} ${child.y}`}));
      }
      for (const item of nodes) {
        const node = item.node, group = svg('g', {class:'node' + (node.id === view.selected ? ' selected' : ''),
          transform:`translate(${item.x} ${item.y-22})`, 'data-node-id':node.id, tabindex:0, role:'button', 'aria-label':`${node.type}, linha ${node.line}`});
        group.append(svg('rect', {width:item.width,height:item.height}));
        const text = svg('text', {x:9,y:17}); text.textContent = node.type; group.append(text);
        const value = node.details.name ?? node.details.op ?? node.details.value ?? '';
        const caption = [node.edge, String(value).replace(/\s+/g, ' ')].filter(Boolean).join(' · ') || `linha ${node.line}`;
        const sub = svg('text', {x:9,y:34,class:'node-caption'}); sub.textContent = caption.length > 29 ? caption.slice(0,28) + '…' : caption;
        const hint = svg('title'); hint.textContent = `${node.type} · ${caption}`; group.append(sub, hint);
        if (node.children.length) {
          group.setAttribute('aria-expanded', String(!view.collapsed.has(node.id)));
          const toggle = svg('text', {x:206,y:17,class:'toggle'});
          toggle.textContent = view.collapsed.has(node.id) ? '+' : '−'; group.append(toggle);
        }
        function selectNode(event) {
          event.stopPropagation(); view.selected = node.id; detail(node);
          if (node.children.length) {
            if (view.collapsed.has(node.id)) {
              view.collapsed.delete(node.id);
              if (visibleCount(view.byId.get(view.focus)) > 350) {
                view.collapsed.add(node.id);
                status('Vista cheia · entre na subárvore', 'working');
              }
            } else view.collapsed.add(node.id);
          }
          render(false, node.id);
        }
        group.addEventListener('click', selectNode);
        group.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectNode(event); } });
        layer.append(group);
      }
      detail(view.byId.get(view.selected));
      if (center) fit();
      else {
        const after = nodes.find(item => item.node.id === anchor);
        if (before && after) { view.transform.x += (before.x - after.x) * view.transform.k; view.transform.y += (before.y - after.y) * view.transform.k; }
        applyTransform();
      }
    }
    let drag = null;
    graphic.addEventListener('pointerdown', event => { drag = {x:event.clientX,y:event.clientY,tx:view.transform.x,ty:view.transform.y}; graphic.setPointerCapture(event.pointerId); canvas.classList.add('dragging'); });
    graphic.addEventListener('pointermove', event => {
      if (!drag) return; view.transform.x = drag.tx + event.clientX-drag.x; view.transform.y = drag.ty + event.clientY-drag.y; applyTransform();
    });
    graphic.addEventListener('pointerup', () => { drag = null; canvas.classList.remove('dragging'); });
    graphic.addEventListener('pointercancel', () => { drag = null; canvas.classList.remove('dragging'); });
    graphic.addEventListener('wheel', event => {
      event.preventDefault(); const rect = graphic.getBoundingClientRect();
      view.transform = MiniParView.zoomAt(view.transform, event.deltaY < 0 ? 1.12 : .89, event.clientX - rect.left, event.clientY - rect.top); applyTransform();
    }, {passive:false});
    const observer = window.ResizeObserver ? new ResizeObserver(fit) : null;
    view.dispose = () => observer?.disconnect();
    render(true); observer?.observe(canvas); return view;
  }
  async function analyze(stage) {
    state.astView?.dispose(); state.astView = null;
    chooseStage(stage); const ticket = ++state.request;
    status('Analisando ' + stage + '…', 'working');
    messages.replaceChildren(); panel.replaceChildren();
    try {
      const result = await post('/api/educacional/analyze', {code:code(), stage});
      if (ticket !== state.request) return;
      phases(result.phases); errors(result.diagnostics);
      status(result.success ? 'Etapa aprovada' : 'Etapa reprovada', result.success ? 'ok' : 'error');
      if (stage === 'tokens' && result.tokens) showTokens(result);
      else if (stage === 'ast' && result.ast) { intro('AST do programa MiniPar · selecione um nó ou entre em uma subárvore.'); state.ast = result.ast; state.astView = createTree(result.ast, result.node_count); }
      else if (stage === 'semantic' && result.symbols) showSemantic(result);
      else if (stage === 'tac' && result.tac !== undefined) { state.tac = result.tac; showCode(result.tac, 'tac', 'TAC do programa MiniPar.'); }
      else if (stage === 'cpp' && result.cpp !== undefined) { state.cpp = result.cpp; showCode(result.cpp, 'cpp', 'C++ gerado para o programa MiniPar.'); }
      else intro('A etapa parou no diagnóstico acima; etapas posteriores não foram executadas.');
    } catch (error) { if (ticket === state.request) { status('Falha de comunicação', 'error'); intro(error.message); } }
  }
  stageButtons.forEach(button => button.addEventListener('click', () => analyze(button.dataset.stage)));
  function showDownloads(extra=[]) {
    const box = $('downloads'); box.replaceChildren();
    const all = [['C++ gerado',state.downloads.cpp], ['TAC',state.downloads.tac],
      ['Executável nativo',state.downloads.executable], ...extra.map(a => [a.name,a.url])];
    for (const [label,url] of all) if (url) { const link = element('a', '', `↓ ${label}`); link.href = url; box.append(link); }
    if (!box.childNodes.length) box.append(element('span', 'panel-intro', 'Compile e execute para disponibilizar os arquivos desta execução.'));
    box.hidden = false;
  }
  $('downloads-button').addEventListener('click', () => { const box = $('downloads'); if (box.hidden) showDownloads(state.artifacts || []); else box.hidden = true; });
  async function compile() {
    const ticket = ++state.request; state.job = null; runButton.disabled = true;
    status('Gerando C++ e compilando com G++…', 'working');
    $('execution-console').open = true;
    $('console-status').textContent = 'Compilando'; $('console-output').textContent = 'Aguardando o compilador nativo…';
    try {
      const result = await post('/api/educacional/compile', {code:code()});
      if (ticket !== state.request) return;
      if (result.analysis) { phases(result.analysis.phases); errors(result.analysis.diagnostics); status('Compilação interrompida na análise', 'error'); $('console-output').textContent = result.error; return; }
      phases(result.phases); state.downloads = result.downloads || {}; state.job = result.success ? result.job_id : null;
      runButton.disabled = !result.success;
      const c = result.compilation;
      $('console-status').textContent = result.success ? `Compilado · ${result.filename}` : c.timed_out ? 'Timeout G++' : `Erro G++ · código ${c.returncode}`;
      $('console-output').textContent = [c.stdout,c.stderr].filter(Boolean).join('\n') || (result.success ? 'G++ concluiu sem avisos.' : 'G++ não produziu o binário.');
      status(result.success ? 'Compilação aprovada' : 'Compilação reprovada', result.success ? 'ok' : 'error');
      if (result.remote_forks) {
        const row = element('div','status-card',`${result.remote_forks} Fork remoto(s): inicie o binário compilado como trabalhador externo (--worker --port PORTA --workers N) nos endereços declarados no programa antes de executar.`);
        panel.prepend(row);
      }
      showDownloads();
    } catch (error) { if (ticket === state.request) { status('Falha ao compilar', 'error'); $('console-output').textContent = error.message; } }
  }
  $('compile-button').addEventListener('click', compile);
  runButton.addEventListener('click', async () => {
    if (!state.job) return;
    const ticket = ++state.request;
    $('execution-console').open = true;
    status('Executando binário real…', 'working'); $('console-status').textContent = 'Executando';
    try {
      const result = await post(`/api/educacional/jobs/${state.job}/run`, {stdin:$('stdin-editor').value});
      if (ticket !== state.request) return;
      const e = result.execution;
      $('console-status').textContent = e.timed_out ? 'Timeout após 30 s' : `Saída ${e.returncode}`;
      const binary = e.stdout.includes('TOKENS_BEGIN') && e.stdout.includes('ARM_BEGIN');
      $('console-output').textContent = (binary ? '--- Saída do minicompilador de expressões escrito em MiniPar ---\n' : '') +
        [e.stdout,e.stderr].filter(Boolean).join('\n') +
        (e.stdout_truncated || e.stderr_truncated ? '\n[Saída limitada a 64 KiB por fluxo.]' : '') || '(Sem saída textual.)';
      status(result.success ? 'Execução concluída' : 'Execução falhou', result.success ? 'ok' : 'error');
      state.artifacts = result.artifacts || []; showDownloads(state.artifacts);
    } catch (error) { if (ticket === state.request) { status('Falha ao executar', 'error'); $('console-status').textContent = 'Erro'; $('console-output').textContent = error.message; } }
  });
  $('clear-source').addEventListener('click', () => { state.sourceName = 'ide_temp.minipar'; setCode(''); $('example-select').value = ''; });
  async function loadExamples() {
    try {
      const response = await fetch('/api/educacional/examples'); const data = await response.json();
      const select = $('example-select');
      for (const group of ['Programas 1–11','Exemplos didáticos']) {
        const options = data.examples.filter(item => item.group === group);
        const section = element('optgroup'); section.label = group;
        for (const item of options) { const option = element('option', '', item.name); option.value = item.key; section.append(option); }
        select.append(section);
      }
      if ([...select.options].some(option => option.value === state.sourceName)) select.value = state.sourceName;
    } catch (error) { status('Exemplos indisponíveis', 'error'); }
  }
  $('example-select').addEventListener('change', async event => {
    const key = event.target.value; if (!key) return;
    const response = await fetch('/api/educacional/examples/' + encodeURIComponent(key));
    if (!response.ok) { status('Falha ao carregar exemplo', 'error'); return; }
    const result = await response.json(); state.sourceName = key; setCode(result.code);
    if (key.startsWith('teste11_')) $('stdin-editor').value = '((2+4)*7)-(5*4)\n';
    status(result.name + ' carregado', 'ok');
  });
  MiniParWorkspace.connect({read: () => ({code:code(), filename:state.sourceName}),
    write: draft => { state.sourceName = draft.filename; setCode(draft.code); }});
  loadExamples();
})();
