/* Passagem unica do fonte na mesma aba; nenhum resultado ou binario e compartilhado. */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.MiniParWorkspace = factory();
}(globalThis, function () {
    'use strict';
    const KEY = 'minipar.web.source.v1';
    const MODES = ['/', '/educacional'];
    function filename(value) {
        return typeof value === 'string' && value.length <= 120 && value.endsWith('.minipar') &&
            !value.startsWith('.') && !/[\\/:\x00-\x1f]/.test(value) ? value : 'ide_temp.minipar';
    }
    function connect(adapter, env = window) {
        let restored = false;
        try {
            const raw = env.sessionStorage.getItem(KEY);
            env.sessionStorage.removeItem(KEY);
            const draft = raw ? JSON.parse(raw) : null;
            if (draft && draft.destination === env.location.pathname &&
                typeof draft.code === 'string' && draft.code.length <= 300000) {
                adapter.write({code: draft.code, filename: filename(draft.filename)});
                restored = true;
            }
        } catch (_) { /* Armazenamento bloqueado nao impede usar os dois ambientes. */ }
        env.document.querySelectorAll('.web-mode-link').forEach(link => {
            link.addEventListener('click', event => {
                const destination = link.getAttribute('href');
                if (event.defaultPrevented || event.button > 0 || event.ctrlKey || event.metaKey ||
                    event.shiftKey || event.altKey || destination === env.location.pathname || !MODES.includes(destination)) return;
                try {
                    const draft = adapter.read();
                    env.sessionStorage.removeItem(KEY);
                    if (typeof draft.code === 'string' && draft.code.length <= 300000)
                        env.sessionStorage.setItem(KEY, JSON.stringify({code: draft.code,
                            filename: filename(draft.filename), destination}));
                } catch (_) { /* A navegacao por link continua funcionando sem storage. */ }
            });
        });
        return restored;
    }
    return {connect};
}));
