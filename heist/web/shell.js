/* shell.js — shared module loaded by /hiring, /job, /heist, /epilogue
 *
 * Exposes:
 *   window.Shell           — shared state + helpers (read by tab fragments)
 *   window.initShell(opts) — boot entry point called by each page
 *   window.loadTabFragment — fetch + exec a /tabs/<name> fragment
 *   window.replayStep / replayToggle / replayReset — replay controls (used in onclick)
 *   window._selectAIFromUI  — AI picker onclick target
 */
'use strict';

// ── constants ─────────────────────────────────────────────────────────────────
const SKILL_API_TO_SHORT = {
  hacker: 'hack', safecracker: 'safe', muscle: 'musc',
  inside_man: 'soc', driver: 'drive',
};
const SKILL_SHORT_TO_API = Object.fromEntries(
  Object.entries(SKILL_API_TO_SHORT).map(([k, v]) => [v, k])
);
const SKILL_KEYS  = ['hack','safe','musc','soc','drive'];
const SKILL_LABEL = { hack:'HACK', safe:'SAFE', musc:'MUSC', soc:'SOC', drive:'DRIVE' };
const SKILL_VALUE = { HIGH:3, MEDIUM:2, LOW:1, NONE:0 };
const PORTRAIT_STYLE = { hack:'pixel-art', safe:'notionists', musc:'bottts', soc:'personas', drive:'adventurer' };
const PORTRAIT_BG    = { hack:'1a2840', safe:'2a2008', musc:'2a0c0c', soc:'1e1430', drive:'0c2018' };

// ── Shell object ──────────────────────────────────────────────────────────────
const Shell = {
  roster: [],
  charById: new Map(),
  aiList: [{ idx: 0, label: 'AI', color: 'var(--ai-a)' }],
  currentAI: 0,
  replayEvents: [],  // set by initShell after loading replay buffer

  helpers: {
    escapeHtml(s) {
      return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    },
    renderMd(text) {
      if (!text) return '';
      let s = String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      s = s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
           .replace(/\*(.+?)\*/g,'<em>$1</em>')
           .replace(/`(.+?)`/g,'<code>$1</code>');
      return s.split(/\n{2,}/).map(p=>`<p>${p.replace(/\n/g,'<br>')}</p>`).join('');
    },
    skillVal(c, short) {
      const apiKey = SKILL_SHORT_TO_API[short];
      const levelStr = c.skills?.[apiKey];
      return SKILL_VALUE[levelStr] || 0;
    },
    primarySkill(c) {
      let bestKey = 'hack', bestVal = -1;
      Object.entries(c.skills || {}).forEach(([apiKey, levelStr]) => {
        const short = SKILL_API_TO_SHORT[apiKey];
        if (!short) return;
        const val = SKILL_VALUE[levelStr] || 0;
        if (val > bestVal) { bestVal = val; bestKey = short; }
      });
      return bestKey;
    },
    portraitUrl(c) {
      const p = Shell.helpers.primarySkill(c);
      const seed = (c.name || '').toLowerCase().replace(/\s+/g, '');
      return `https://api.dicebear.com/9.x/${PORTRAIT_STYLE[p]}/svg?seed=${encodeURIComponent(seed)}&backgroundColor=${PORTRAIT_BG[p]}`;
    },
    charCardHtml(c, opts) {
      const { hideCost = false, noId = false } = opts || {};
      const esc = Shell.helpers.escapeHtml;
      const primary = Shell.helpers.primarySkill(c);
      const initials = (c.name || '?').slice(0,1).toUpperCase();
      const skillsHtml = SKILL_KEYS.map(sk => {
        const val = Shell.helpers.skillVal(c, sk);
        const segs = Array.from({length:3}, (_, j) =>
          `<span class="seg ${j < val ? 'f-' + sk : ''}"></span>`).join('');
        return `<div class="cc-skill"><span class="cc-skill-label">${SKILL_LABEL[sk]}</span><div class="cc-skill-bars">${segs}</div></div>`;
      }).join('');
      const idAttr = noId ? '' : ` id="cc-${c.id}"`;
      const costRow = hideCost ? '' :
        `<div class="cc-cost-row">$${Number(c.floor_cost).toLocaleString()}</div>`;
      return `<div class="char-card" data-primary="${primary}"${idAttr}>
        <div class="cc-portrait">
          <div class="cc-portrait-fallback">${esc(initials)}</div>
          <img src="${Shell.helpers.portraitUrl(c)}" alt="${esc(c.name)}" loading="lazy" onerror="this.style.display='none'">
        </div>
        <div class="cc-header"><span class="cc-name" title="${esc(c.name)}">${esc(c.name)}</span></div>
        <div class="cc-info"><div class="cc-skills">${skillsHtml}</div></div>
        ${costRow}
      </div>`;
    },
    buildDiffBar(level) {
      const segs = {HARD:3, MEDIUM:2, LOW:1, NONE:0}[level] || 0;
      const cls  = {HARD:'lvl-hard', MEDIUM:'lvl-medium', LOW:'lvl-low'}[level] || '';
      return '<div class="ct-bar-segs">' + Array.from({length:3}, (_,i) =>
        `<span class="ct-seg ${i<segs?cls:''}"></span>`).join('') + '</div>';
    },
    diffCls(level) {
      return {HARD:'ct-level-hard', MEDIUM:'ct-level-medium', LOW:'ct-level-low'}[level] || 'ct-level-none';
    },
  },

  // shell helpers for tabs
  setJobDisplay(name) {
    const el = document.getElementById('job-display');
    if (el) el.textContent = name || '—';
  },
  setHeat(n)          { _updateHeat(n); },
  setStatus(cls, txt) { _setStatus(cls, txt); },
  unlockTab()         { /* no-op in multi-page architecture */ },
  addThought(aiIdx, kind, title, bodyHtml, opts) { _addThought(aiIdx, kind, title, bodyHtml, opts); },
  markHired(aiIdx, charId) { _markHired(aiIdx, charId); },
  onAISelected(cb) { _aiSubscribers.push(cb); },
};
window.Shell = Shell;

// ── shell-private state ───────────────────────────────────────────────────────
let _evtSource = null;
const _aiStreams = [[]];           // per-AI thought arrays (newest first)
const _hiredMarks = {};            // ai_idx -> Set<char_id>
const _aiSubscribers = [];         // callbacks registered via Shell.onAISelected

let _REPLAY_EVENTS = [];
let _REPLAY_INDEX  = 0;
let _REPLAY_TIMER  = null;

const _THOUGHT_CARD_DELAY_MS = (() => {
  const p = new URLSearchParams(window.location.search);
  const n = parseInt(p.get('cardDelay') || '', 10);
  return Number.isFinite(n) ? n : 5000;
})();
const _thoughtQueue = [];
let   _thoughtTimer  = null;

let _currentOnEvent = null;  // set by initShell; used by replayStep

// ── isVisibleEvent: true for events that produce a visible DOM change ─────────
function _isVisibleEvent(e) {
  if (e.type === 'turn_start') return false;
  if (e.type === 'turn_end') {
    const label = e.label || '';
    if (label === 'bid')             return true;
    if (label === 'job_pick')        return true;
    if (label === 'casting_summary') return true;
    if (/^scene_\d+_(?:escape_)?narrate$/.test(label)) return true;
    return false;
  }
  return true;
}

// ── replay controls ───────────────────────────────────────────────────────────
function replayStep() {
  if (_REPLAY_INDEX >= _REPLAY_EVENTS.length) return;
  while (_REPLAY_INDEX < _REPLAY_EVENTS.length) {
    const evt = _REPLAY_EVENTS[_REPLAY_INDEX++];
    _processEvent(evt, _currentOnEvent);
    if (_isVisibleEvent(evt)) break;
  }
  _replayUpdateCounter();
  if (_REPLAY_INDEX >= _REPLAY_EVENTS.length && _REPLAY_TIMER) replayToggle();
}

function replayToggle() {
  const btn = document.getElementById('replay-play');
  if (_REPLAY_TIMER) {
    clearInterval(_REPLAY_TIMER); _REPLAY_TIMER = null;
    if (btn) btn.textContent = '▶ Play';
  } else {
    _REPLAY_TIMER = setInterval(replayStep, Math.max(_THOUGHT_CARD_DELAY_MS, 500));
    if (btn) btn.textContent = '⏸ Pause';
  }
}

function replayReset() {
  if (_REPLAY_TIMER) replayToggle();
  _REPLAY_INDEX = 0;
  _thoughtQueue.length = 0;
  if (_thoughtTimer) { clearTimeout(_thoughtTimer); _thoughtTimer = null; }
  for (const k of Object.keys(_hiredMarks)) delete _hiredMarks[k];
  _aiStreams.forEach((_, i) => _aiStreams[i] = []);
  _selectAI(Shell.currentAI);
  _replayUpdateCounter();
  // Signal reset to the current page so it can reset its tab module
  if (_currentOnEvent) {
    try { _currentOnEvent({ type: '_reset' }); } catch {}
  }
}

function _replayUpdateCounter() {
  const el = document.getElementById('replay-counter');
  if (!el) return;
  const seen  = _REPLAY_EVENTS.slice(0, _REPLAY_INDEX).filter(_isVisibleEvent).length;
  const total = _REPLAY_EVENTS.filter(_isVisibleEvent).length;
  el.textContent = `${seen} / ${total}`;
}

// Expose for HTML onclick attributes
window.replayStep   = replayStep;
window.replayToggle = replayToggle;
window.replayReset  = replayReset;

// ── fragment loader ───────────────────────────────────────────────────────────
async function loadTabFragment(name) {
  const html = await fetch('/tabs/' + name).then(r => {
    if (!r.ok) throw new Error(`fetch /tabs/${name}: ${r.status}`);
    return r.text();
  });
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  wrap.querySelectorAll('style, template').forEach(el => document.body.appendChild(el));
  wrap.querySelectorAll('script').forEach(oldScript => {
    const fresh = document.createElement('script');
    if (oldScript.src) fresh.src = oldScript.src;
    else fresh.textContent = oldScript.textContent;
    document.body.appendChild(fresh);
  });
}
window.loadTabFragment = loadTabFragment;

// ── initShell ─────────────────────────────────────────────────────────────────
//
// Called by each page's inline script after mounting its tab fragment.
//
//   gameId   — from ?game=ID; null falls back to most-recent game
//   onEvent  — called for every SSE or replay event (including { type:'_reset' })
//
window.initShell = async function({ gameId, onEvent } = {}) {
  _currentOnEvent = onEvent || null;

  // 1. Load roster so tab fragments can render character data
  try {
    const meta = await fetch('/api/meta').then(r => r.json());
    Shell.roster = meta.roster || [];
    Shell.roster.forEach(c => Shell.charById.set(c.id, c));
  } catch (e) {
    console.error('shell: failed to load meta', e);
  }

  // 2. Find this game in the games list → populate aiList
  let targetGame = null;
  const gid = gameId != null
    ? (typeof gameId === 'string' ? parseInt(gameId, 10) : gameId)
    : null;
  try {
    const games = await fetch('/api/games').then(r => r.json());
    if (gid != null) targetGame = games.find(g => g.id === gid);
    if (!targetGame) {
      targetGame = [...games].reverse().find(g => g.status === 'running')
        || [...games].reverse().find(g => g.status === 'done')
        || [...games].reverse()[0];
    }
    if (targetGame && targetGame.ais && targetGame.ais.length) {
      Shell.aiList = targetGame.ais.map((ai, i) => ({
        idx: i,
        label: ai.agent || ('AI ' + (i+1)),
        color: ['var(--ai-a)','var(--ai-b)','var(--ai-c)'][i] || 'var(--ai-a)',
      }));
      while (_aiStreams.length < Shell.aiList.length) _aiStreams.push([]);
    }
  } catch {}

  _renderAIPicker();
  _selectAI(0);

  // 3. Connect to events
  const isReplay = targetGame && targetGame.status === 'done';
  if (isReplay) {
    _setStatus('s-idle', 'REPLAY');
    const rcEl = document.getElementById('replay-controls');
    if (rcEl) rcEl.style.display = '';
    try {
      const effectiveGid = targetGame.id;
      const data = await fetch(`/api/games/${effectiveGid}/events`).then(r => r.json());
      _REPLAY_EVENTS = data.events || [];
      Shell.replayEvents = _REPLAY_EVENTS;
      _replayUpdateCounter();
    } catch (e) {
      _addThought(0, 'scene', 'Replay load error', Shell.helpers.escapeHtml(String(e)));
    }
  } else {
    _evtSource = new EventSource('/stream');
    _evtSource.onmessage = (raw) => {
      let e;
      try { e = JSON.parse(raw.data); } catch { return; }
      _processEvent(e, _currentOnEvent);
    };
    _evtSource.onerror = () => {
      if (_evtSource && _evtSource.readyState === EventSource.CLOSED) _setStatus('s-idle', 'IDLE');
    };
  }
};

// ── event processor ───────────────────────────────────────────────────────────
function _processEvent(e, onEvent) {
  // Rail-level handling (thought cards, bid cards, etc.)
  if (e.type === 'turn_end') _railFromTurnEnd(e);

  const aiIdx = e.ai_idx ?? 0;

  // Top bar updates
  if (e.type === 'job_known' && aiIdx === Shell.currentAI) {
    const el = document.getElementById('job-display');
    if (el) el.textContent = e.job.name;
  } else if (e.type === 'scene_done' && aiIdx === Shell.currentAI) {
    _updateHeat(e.heat);
  } else if (e.type === 'game_done') {
    if (aiIdx === Shell.currentAI) {
      const jd = document.getElementById('job-display');
      if (jd) jd.textContent = e.state.job.name;
      _updateHeat(e.state.heat);
    }
    _maybeFinishStream(e);
  } else if (e.type === 'error') {
    _addThought(aiIdx, 'scene', 'Error', Shell.helpers.escapeHtml(e.message || 'unknown error'));
    _setStatus('s-error', 'ERROR');
  } else if (e.type === 'crew_known') {
    _markCrewHired(aiIdx, e.crew);
  }

  // Fan to the page's onEvent callback
  if (onEvent) {
    try { onEvent(e); } catch (err) { console.error('shell: onEvent error:', err); }
  }
}

function _railFromTurnEnd(e) {
  const aiIdx = e.ai_idx ?? 0;
  const esc = Shell.helpers.escapeHtml;
  if (e.label === 'bid' && e.parsed) {
    if (e.parsed.casting_strategy) {
      _addThought(aiIdx, 'strategy', 'Strategy', esc(e.parsed.casting_strategy));
    }
    (e.parsed.bids || []).forEach(b => {
      _flashCard(b.character_id);
      const c = Shell.charById.get(b.character_id);
      if (!c) return;
      const amount = b.bid != null ? ' · $' + Number(b.bid).toLocaleString() : '';
      _addThought(aiIdx, 'bid', 'Bid · ' + c.name + amount, esc(b.rationale || '—'),
        { id: 'bid-' + aiIdx + '-' + b.character_id, charId: b.character_id });
    });
  } else if (e.label === 'casting_summary' && e.parsed && e.parsed.summary) {
    const s = e.parsed.summary;
    _addThought(aiIdx, 'strategy', 'Casting summary',
      esc(s.length > 240 ? s.slice(0,240) + '…' : s));
  } else if (e.label === 'job_pick' && e.parsed) {
    const whyThis = e.parsed.why_this || '';
    const whyNot  = e.parsed.why_not  || '';
    const legacy  = e.parsed.reasoning || '';
    let body;
    if (whyThis || whyNot) {
      body = '';
      if (whyThis) body += `<div class="thought-sub-head">Why this job</div>${esc(whyThis)}`;
      if (whyNot)  body += `<div class="thought-sub-head">Why not the others</div>${esc(whyNot)}`;
    } else {
      body = esc(legacy || '—');
    }
    _addThought(aiIdx, 'job', 'Job pick', body);
  }
}

function _markCrewHired(aiIdx, crew) {
  if (!crew || !crew.members) return;
  crew.members.forEach(member => _markHired(aiIdx, member.id));
}

function _maybeFinishStream(latestGameDone) {
  _maybeFinishStream._seenDone = _maybeFinishStream._seenDone || new Set();
  _maybeFinishStream._seenDone.add(latestGameDone.ai_idx ?? 0);
  if (_maybeFinishStream._seenDone.size < Shell.aiList.length) return;
  if (_evtSource) { _evtSource.close(); _evtSource = null; }
  if (latestGameDone && latestGameDone.state) {
    const s = latestGameDone.state;
    const ok = !s.aborted && s.escape_success !== false;
    _setStatus(ok ? 's-done' : 's-error',
      ok && s.final_take != null
        ? '$' + (s.final_take / 1e6).toFixed(2) + 'M'
        : 'FAILED');
  }
}

// ── AI picker + thinking stream ───────────────────────────────────────────────
function _renderAIPicker() {
  const esc = Shell.helpers.escapeHtml;
  const el = document.getElementById('ai-pills');
  if (!el) return;
  el.innerHTML = Shell.aiList.map(ai =>
    `<button class="ai-pill ${ai.idx === Shell.currentAI ? 'ap-active' : ''}" data-aiidx="${ai.idx}" onclick="_selectAIFromUI(${ai.idx})">
      <span class="ap-dot"></span>${esc(ai.label)}
    </button>`
  ).join('');
}
window._selectAIFromUI = (idx) => _selectAI(idx);

function _selectAI(idx) {
  Shell.currentAI = idx;
  document.querySelectorAll('.ai-pill').forEach(p =>
    p.classList.toggle('ap-active', parseInt(p.dataset.aiidx) === idx));
  const ai = Shell.aiList[idx] || Shell.aiList[0];
  const av = document.getElementById('thinking-avatar');
  if (av) { av.textContent = ['A','B','C'][idx] || '·'; av.style.background = ai.color; }
  const tt = document.getElementById('thinking-title');
  if (tt) tt.textContent = ai.label;
  _renderThinking();
  _aiSubscribers.forEach(cb => { try { cb(idx); } catch (e) { console.error('AI subscriber error:', e); } });
}

function _addThought(aiIdx, kind, title, bodyHtml, opts) {
  const t = { aiIdx, kind, title, body: bodyHtml, ...(opts || {}) };
  while (_aiStreams.length <= aiIdx) _aiStreams.push([]);
  _aiStreams[aiIdx].unshift(t);
  if (_THOUGHT_CARD_DELAY_MS <= 0) {
    if (aiIdx === Shell.currentAI) _prependThought(t);
    return;
  }
  _thoughtQueue.push(t);
  if (!_thoughtTimer) _thoughtTimer = setTimeout(_drainOneThought, _THOUGHT_CARD_DELAY_MS);
}

function _drainOneThought() {
  const t = _thoughtQueue.shift();
  if (!t) { _thoughtTimer = null; return; }
  if (t.aiIdx === Shell.currentAI) _prependThought(t);
  if (_thoughtQueue.length > 0) {
    _thoughtTimer = setTimeout(_drainOneThought, _THOUGHT_CARD_DELAY_MS);
  } else {
    _thoughtTimer = null;
  }
}

function _prependThought(t) {
  const stream = document.getElementById('thinking-stream');
  if (!stream) return;
  stream.querySelector('.thinking-empty')?.remove();
  if (t.id) { const ex = document.getElementById('thought-' + t.id); if (ex) ex.remove(); }
  const line = document.createElement('div');
  line.className = `thought-line tk-${t.kind}`;
  if (t.id) line.id = 'thought-' + t.id;
  const showHired = t.kind === 'bid' && t.charId != null
    && _hiredMarks[t.aiIdx] && _hiredMarks[t.aiIdx].has(t.charId);
  line.innerHTML =
    `<div class="thought-kind">${Shell.helpers.escapeHtml(t.title)}</div>` +
    `<div class="thought-body">${t.body}</div>` +
    (showHired ? '<div class="thought-hired-badge">✓ Hired</div>' : '');
  stream.insertBefore(line, stream.firstChild);
  stream.scrollTop = 0;
}

function _markHired(aiIdx, charId) {
  if (!_hiredMarks[aiIdx]) _hiredMarks[aiIdx] = new Set();
  if (_hiredMarks[aiIdx].has(charId)) return;
  _hiredMarks[aiIdx].add(charId);
  const arr = _aiStreams[aiIdx] || [];
  for (const t of arr) { if (t.kind === 'bid' && t.charId === charId) { t.hired = true; break; } }
  if (aiIdx !== Shell.currentAI) return;
  const card = document.getElementById('thought-bid-' + aiIdx + '-' + charId);
  if (!card) return;
  if (!card.querySelector('.thought-hired-badge'))
    card.insertAdjacentHTML('beforeend', '<div class="thought-hired-badge">✓ Hired</div>');
  const streamEl = document.getElementById('thinking-stream');
  if (streamEl && streamEl.firstChild !== card) {
    streamEl.insertBefore(card, streamEl.firstChild);
    streamEl.scrollTop = 0;
  }
  if (arr) {
    const i = arr.findIndex(x => x.kind === 'bid' && x.charId === charId);
    if (i > 0) { const [item] = arr.splice(i, 1); arr.unshift(item); }
  }
}

function _renderThinking() {
  const stream = document.getElementById('thinking-stream');
  if (!stream) return;
  stream.innerHTML = '';
  const items = _aiStreams[Shell.currentAI] || [];
  if (!items.length) {
    stream.innerHTML = '<div class="thinking-empty">No thoughts yet.</div>';
    return;
  }
  const hiredHere = _hiredMarks[Shell.currentAI];
  items.forEach(t => {
    const line = document.createElement('div');
    line.className = `thought-line tk-${t.kind}`;
    line.style.animation = 'none';
    if (t.id) line.id = 'thought-' + t.id;
    const showHired = t.kind === 'bid' && t.charId != null
      && (t.hired || (hiredHere && hiredHere.has(t.charId)));
    line.innerHTML =
      `<div class="thought-kind">${Shell.helpers.escapeHtml(t.title)}</div>` +
      `<div class="thought-body">${t.body}</div>` +
      (showHired ? '<div class="thought-hired-badge">✓ Hired</div>' : '');
    stream.appendChild(line);
  });
}

function _flashCard(charId) {
  const el = document.getElementById('cc-' + charId);
  if (!el) return;
  el.classList.remove('bidding-flash');
  void el.offsetWidth;
  el.classList.add('bidding-flash');
  el.scrollIntoView({ block:'nearest', behavior:'smooth' });
}

// ── status / heat ─────────────────────────────────────────────────────────────
function _setStatus(cls, text) {
  const b = document.getElementById('status-badge');
  if (!b) return;
  b.className = cls; b.textContent = text;
}
function _updateHeat(n) {
  const el = document.getElementById('heat-display');
  if (!el) return;
  el.textContent = n ? '● '.repeat(n).trim() + '  heat ' + n : '';
}
