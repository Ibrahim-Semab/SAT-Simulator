/* Advanced review, per-question timing, and College Board Desmos link.
   Kept separate from the simulator core so the original test flow stays intact. */
(function () {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = seconds => {
    const n = Math.max(0, Math.round(Number(seconds) || 0));
    return n >= 60 ? Math.floor(n / 60) + 'm ' + String(n % 60).padStart(2, '0') + 's' : n + 's';
  };
  const originalDraw = draw;
  let activeQuestion = null;
  let activeSince = Date.now();

  function flushTime() {
    if (!T || !activeQuestion) return;
    T.timeSpentByQuestion = T.timeSpentByQuestion || {};
    const elapsed = Math.max(0, (Date.now() - activeSince) / 1000);
    T.timeSpentByQuestion[activeQuestion] = (T.timeSpentByQuestion[activeQuestion] || 0) + elapsed;
    activeSince = Date.now();
    if (T.phase !== 'results') save();
  }

  // A draw occurs after navigation and when leaving a module, so this records
  // elapsed time against the question actually being viewed (not answer clicks).
  draw = function () {
    const next = T && T.phase === 'exam' && T.plan && T.plan[T.mod]
      ? T.plan[T.mod][T.idx] : null;
    if (next !== activeQuestion) {
      flushTime();
      activeQuestion = next;
      activeSince = Date.now();
    }
    const result = originalDraw.apply(this, arguments);
    if (!next) activeQuestion = null;
    return result;
  };
  if (T && T.phase === 'exam' && T.plan && T.plan[T.mod]) { activeQuestion = T.plan[T.mod][T.idx] || null; activeSince = Date.now(); }
  addEventListener('beforeunload', flushTime);
  document.addEventListener('visibilitychange', () => {
    flushTime();
    activeSince = Date.now();
  });

  const oldHeader = headerHTML;
  headerHTML = function () {
    return oldHeader.apply(this, arguments).replace('Calculator</button>', 'Desmos</button>');
  };

  function openDesmos() {
    const url = 'https://www.desmos.com/testing/collegeboard/graphing';
    const w = floatWin('desmoswin', 'Desmos Graphing Calculator',
      '<div class="desmos-frame"><iframe title="College Board Desmos Graphing Calculator" src="' + url +
      '" allow="fullscreen"></iframe><p><a href="' + url +
      '" target="_blank" rel="noopener noreferrer">Open Desmos in a new tab</a></p></div>', 'desmos');
    if (w) {
      const frame = w.querySelector('iframe');
      if (frame) frame.addEventListener('error', () => {
        const p = w.querySelector('p');
        if (p) p.textContent = 'If the calculator does not load here, use the link below.';
      });
    }
  }
  A.calc = openDesmos;

  const modulesFor = subject => ORDER.filter(k => MODS[k].s === subject && T.plan[k]);
  function allRows() {
    return ORDER.filter(k => T.plan[k]).flatMap(k => (T.plan[k] || []).map((id, i) => {
      const q = BYID[id], answered = has(T.ans[id]), correct = isCorrect(q, T.ans[id]);
      return { k, i, id, q, answered, correct, status: correct ? 'correct' : answered ? 'incorrect' : 'missed',
        seconds: (T.timeSpentByQuestion && T.timeSpentByQuestion[id]) || 0 };
    }));
  }
  function filteredRows() {
    const rows = allRows();
    return (UI.advFilter || 'review') === 'all' ? rows : rows.filter(r => !r.correct);
  }
  const SIZES = [10, 20, 50];
  function pageList(cur, n) {
    const set = new Set([1, n, cur - 1, cur, cur + 1].filter(p => p >= 1 && p <= n));
    const out = []; let prev = 0;
    [...set].sort((a, b) => a - b).forEach(p => { if (p - prev > 1) out.push('…'); out.push(p); prev = p; });
    return out;
  }
  function pager(total, size, page) {
    const n = Math.max(1, Math.ceil(total / size));
    const btn = (label, p, on, off, aria) => '<button class="adv-page ' + (on ? 'on' : '') + '" ' + (off ? 'disabled ' : '') +
      'data-a="advPage" data-v="' + p + '"' + (aria ? ' aria-label="' + aria + '"' : '') + '>' + label + '</button>';
    return '<div class="adv-pager">' + btn('‹', page - 1, false, page <= 1, 'Previous page') +
      pageList(page, n).map(p => p === '…' ? '<span class="adv-gap">…</span>' : btn(p, p, p === page, false, 'Page ' + p)).join('') +
      btn('›', page + 1, false, page >= n, 'Next page') + '</div>';
  }
  function domainStats(rows) {
    const map = new Map();
    rows.forEach(r => {
      const key = r.q.d || 'Other';
      if (!map.has(key)) map.set(key, { name: key, total: 0, correct: 0 });
      const d = map.get(key);
      d.total++; d.correct += r.correct ? 1 : 0;
    });
    return [...map.values()].sort((a, b) => (a.correct / a.total) - (b.correct / b.total) || a.name.localeCompare(b.name));
  }
  const tone = p => p >= 75 ? 'good' : p >= 50 ? 'mid' : 'bad';
  const LEVEL = { E: 'Easy', M: 'Medium', H: 'Hard' };

  function ringSVG(value, min, max, label) {
    const r = 52, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, (value - min) / (max - min)));
    return '<div class="adv-ring"><svg viewBox="0 0 128 128" role="img" aria-label="' + label + '">' +
      '<circle cx="64" cy="64" r="' + r + '" fill="none" stroke="var(--bar)" stroke-width="12"/>' +
      '<circle cx="64" cy="64" r="' + r + '" fill="none" stroke="var(--accent)" stroke-width="12" stroke-linecap="round" ' +
      'stroke-dasharray="' + (c * f).toFixed(1) + ' ' + c.toFixed(1) + '" transform="rotate(-90 64 64)"/></svg>' +
      '<div class="adv-ring-v"><b>' + value + '</b><span>/ 1600</span></div></div>';
  }
  function rangeBar(est) {
    const left = Math.max(0, Math.min(100, (est - 200) / 6));
    return '<div class="adv-range"><i style="width:' + left + '%"></i><em style="left:' + left + '%"></em></div>' +
      '<div class="adv-range-ends"><span>200</span><span>800</span></div>';
  }
  function scoreRow(name, sec) {
    return '<div class="adv-score"><div class="adv-score-head"><span>' + name + '</span><b>' + sec.est +
      '</b></div>' + rangeBar(sec.est) + '</div>';
  }
  function moduleStrip(k) {
    const list = T.plan[k];
    if (!list) return '';
    const c = list.filter(id => isCorrect(BYID[id], T.ans[id])).length;
    const hard = k === 'rw2' ? T.route.rw : k === 'm2' ? T.route.math : null;
    const tag = hard ? '<small class="adv-tag">' + (hard === 'h' ? 'Harder' : 'Easier') + '</small>' : '';
    return '<div class="adv-mod"><div class="adv-mod-head"><span>Module ' + MODS[k].num + tag + '</span><b>' + c + '/' +
      list.length + '</b></div><div class="adv-strip">' + list.map((id, i) => {
        const ok = isCorrect(BYID[id], T.ans[id]);
        return '<button class="cell ' + (ok ? 'rg' : has(T.ans[id]) ? 'rb2' : 'ru') + '" data-a="qrev" data-k="' + k +
          '" data-i="' + i + '" aria-label="Review question ' + (i + 1) + '">' + (i + 1) + '</button>';
      }).join('') + '</div></div>';
  }
  function topicBars(rows) {
    return domainStats(rows).map(d => {
      const p = Math.round(100 * d.correct / d.total);
      return '<div class="adv-topic"><div class="adv-topic-head"><span>' + esc(d.name) + '</span><b>' + d.correct + '/' +
        d.total + '</b></div><div class="adv-track"><i class="' + tone(p) + '" style="width:' + p + '%"></i></div></div>';
    }).join('');
  }
  function sectionCard(subject, name, sec) {
    const rows = allRows().filter(r => MODS[r.k].s === subject);
    return '<section class="adv-card"><h2>' + name + '</h2>' + scoreRow('Score', sec) +
      '<div class="adv-sub">Modules</div>' + modulesFor(subject).map(moduleStrip).join('') +
      '<div class="adv-sub">Topics · weakest first</div>' + topicBars(rows) + '</section>';
  }
  function drawAdvancedResults(app) {
    const S = T.sum || summarize(T), rows = allRows(), shown = filteredRows();
    const right = rows.filter(r => r.correct).length, wrong = rows.length - right;
    const filter = UI.advFilter || 'review';
    const size = UI.advSize || 10, pages = Math.max(1, Math.ceil(shown.length / size));
    const page = Math.min(Math.max(1, UI.advPage || 1), pages); UI.advPage = page;
    const slice = shown.slice((page - 1) * size, page * size);
    app.innerHTML = '<div class="ribbon"></div><div class="center"><div class="res adv-res">' +
      '<h1>Practice Test ' + T.n + '</h1>' +
      '<section class="adv-hero">' + ringSVG(S.total, 400, 1600, 'Estimated total ' + S.total + ' out of 1600') +
      '<div class="adv-hero-main"><div class="adv-hero-l">Estimated score</div>' +
      '<div class="adv-hero-stats"><span><b class="g">' + right + '</b> correct</span><span><b class="r">' + wrong +
      '</b> to review</span></div><p class="adv-fine">Unofficial estimate</p></div></section>' +
      '<div class="adv-cols">' + sectionCard('rw', 'Reading &amp; Writing', S.rw) + sectionCard('math', 'Math', S.math) + '</div>' +
      '<section class="adv-card"><div class="adv-list-head"><h2>Review</h2><div class="adv-controls">' +
      '<button class="adv-filter ' + (filter === 'review' ? 'on' : '') + '" data-a="advFilter" data-v="review">To review (' + wrong + ')</button>' +
      '<button class="adv-filter ' + (filter === 'all' ? 'on' : '') + '" data-a="advFilter" data-v="all">All (' + rows.length + ')</button></div></div>' +
      (shown.length ? '<div class="adv-question-list">' + slice.map(r =>
        '<button class="adv-question" data-a="advOpen" data-k="' + r.k + '" data-i="' + r.i + '">' +
        '<span class="adv-dot ' + r.status + '"></span><span class="adv-qnum">' + (MODS[r.k].s === 'rw' ? 'R&amp;W ' : 'Math ') +
        MODS[r.k].num + '.' + (r.i + 1) + '</span><span class="adv-qmain">' + esc(r.q.d) + '</span><span class="adv-lvl ' +
        r.q.l + '" title="' + (LEVEL[r.q.l] || '') + '">' + (LEVEL[r.q.l] || '').charAt(0) + '</span><span class="adv-qtime">' +
        (r.seconds ? fmt(r.seconds) : '') + '</span></button>').join('') + '</div>' +
        '<div class="adv-foot"><div class="adv-size"><span>Show</span>' + SIZES.map(n =>
          '<button class="adv-filter ' + (n === size ? 'on' : '') + '" data-a="advSize" data-v="' + n + '">' + n + '</button>').join('') +
        '</div><span class="adv-range-txt">' + ((page - 1) * size + 1) + '–' + Math.min(page * size, shown.length) + ' of ' + shown.length +
        '</span>' + (pages > 1 ? pager(shown.length, size, page) : '') + '</div>' :
        '<p class="adv-empty">Nothing to review. Perfect score!</p>') + '</section>' +
      '<div class="resacts"><button class="btn" data-a="home">Done</button><button class="btn ghost" data-a="again">Start another test</button></div>' +
      '</div></div><div class="ribbon"></div>';
    layout();
  }

  drawResults = drawAdvancedResults;
  A.advFilter = b => { UI.advFilter = b.dataset.v; UI.advPage = 1; drawResults($('#app')); };
  A.advSize = b => { UI.advSize = Number(b.dataset.v); UI.advPage = 1; drawResults($('#app')); };
  A.advPage = b => { UI.advPage = Number(b.dataset.v); drawResults($('#app')); const l = $('.adv-question-list'); if (l) l.scrollIntoView({block:'start'}); };
    A.advOpen = b => {
    UI.view = { k:b.dataset.k, i:Number(b.dataset.i) };
    draw();
    scrollTo(0,0);
  };
  // Keep review state predictable when opening another test.
  const oldOpen = A.open;
  A.open = function (b) { UI.advFilter='review'; UI.advPage=1; return oldOpen(b); };
  const oldAgain = A.again;
  A.again = function (b) { UI.advFilter='review'; UI.advPage=1; return oldAgain(b); };
  const oldStart = A.start;
  A.start = function (b) { UI.advFilter='review'; UI.advPage=1; return oldStart(b); };

  const style = document.createElement('style');
  style.textContent = `
    .desmos{width:min(900px,calc(100vw - 24px));height:min(720px,calc(100vh - 110px));right:12px;top:70px;display:flex;flex-direction:column}
    .desmos-frame{display:flex;flex:1;min-height:0;flex-direction:column;padding:10px;gap:8px}
    .desmos-frame iframe{width:100%;flex:1;min-height:280px;border:1px solid var(--line);border-radius:8px}
    .desmos-frame p{margin:0;font-size:13px}.desmos-frame a{color:var(--accent-d);font-weight:700}
    .adv-res{max-width:980px}.adv-res h1{margin-bottom:16px}
    .adv-res h2{font-size:15px;margin:0 0 14px}
    .adv-hero{display:flex;align-items:center;gap:28px;border:1px solid var(--line);border-radius:16px;padding:22px 28px}
    .adv-ring{position:relative;width:150px;height:150px;flex:none}
    .adv-ring svg{width:100%;height:100%}
    .adv-ring-v{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
    .adv-ring-v b{font-size:38px;line-height:1;font-weight:800;font-variant-numeric:tabular-nums}
    .adv-ring-v span{font-size:12px;color:var(--ink2);margin-top:4px}
    .adv-hero-l{font-size:13px;font-weight:700;color:var(--ink2);text-transform:uppercase;letter-spacing:.6px}
    .adv-hero-stats{display:flex;gap:22px;margin-top:12px;font-size:14px;color:var(--ink2)}
    .adv-hero-stats b{font-size:30px;font-weight:800;margin-right:5px;font-variant-numeric:tabular-nums}
    .adv-hero-stats .g{color:var(--good)}.adv-hero-stats .r{color:var(--bad)}
    .adv-fine{margin:12px 0 0;font-size:11.5px;color:var(--ink2)}
    .adv-cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
    .adv-card{border:1px solid var(--line);border-radius:16px;padding:20px 22px}
    .adv-cols .adv-card{margin:0}
    .adv-res>.adv-card{margin:14px 0}
    .adv-score-head{display:flex;justify-content:space-between;align-items:baseline}
    .adv-score-head span{font-size:13px;color:var(--ink2);font-weight:600}
    .adv-score-head b{font-size:34px;font-weight:800;font-variant-numeric:tabular-nums}
    .adv-range{position:relative;height:8px;background:var(--bar);border-radius:8px;margin-top:6px}
    .adv-range i{position:absolute;left:0;top:0;bottom:0;background:var(--accent);border-radius:8px}
    .adv-range em{position:absolute;top:50%;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:var(--bg);border:3px solid var(--accent-d)}
    .adv-range-ends{display:flex;justify-content:space-between;font-size:11px;color:var(--ink2);margin-top:5px}
    .adv-sub{margin:22px 0 10px;font-size:11.5px;font-weight:700;color:var(--ink2);text-transform:uppercase;letter-spacing:.6px}
    .adv-mod{margin-bottom:14px}
    .adv-mod-head{display:flex;justify-content:space-between;font-size:13px;font-weight:600;margin-bottom:6px}
    .adv-tag{margin-left:8px;font-size:11px;font-weight:700;color:var(--accent-d);background:var(--accent-s);border-radius:10px;padding:1px 8px}
    .adv-strip{display:flex;flex-wrap:wrap;gap:5px}
    .adv-strip .cell{width:27px;height:27px;font-size:11px;border-radius:5px}
    .adv-strip .cell:hover{transform:translateY(-1px);box-shadow:0 2px 6px rgba(15,23,34,.25)}
    .adv-topic{margin-bottom:12px}
    .adv-topic-head{display:flex;justify-content:space-between;gap:10px;font-size:13px}
    .adv-topic-head b{font-variant-numeric:tabular-nums;color:var(--ink2)}
    .adv-track{height:8px;background:var(--bar);border-radius:8px;overflow:hidden;margin-top:5px}
    .adv-track i{display:block;height:100%;border-radius:8px;min-width:3px}
    .adv-track i.good{background:var(--good)}.adv-track i.mid{background:var(--r3)}.adv-track i.bad{background:var(--bad)}
    .adv-list-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
    .adv-list-head h2{margin:0}
    .adv-controls{display:flex;gap:6px}
    .adv-filter{border:1px solid var(--line);border-radius:18px;padding:6px 13px;font-size:12px;font-weight:700}
    .adv-filter.on{background:var(--accent-s);border-color:var(--accent);color:var(--accent-d)}
    .adv-question{width:100%;display:flex;align-items:center;gap:12px;text-align:left;padding:11px 6px;border-top:1px solid var(--line);font-size:13.5px}
    .adv-question:hover{background:var(--bar)}
    .adv-dot{flex:none;width:10px;height:10px;border-radius:50%}
    .adv-dot.correct{background:var(--good)}.adv-dot.incorrect{background:var(--bad)}.adv-dot.missed{background:none;border:2px dashed var(--ink2)}
    .adv-qnum{flex:none;min-width:62px;font-weight:700}
    .adv-qmain{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .adv-lvl{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:800;color:#fff}
    .adv-lvl.E{background:var(--good)}.adv-lvl.M{background:#b7791f}.adv-lvl.H{background:var(--bad)}
    .adv-qtime{flex:none;min-width:48px;text-align:right;font-size:12px;color:var(--ink2);font-variant-numeric:tabular-nums}
    .adv-foot{display:flex;align-items:center;gap:14px;flex-wrap:wrap;justify-content:space-between;border-top:1px solid var(--line);padding-top:14px;margin-top:4px}
    .adv-size{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--ink2)}.adv-size span{margin-right:2px}
    .adv-range-txt{font-size:12px;color:var(--ink2);font-variant-numeric:tabular-nums}
    .adv-pager{display:flex;gap:4px;align-items:center}
    .adv-page{min-width:32px;height:32px;padding:0 8px;border:1px solid var(--line);border-radius:8px;font-size:13px;font-weight:700}
    .adv-page:hover:not(:disabled):not(.on){background:var(--bar)}
    .adv-page.on{background:var(--accent);border-color:var(--accent);color:#fff}
    .adv-page:disabled{opacity:.35;cursor:default}.adv-gap{color:var(--ink2);padding:0 2px}
    .adv-empty{margin:18px 0 6px;font-size:14px;color:var(--ink2)}
    @media(max-width:760px){.adv-hero{flex-direction:column;align-items:flex-start;gap:16px;padding:18px}.adv-cols{grid-template-columns:1fr}.adv-card{padding:16px}}
  `;
  document.head.appendChild(style);
})();
