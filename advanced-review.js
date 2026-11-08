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

  const oldHome = drawHome;
  drawHome = function (app) {
    oldHome.apply(this, arguments);
    const sub = app.querySelector('.home .sub');
    if (sub && !app.querySelector('.cb-note')) {
      sub.insertAdjacentHTML('afterend',
        '<p class="cb-note">Practice material based on College Board content. Independent study tool; not an official College Board product.</p>');
    }
  };

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
    const filter = UI.advFilter || 'all', section = UI.advSection || 'all';
    return allRows().filter(r =>
      (filter === 'all' || r.status === filter) &&
      (section === 'all' || (section === 'rw' ? MODS[r.k].s === 'rw' : MODS[r.k].s === 'math')));
  }
  function domainStats(rows) {
    const map = new Map();
    rows.forEach(r => {
      const key = r.q.d || 'Uncategorized';
      if (!map.has(key)) map.set(key, {name:key,total:0,correct:0,seconds:0,levels:{E:{n:0,c:0},M:{n:0,c:0},H:{n:0,c:0}}});
      const d = map.get(key), level = d.levels[r.q.l] || d.levels.M;
      d.total++; d.correct += r.correct ? 1 : 0; d.seconds += r.seconds;
      level.n++; level.c += r.correct ? 1 : 0;
    });
    return [...map.values()].sort((a,b) => a.name.localeCompare(b.name));
  }
  function pct(n,d) { return d ? Math.round(100*n/d) + '%' : '—'; }
  function levelReached(d) {
    return ['H','M','E'].find(l => d.levels[l].c > 0) || '—';
  }
  function drawAdvancedResults(app) {
    const S = T.sum || summarize(T), rows = allRows(), shown = filteredRows();
    const totalTime = rows.reduce((n,r) => n+r.seconds, 0);
    const timed = rows.filter(r => r.seconds > 0);
    const slowest = [...domainStats(rows)].sort((a,b) =>
      (b.total ? b.seconds/b.total : 0) - (a.total ? a.seconds/a.total : 0)).slice(0,4);
    const filters = [['all','All'],['missed','Missed'],['incorrect','Incorrect']];
    const sections = [['all','All sections'],['rw','Reading & Writing'],['math','Math']];
    const domainPanel = subject => {
      const list = rows.filter(r => MODS[r.k].s === subject);
      const stats = domainStats(list);
      return '<section class="adv-panel"><h2>' + (subject === 'rw' ? 'Reading &amp; Writing' : 'Math') +
        ' · Domain insights</h2>' + (stats.length ? stats.map(d =>
        '<div class="adv-domain"><div class="adv-domain-head"><b>' + esc(d.name) + '</b><strong>' +
        pct(d.correct,d.total) + '</strong></div><div class="adv-track"><i style="width:' +
        (d.total ? 100*d.correct/d.total : 0) + '%"></i></div><div class="adv-meta">' +
        d.correct + '/' + d.total + ' correct · Avg. ' + fmt(d.total ? d.seconds/d.total : 0) +
        ' · Highest difficulty answered correctly: <b>' + ({E:'Easy',M:'Medium',H:'Hard'}[levelReached(d)] || 'Not yet reached') +
        '</b></div><div class="adv-levels">' + ['E','M','H'].map(l =>
          '<span>' + ({E:'Easy',M:'Medium',H:'Hard'}[l]) + ': ' +
          pct(d.levels[l].c,d.levels[l].n) + '</span>').join('') + '</div></div>').join('') :
        '<p class="adv-muted">No questions in this section.</p>') + '</section>';
    };
    const modulePanel = k => {
      const list = rows.filter(r => r.k === k);
      if (!list.length) return '';
      const c = list.filter(r => r.correct).length;
      return '<div class="adv-module"><b>' + esc(modTitle(k)) + '</b><span>' + c + '/' + list.length +
        ' correct · ' + fmt(list.reduce((n,r)=>n+r.seconds,0)) + ' spent</span></div>';
    };
    app.innerHTML = '<div class="ribbon"></div><div class="center"><div class="res adv-res">' +
      '<h1>Practice Test ' + T.n + ' · Advanced Review</h1>' +
      '<div class="scores"><div class="sbox tot"><div class="l">Estimated total</div><div class="v">' + S.total +
      '</div><div class="d">out of 1600 · unofficial estimate</div></div>' +
      '<div class="sbox"><div class="l">Reading and Writing</div><div class="v">' + S.rw.est +
      '</div><div class="d">' + S.rw.correct + ' / ' + S.rw.total + ' correct</div></div>' +
      '<div class="sbox"><div class="l">Math</div><div class="v">' + S.math.est +
      '</div><div class="d">' + S.math.correct + ' / ' + S.math.total + ' correct</div></div></div>' +
      '<div class="adv-kpis"><div><b>' + rows.filter(r=>r.correct).length + '/' + rows.length +
      '</b><span>Accuracy</span></div><div><b>' + fmt(totalTime) + '</b><span>Tracked question time</span></div>' +
      '<div><b>' + (timed.length ? fmt(totalTime/timed.length) : '—') +
      '</b><span>Average per question</span></div><div><b>' + rows.filter(r=>r.status==='missed').length +
      '</b><span>Unanswered</span></div></div>' +
      '<p class="note">Question time is tracked while a question is open in the simulator. Time from before this feature was enabled is not available. Score estimates are not official College Board scores.</p>' +
      '<section class="adv-panel"><h2>Module breakdown</h2>' + ORDER.map(modulePanel).join('') + '</section>' +
      domainPanel('rw') + domainPanel('math') +
      '<section class="adv-panel"><h2>Where time is going</h2>' +
      (slowest.length ? '<p class="adv-muted">Domains with the highest average time per question:</p>' +
        slowest.map(d=>'<div class="adv-time-row"><span>' + esc(d.name) + '</span><b>' +
          fmt(d.total ? d.seconds/d.total : 0) + ' avg.</b><small>' + fmt(d.seconds) + ' total</small></div>').join('') :
        '<p class="adv-muted">Time insights will appear as you complete questions.</p>') + '</section>' +
      '<section class="adv-panel"><div class="adv-list-head"><div><h2>Question review</h2><p class="adv-muted">' +
      shown.length + ' of ' + rows.length + ' questions</p></div></div>' +
      '<div class="adv-controls"><div>' + filters.map(([v,l]) =>
        '<button class="adv-filter ' + ((UI.advFilter||'all')===v?'on':'') + '" data-a="advFilter" data-v="' + v + '">' + l +
        (v==='missed'?' ('+rows.filter(r=>r.status==='missed').length+')':v==='incorrect'?' ('+rows.filter(r=>r.status==='incorrect').length+')':'') +
        '</button>').join('') + '</div><div>' + sections.map(([v,l]) =>
        '<button class="adv-filter ' + ((UI.advSection||'all')===v?'on':'') + '" data-a="advSection" data-v="' + v + '">' + l +
        '</button>').join('') + '</div></div>' +
      (shown.length ? '<div class="adv-question-list">' + shown.map(r =>
        '<button class="adv-question" data-a="advOpen" data-k="' + r.k + '" data-i="' + r.i + '">' +
        '<span class="adv-qnum">Q' + (r.i+1) + '</span><span class="adv-qmain"><b>' + esc(r.q.d) +
        '</b><small>' + esc(modTitle(r.k)) + ' · ' + esc(r.q.k) + ' · ' +
        ({E:'Easy',M:'Medium',H:'Hard'}[r.q.l] || '') + '</small></span><span class="adv-qstatus ' + r.status + '">' +
        ({correct:'Correct',incorrect:'Incorrect',missed:'Missed'}[r.status]) + '</span><span class="adv-qtime">' +
        fmt(r.seconds) + '</span><span class="adv-open">Review →</span></button>').join('') +
      '</div>' : '<p class="adv-muted">No questions match these filters.</p>') + '</section>' +
      '<div class="resacts"><button class="btn" data-a="home">Done</button><button class="btn ghost" data-a="again">Start another test</button></div>' +
      '</div></div><div class="ribbon"></div>';
    layout();
  }

  drawResults = drawAdvancedResults;
  A.advFilter = b => { UI.advFilter = b.dataset.v; drawResults($('#app')); };
  A.advSection = b => { UI.advSection = b.dataset.v; drawResults($('#app')); };
  A.advOpen = b => {
    UI.view = { k:b.dataset.k, i:Number(b.dataset.i) };
    draw();
    scrollTo(0,0);
  };
  // Keep review state predictable when opening another test.
  const oldOpen = A.open;
  A.open = function (b) { UI.advFilter='all'; UI.advSection='all'; return oldOpen(b); };
  const oldAgain = A.again;
  A.again = function (b) { UI.advFilter='all'; UI.advSection='all'; return oldAgain(b); };
  const oldStart = A.start;
  A.start = function (b) { UI.advFilter='all'; UI.advSection='all'; return oldStart(b); };

  const style = document.createElement('style');
  style.textContent = `
    .cb-note{margin:10px 0 0;padding:9px 12px;border-left:3px solid var(--accent);background:var(--accent-s);color:var(--ink2);font-size:12px;line-height:1.45}
    .desmos{width:min(900px,calc(100vw - 24px));height:min(720px,calc(100vh - 110px));right:12px;top:70px;display:flex;flex-direction:column}
    .desmos-frame{display:flex;flex:1;min-height:0;flex-direction:column;padding:10px;gap:8px}
    .desmos-frame iframe{width:100%;flex:1;min-height:280px;border:1px solid var(--line);border-radius:8px}
    .desmos-frame p{margin:0;font-size:13px}.desmos-frame a{color:var(--accent-d);font-weight:700}
    .adv-res{max-width:1000px}.adv-res h2{font-size:17px;margin:0 0 14px}
    .adv-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}
    .adv-kpis>div{border:1px solid var(--line);border-radius:10px;padding:12px 14px}
    .adv-kpis b{display:block;font-size:23px;font-variant-numeric:tabular-nums}
    .adv-kpis span,.adv-muted{font-size:12.5px;color:var(--ink2)}
    .adv-panel{border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
    .adv-module,.adv-time-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);font-size:13px}
    .adv-module:last-child,.adv-time-row:last-child{border-bottom:0}
    .adv-module span{margin-left:auto;color:var(--ink2)}
    .adv-domain{padding:12px 0;border-bottom:1px solid var(--line)}
    .adv-domain:last-child{border-bottom:0}
    .adv-domain-head{display:flex;justify-content:space-between;gap:12px;font-size:14px}
    .adv-track{height:7px;background:var(--bar);border-radius:10px;overflow:hidden;margin:8px 0}
    .adv-track i{display:block;height:100%;background:var(--accent);border-radius:10px}
    .adv-meta{font-size:12px;color:var(--ink2)}
    .adv-levels{display:flex;gap:14px;flex-wrap:wrap;margin-top:6px;font-size:12px;color:var(--ink2)}
    .adv-time-row span{flex:1}.adv-time-row small{color:var(--ink2)}
    .adv-controls{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:10px 0 14px}
    .adv-controls>div{display:flex;gap:6px;flex-wrap:wrap}
    .adv-filter{border:1px solid var(--line);border-radius:18px;padding:7px 12px;font-size:12px;font-weight:700}
    .adv-filter.on{background:var(--accent-s);border-color:var(--accent);color:var(--accent-d)}
    .adv-question{width:100%;display:flex;align-items:center;gap:12px;text-align:left;padding:12px 4px;border-top:1px solid var(--line)}
    .adv-qnum{font-weight:800;min-width:34px}.adv-qmain{min-width:0;flex:1}
    .adv-qmain b,.adv-qmain small{display:block}.adv-qmain small{color:var(--ink2);font-size:11px;margin-top:3px}
    .adv-qstatus{font-size:11px;font-weight:800;min-width:72px}
    .adv-qstatus.correct{color:var(--good)}.adv-qstatus.incorrect{color:var(--bad)}.adv-qstatus.missed{color:var(--flag)}
    .adv-qtime{font-size:12px;color:var(--ink2);min-width:48px;text-align:right}
    .adv-open{font-size:12px;color:var(--accent-d);font-weight:700}
    @media(max-width:760px){.adv-kpis{grid-template-columns:repeat(2,1fr)}.adv-panel{padding:14px}.adv-question{gap:7px}.adv-qstatus{min-width:0}.adv-open{display:none}.adv-time-row{flex-wrap:wrap}}
  `;
  document.head.appendChild(style);
})();