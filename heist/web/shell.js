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

// ── shared component styles ─────────────────────────────────────────────────
// The .char-card component is rendered by Shell.helpers.charCardHtml below
// and used across the Hiring, Job, and Heist tabs. Its CSS lives here so the
// component is self-contained — any page that loads shell.js gets the styling
// without each tab having to re-import the rules.
(function injectCharCardStyles() {
  if (document.getElementById('shell-char-card-styles')) return;
  const style = document.createElement('style');
  style.id = 'shell-char-card-styles';
  style.textContent = `
/* character card (rendered by Shell.helpers.charCardHtml) */
.char-card {
  position: relative;
  border-radius: 7px;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex; flex-direction: column;
  background: var(--panel2);
  animation: cardIn 0.35s ease;
}
@keyframes cardIn {
  from { opacity: 0; transform: scale(0.95) translateY(4px); }
  to   { opacity: 1; transform: none; }
}
.char-card[data-primary="hack"]  { background: linear-gradient(180deg, rgba(88,152,224,0.32) 0%, rgba(88,152,224,0.08) 100%); border-color: rgba(88,152,224,0.65); }
.char-card[data-primary="safe"]  { background: linear-gradient(180deg, rgba(232,160,48,0.32) 0%, rgba(232,160,48,0.08) 100%); border-color: rgba(232,160,48,0.65); }
.char-card[data-primary="musc"]  { background: linear-gradient(180deg, rgba(224,80,80,0.32) 0%, rgba(224,80,80,0.08) 100%);  border-color: rgba(224,80,80,0.65); }
.char-card[data-primary="soc"]   { background: linear-gradient(180deg, rgba(144,112,224,0.32) 0%, rgba(144,112,224,0.08) 100%); border-color: rgba(144,112,224,0.65); }
.char-card[data-primary="drive"] { background: linear-gradient(180deg, rgba(82,196,122,0.32) 0%, rgba(82,196,122,0.08) 100%); border-color: rgba(82,196,122,0.65); }

.char-card.bidding-flash { animation: bidFlash 0.7s ease; }
@keyframes bidFlash {
  0%, 100% { box-shadow: none; }
  40%      { box-shadow: 0 0 0 2px rgba(255,255,255,0.5); }
}

.cc-portrait {
  width: 100%; aspect-ratio: 1;
  background: rgba(0,0,0,0.35);
  overflow: hidden;
  position: relative;
}
.cc-portrait img { width: 100%; height: 100%; object-fit: cover; display: block; }
.cc-portrait-fallback {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; font-weight: 700; color: rgba(255,255,255,0.25);
  font-family: monospace;
}
.cc-header {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px;
  font-weight: 800;
  min-width: 0;
}
.char-card[data-primary="hack"]  .cc-header { background: var(--sk-hack);  color: #0a1428; }
.char-card[data-primary="safe"]  .cc-header { background: var(--sk-safe);  color: #2a1c08; }
.char-card[data-primary="musc"]  .cc-header { background: var(--sk-musc);  color: #2a0808; }
.char-card[data-primary="soc"]   .cc-header { background: var(--sk-soc);   color: #1c1030; }
.char-card[data-primary="drive"] .cc-header { background: var(--sk-drive); color: #0a2018; }
.cc-name {
  font-size: 12px; letter-spacing: 0.2px; min-width: 0; flex: 1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cc-cost-row {
  padding: 4px 8px 5px;
  font-family: monospace; font-size: 11px;
  color: var(--muted); text-align: right;
  border-top: 1px solid rgba(255,255,255,0.04);
}
.cc-info { padding: 6px 8px 7px; display: flex; flex-direction: column; gap: 3px; }
.cc-skills { display: flex; flex-direction: column; gap: 2px; }
.cc-skill { display: flex; align-items: center; gap: 6px; }
.cc-skill-label {
  font-size: 9px; font-weight: 700; letter-spacing: 0.6px;
  color: var(--muted); width: 30px; flex-shrink: 0;
  font-family: monospace;
}
.cc-skill-bars { display: flex; gap: 2px; }
.seg { width: 10px; height: 4px; border-radius: 1px; background: rgba(255,255,255,0.08); }
.seg.f-hack  { background: var(--sk-hack); }
.seg.f-safe  { background: var(--sk-safe); }
.seg.f-musc  { background: var(--sk-musc); }
.seg.f-soc   { background: var(--sk-soc); }
.seg.f-drive { background: var(--sk-drive); }

`;
  document.head.appendChild(style);
})();

// Shared portrait card used by the Heist scene lead and the Campaign war room.
(function injectPortraitCardStyles() {
  if (document.getElementById('shell-portrait-card-styles')) return;
  const style = document.createElement('style');
  style.id = 'shell-portrait-card-styles';
  style.textContent = `
.portrait-card {
  position: relative;
  aspect-ratio: 1;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: rgba(0,0,0,0.35);
}
.portrait-card[data-primary="hack"]  { background: linear-gradient(180deg, rgba(88,152,224,0.32) 0%, rgba(88,152,224,0.08) 100%); border-color: rgba(88,152,224,0.65); }
.portrait-card[data-primary="safe"]  { background: linear-gradient(180deg, rgba(232,160,48,0.32) 0%, rgba(232,160,48,0.08) 100%); border-color: rgba(232,160,48,0.65); }
.portrait-card[data-primary="musc"]  { background: linear-gradient(180deg, rgba(224,80,80,0.32) 0%, rgba(224,80,80,0.08) 100%); border-color: rgba(224,80,80,0.65); }
.portrait-card[data-primary="soc"]   { background: linear-gradient(180deg, rgba(144,112,224,0.32) 0%, rgba(144,112,224,0.08) 100%); border-color: rgba(144,112,224,0.65); }
.portrait-card[data-primary="drive"] { background: linear-gradient(180deg, rgba(82,196,122,0.32) 0%, rgba(82,196,122,0.08) 100%); border-color: rgba(82,196,122,0.65); }
.pc-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: monospace;
  font-weight: 700;
  font-size: 46px;
  color: rgba(255,255,255,0.30);
}
.portrait-card img {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pc-cap {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2;
  padding: 4px 6px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.3px;
  text-align: center;
  line-height: 1.2;
}
.portrait-card[data-primary="hack"] .pc-cap { background: var(--sk-hack); color: #0a1428; }
.portrait-card[data-primary="safe"] .pc-cap { background: var(--sk-safe); color: #2a1c08; }
.portrait-card[data-primary="musc"] .pc-cap { background: var(--sk-musc); color: #2a0808; }
.portrait-card[data-primary="soc"] .pc-cap { background: var(--sk-soc); color: #1c1030; }
.portrait-card[data-primary="drive"] .pc-cap { background: var(--sk-drive); color: #0a2018; }
.portrait-card.portrait-card--noname .pc-cap { display: none; }
.pc-stamp {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(224,80,80,0.18);
  color: rgba(255,210,210,0.94);
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 1.8px;
  text-transform: uppercase;
  transform: rotate(-12deg) scale(0.85);
  opacity: 0;
  pointer-events: none;
  transition: opacity 180ms ease, transform 180ms ease;
}
.portrait-card.captured .pc-stamp,
.portrait-card.caught-landed .pc-stamp,
.portrait-card.caught-now .pc-stamp {
  opacity: 1;
  transform: rotate(-12deg) scale(1);
}
.portrait-card.captured {
  opacity: 0.25;
  filter: grayscale(0.7);
  border-style: dashed;
  border-color: rgba(224,80,80,0.48) !important;
}
.portrait-card.caught-landed,
.portrait-card.caught-now {
  opacity: 1;
  filter: none;
}
`;
  document.head.appendChild(style);
})();

// ── thinking bar styles ───────────────────────────────────────────────────────
// The AI picker (#ai-picker) and thinking stream (#thinking-section) are
// injected into #rail by _mountThinkingBar() at initShell time. Their CSS
// lives here so no page file needs to duplicate it.
(function injectThinkingBarStyles() {
  if (document.getElementById('shell-thinking-bar-styles')) return;
  const style = document.createElement('style');
  style.id = 'shell-thinking-bar-styles';
  style.textContent = `
#ai-picker {
  flex-shrink: 0; padding: 7px 10px;
  display: flex; gap: 5px; align-items: center;
  border-bottom: 1px solid var(--border);
  background: var(--panel2);
}
.ai-pick-label { font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); margin-right: 4px; }
.ai-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 18px;
  font-size: 11px; font-weight: 700;
  background: transparent; border: 1px solid var(--border);
  color: var(--muted); cursor: pointer; transition: all 0.15s;
}
.ai-pill:hover { color: var(--text); }
.ai-pill.ap-active { background: var(--panel); color: var(--text); }
.ai-pill .ap-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--border); }
.ai-pill[data-aiidx="0"].ap-active { border-color: var(--ai-a); }
.ai-pill[data-aiidx="0"] .ap-dot { background: var(--ai-a); }
.ai-pill[data-aiidx="1"].ap-active { border-color: var(--ai-b); }
.ai-pill[data-aiidx="1"] .ap-dot { background: var(--ai-b); }
.ai-pill[data-aiidx="2"].ap-active { border-color: var(--ai-c); }
.ai-pill[data-aiidx="2"] .ap-dot { background: var(--ai-c); }

#thinking-section { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.thinking-header { padding: 8px 14px; flex-shrink: 0; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid var(--border); }
.thinking-avatar { width: 16px; height: 16px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700; color: #000; }
.thinking-title  { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--text); flex: 1; }
.thinking-private { font-size: 9px; font-weight: 700; letter-spacing: 1px; color: var(--muted); background: #1e1e22; padding: 2px 6px; border-radius: 3px; }
#journey-controls {
  flex-shrink: 0;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  background: var(--panel2);
}
.journey-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.journey-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--muted);
  min-width: 34px;
}
.journey-rounds {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.journey-round {
  appearance: none;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  border-radius: 18px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.journey-round:hover { color: var(--text); border-color: rgba(232,160,48,0.35); }
.journey-round.active {
  color: var(--text);
  border-color: rgba(232,160,48,0.5);
  background: rgba(232,160,48,0.08);
}
.journey-team {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
}
#thinking-stream { flex: 1; overflow-y: auto; padding: 8px 12px; display: flex; flex-direction: column; gap: 6px; }
.thought-line { font-size: 12px; line-height: 1.5; padding: 7px 10px; border-radius: 4px; background: var(--panel2); border-left: 3px solid var(--border); animation: slideDownIn 0.35s ease; }
@keyframes slideDownIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
.thought-kind { font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); margin-bottom: 3px; }
.thought-body { color: #d0cee0; }
.thought-body strong { color: var(--text); font-weight: 600; }
.thought-line.tk-strategy { border-left-color: var(--accent); }
.thought-line.tk-strategy .thought-kind { color: var(--accent); }
.thought-line.tk-bid { border-left-color: var(--blue); }
.thought-line.tk-bid .thought-kind { color: var(--blue); }
.thought-line.tk-hire { border-left-color: var(--green); }
.thought-line.tk-hire .thought-kind { color: var(--green); }
.thought-line.tk-job { border-left-color: var(--purple); }
.thought-line.tk-job .thought-kind { color: var(--purple); }
.thought-line.tk-scene { border-left-color: var(--muted); }
.thought-sub-head { font-size: 9px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: var(--purple); margin-top: 6px; margin-bottom: 2px; }
.thought-sub-head:first-child { margin-top: 0; }
.thinking-empty { font-size: 12px; color: var(--muted); font-style: italic; text-align: center; padding: 16px 0; }
.thought-hired-badge  { margin-top: 6px; display: inline-flex; align-items: center; gap: 4px; background: #0c2018; color: var(--green); padding: 2px 7px; border-radius: 3px; font-size: 10px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
.thought-failed-badge { margin-top: 6px; display: inline-flex; align-items: center; gap: 4px; background: #2e0c0c; color: var(--red);   padding: 2px 7px; border-radius: 3px; font-size: 10px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
`;
  document.head.appendChild(style);
})();

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
  aiList: [{ idx: 0, label: 'AI', name: 'AI', team_name: 'AI', color: 'var(--ai-a)' }],
  currentAI: 0,
  journeyMode: false,
  journey: null,
  selectedRoundIdx: 0,
  replayGameId: null,
  replayAiIndices: new Set(),
  replayEvents: [],  // set by initShell after loading replay buffer
  phaseUrl(phase, opts) { return _buildPhaseUrl(phase, opts); },

  helpers: {
    escapeHtml(s) {
      return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    },
    thoughtCardHtml(kind, title, bodyHtml, opts) {
      const esc = Shell.helpers.escapeHtml;
      const { id = '', hired = false, failed = false } = opts || {};
      const idAttr = id ? ` id="${esc(id)}"` : '';
      return `<div class="thought-line tk-${kind}"${idAttr}>` +
        `<div class="thought-kind">${esc(title)}</div>` +
        `<div class="thought-body">${bodyHtml ?? ''}</div>` +
        (hired  ? '<div class="thought-hired-badge">✓ Hired</div>'  : '') +
        (failed ? '<div class="thought-failed-badge">✗ Failed</div>' : '') +
        `</div>`;
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
      // Try local portrait first. Server returns 404 if not generated yet;
      // the <img> onerror handler hides the image and the initials show instead.
      if (c && c.id) return `/portraits/${c.id}`;
      const p = Shell.helpers.primarySkill(c);
      const seed = (c.name || '').toLowerCase().replace(/\s+/g, '');
      return `https://api.dicebear.com/9.x/${PORTRAIT_STYLE[p]}/svg?seed=${encodeURIComponent(seed)}&backgroundColor=${PORTRAIT_BG[p]}`;
    },
    portraitCardHtml(c, opts) {
      const esc = Shell.helpers.escapeHtml;
      const {
        charId = null,
        captured = false,
        widthPx = null,
        hideName = false,
        extraClasses = '',
      } = opts || {};
      const name = String(c?.name ?? '?');
      const initials = (name.trim().slice(0, 1) || '?').toUpperCase();
      const classes = ['portrait-card'];
      if (captured) classes.push('captured');
      if (hideName) classes.push('portrait-card--noname');
      if (extraClasses) classes.push(String(extraClasses).trim());
      const styleAttr = (widthPx != null && Number(widthPx) > 0) ? ` style="width: ${Number(widthPx)}px;"` : '';
      const charIdAttr = charId != null ? ` data-char-id="${esc(charId)}"` : '';
      const primary = Shell.helpers.primarySkill(c);
      return `<div class="${classes.filter(Boolean).join(' ')}" data-primary="${primary}"${charIdAttr}${styleAttr}>
        <div class="pc-fallback">${esc(initials)}</div>
        <img src="${Shell.helpers.portraitUrl(c)}" alt="${esc(name)}" loading="lazy" onerror="this.style.display='none'">
        <div class="pc-cap">${esc(name)}</div>
        <div class="pc-stamp">CAUGHT</div>
      </div>`;
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
  // Called by HiringTab when each bid chip starts flying (stagger is owned by the
  // hiring tab; shell renders the card at that exact moment for sync).
  bidChipFired(aiIdx, charId, amount, rationale) { _bidChipFired(aiIdx, charId, amount, rationale); },
  // Called by HiringTab when auction_round_resolved marks a bid won/failed.
  markBidResult(aiIdx, charId, result) { _markBidResult(aiIdx, charId, result); },
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
let _reviewMode    = false;  // true → fast-forward all events instantly, no animation
let _visibleByAI   = {};     // ai_idx → [buffer indices of visible events for that AI]

const _THOUGHT_CARD_DELAY_MS = (() => {
  const p = new URLSearchParams(window.location.search);
  const n = parseInt(p.get('cardDelay') || '', 10);
  return Number.isFinite(n) ? n : 1000;
})();
const _thoughtQueue = [];
let   _thoughtTimer  = null;

let _currentOnEvent = null;  // set by initShell; used by replayStep

function _isJourneyMode() {
  return !!Shell.journeyMode && !!Shell.journey;
}

function _currentPhasePath() {
  const p = window.location.pathname.replace(/^\//, '').split('?')[0];
  return p || 'hiring';
}

function _journeyTeamName(team) {
  return team?.team_name || team?.ai_name || team?.name || 'Team';
}

function _journeyRoundFor(team, roundIdx) {
  if (!team || !Array.isArray(team.rounds)) return null;
  return team.rounds.find(r => Number(r.round_idx) === Number(roundIdx)) || null;
}

function _journeyTeamFor(aiIdx) {
  if (!Shell.journey || !Array.isArray(Shell.journey.teams)) return null;
  return Shell.journey.teams.find(team => Number(team.ai_idx) === Number(aiIdx)) || null;
}

function _selectedJourneyTeam(aiIdx) {
  const teams = Shell.journey?.teams || [];
  if (!teams.length) return null;
  const wanted = Number.isFinite(Number(aiIdx)) ? Number(aiIdx) : Shell.currentAI;
  return _journeyTeamFor(wanted) || teams[0];
}

function _selectedJourneyRound(roundIdx) {
  const total = Number(Shell.journey?.num_rounds || 0);
  if (!total) return 0;
  const raw = Number.isFinite(Number(roundIdx)) ? Number(roundIdx) : Shell.selectedRoundIdx;
  return Math.max(0, Math.min(total - 1, raw));
}

function _buildPhaseUrl(phase, opts = {}) {
  const path = String(phase || _currentPhasePath()).replace(/^\//, '') || 'hiring';
  const params = new URLSearchParams();
  if (_isJourneyMode()) {
    const journey = Shell.journey;
    const team = _selectedJourneyTeam(opts.aiIdx);
    const roundIdx = _selectedJourneyRound(opts.roundIdx);
    params.set('campaign', String(journey.campaign_id));
    params.set('ai', String(team?.ai_idx ?? Shell.currentAI ?? 0));
    params.set('round', String(roundIdx));
  } else {
    const gameId = opts.gameId ?? Shell.replayGameId ?? new URLSearchParams(window.location.search).get('game');
    if (gameId != null && gameId !== '') params.set('game', String(gameId));
  }
  if (opts.atStage != null) params.set('atStage', String(opts.atStage));
  if (opts.autoplay) params.set('autoplay', '1');
  const q = params.toString();
  return q ? `/${path}?${q}` : `/${path}`;
}

// ── _attachStrategyToStarts ───────────────────────────────────────────────────
// For each turn_start bid_round_N event, peek ahead to find the matching
// turn_end and copy casting_strategy onto the start event as e._strategy.
// This lets _processEvent show the strategy card at step 1 (turn_start),
// before bids are revealed at step 2 (turn_end).
function _attachStrategyToStarts(events) {
  events.forEach(e => {
    if (e.type !== 'turn_start' || !/^bid_round_\d+$/.test(e.label || '')) return;
    const match = events.find(e2 =>
      e2.type === 'turn_end' && e2.label === e.label && e2.ai_idx === e.ai_idx
    );
    if (match && match.parsed) {
      // Auction rounds use 'reasoning'; legacy 'bid' label uses 'casting_strategy'
      e._strategy = match.parsed.casting_strategy || match.parsed.reasoning || '';
    }
  });
}

// ── isVisibleEvent: true for events that produce a visible DOM change ─────────
function _isVisibleEvent(e) {
  if (e.type === 'hidden_depth_rolled') return false;
  // Campaign-conductor events (campaign_stage / campaign_round_done /
  // campaign_done) can leak into an older sub-game's persisted event log.
  // The hire/heist replay has no renderer for them, so they would otherwise
  // surface as blank, dead stop-points. Never treat them as visible stages.
  if (typeof e.type === 'string' && e.type.startsWith('campaign_')) return false;
  if (e.type === 'turn_start') {
    // Auction bid starts are visible: they show the strategy card before chips
    // land, so the user sees intent before the bids are revealed.
    return /^bid_round_\d+$/.test(e.label || '');
  }
  if (e.type === 'turn_end') {
    const label = e.label || '';
    if (label === 'bid')             return true;
    if (/^bid_round_\d+$/.test(label)) return true;  // auction: each round's bids
    if (label === 'job_pick')        return true;
    if (label === 'casting_summary') return true;
    if (/^scene_\d+_(?:escape_)?narrate$/.test(label)) return true;
    return false;
  }
  return true;
}

// Returns true if the event belongs to the currently-selected AI, or has no
// ai_idx (system/global events). Used by Step/Back to skip other AIs' events.
function _isCurrentAIEvent(e) {
  if (/^bid_round_\d+$/.test(e.label || '')) {
    // Every AI's bid reveal (turn_end) is a stop point — user sees all bids land.
    if (e.type === 'turn_end') return true;
    // Strategy preview (turn_start) is only a stop point for the current AI;
    // other AIs' strategy is invisible to this viewer, so skip the empty step.
    if (e.type === 'turn_start') return (e.ai_idx ?? 0) === Shell.currentAI;
  }
  return e.ai_idx === undefined || e.ai_idx === Shell.currentAI;
}

// Returns true if Step/Back should skip this event even when it belongs to
// the current AI.  On the heist page:
//   • scene_start  — card is empty until scene_done; skip so user sees nothing
//                    until the full card (chars + narration + result) lands.
//   • scene_narrate — narration arrives before chars; skipping means scene_done
//                     shows both together in one step.
function _isReplaySkipEvent(e) {
  if (_currentPhasePath() !== 'heist') return false;
  if (e.type === 'scene_start') return true;
  if (e.type === 'turn_end' && /^scene_\d+_(escape_)?narrate$/.test(e.label || '')) return true;
  return false;
}

// The most recent visible stage ≤ maxStage whose event is for the current AI
// and is not a replay-skip event.
// Falls back to maxStage if no such event is found (so Back never stalls).
function _prevCurrentAIStage(maxStage) {
  let n = 0, result = maxStage;
  for (let i = 0; i < _REPLAY_EVENTS.length; i++) {
    if (!_isVisibleEvent(_REPLAY_EVENTS[i])) continue;
    n++;
    if (n > maxStage) break;
    if (_isCurrentAIEvent(_REPLAY_EVENTS[i]) && !_isReplaySkipEvent(_REPLAY_EVENTS[i])) result = n;
  }
  return result;
}

// ── stage helpers ─────────────────────────────────────────────────────────────
// A "stage" is one visible event in the buffer, counted globally (not per-AI).
// Step advances by 1 visible event; Back rewinds by 1. Multi-AI events
// interleave in the buffer in the order the runner emitted them, so each
// stage = exactly one DOM-affecting thing happens.
function _computeVisibleByAI() {
  // Kept for backwards compat (the AI picker uses it indirectly via stage
  // helpers below); rebuilt now as a simple index→AI lookup.
  _visibleByAI = {};
  _REPLAY_EVENTS.forEach((evt, i) => {
    if (!_isVisibleEvent(evt)) return;
    const ai = evt.ai_idx ?? 0;
    if (!_visibleByAI[ai]) _visibleByAI[ai] = [];
    _visibleByAI[ai].push(i);
  });
}
function _totalStages() {
  let n = 0;
  for (let i = 0; i < _REPLAY_EVENTS.length; i++) {
    if (_isVisibleEvent(_REPLAY_EVENTS[i])) n++;
  }
  return n;
}
function _currentStage() {
  let n = 0;
  const cap = Math.min(_REPLAY_INDEX, _REPLAY_EVENTS.length);
  for (let i = 0; i < cap; i++) {
    if (_isVisibleEvent(_REPLAY_EVENTS[i])) n++;
  }
  return n;
}
// Buffer index right after the Nth visible event in the whole buffer.
// Used by Step/Back/_jumpToStage to set _REPLAY_INDEX precisely.
function _bufferIndexAfterStage(stage) {
  if (stage <= 0) return 0;
  let n = 0;
  for (let i = 0; i < _REPLAY_EVENTS.length; i++) {
    if (_isVisibleEvent(_REPLAY_EVENTS[i])) {
      n++;
      if (n === stage) return i + 1;
    }
  }
  return _REPLAY_EVENTS.length;
}

// ── replay controls ───────────────────────────────────────────────────────────
function replayStep() {
  const total = _totalStages();
  if (_currentStage() >= total) {
    if (_REPLAY_TIMER) replayToggle();
    return;
  }
  // Advance through visible events until we land on one for the current AI.
  // Events for other AIs are still processed (internal state stays correct)
  // but don't count as a stop point — the user sees something every step.
  while (_REPLAY_INDEX < _REPLAY_EVENTS.length) {
    const cur        = _currentStage();
    if (cur >= total) break;
    const targetIdx  = _bufferIndexAfterStage(cur + 1);
    const visibleEvt = _REPLAY_EVENTS[targetIdx - 1];
    while (_REPLAY_INDEX < targetIdx && _REPLAY_INDEX < _REPLAY_EVENTS.length) {
      _processEvent(_REPLAY_EVENTS[_REPLAY_INDEX++], _currentOnEvent);
    }
    if (!visibleEvt || (_isCurrentAIEvent(visibleEvt) && !_isReplaySkipEvent(visibleEvt))) break;
  }
  _replayUpdateCounter();
  if (_currentStage() >= total) {
    // Advance to the next journey phase BEFORE stopping the timer, so play mode
    // carries the autoplay flag onto the next page. No-op outside journey mode.
    _journeyMaybeAdvanceAtEnd();
    if (_REPLAY_TIMER) replayToggle();
  }
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

// ── phasenav ──────────────────────────────────────────────────────────────────
// Rewrites #phasenav after events load so completed phases become clickable
// links back to that phase in review mode.
function _updatePhasenav(gameId, events) {
  const nav = document.getElementById('phasenav');
  if (!nav || !gameId) return;

  // Inject link styles once
  if (!document.getElementById('_phase-link-styles')) {
    const s = document.createElement('style');
    s.id = '_phase-link-styles';
    s.textContent = 'a.phase-item{text-decoration:none;cursor:pointer}' +
                    'a.phase-item:hover{color:var(--text)!important}';
    document.head.appendChild(s);
  }

  // Reachability differs by mode. A single-game replay has every phase in one
  // event stream, so detect them from the loaded events. In CAMPAIGN (journey)
  // mode each round is split into a hire sub-game + a heist sub-game, so the
  // current page's events can't see the other phases — derive reachability from
  // the round's sub-game ids instead (job/heist/epilogue all live in that
  // round's heist sub-game).
  let hasHiring = true, hasJob, hasHeist, hasEpilogue;
  if (_isJourneyMode()) {
    const round = _journeyRoundFor(_selectedJourneyTeam(Shell.currentAI), Shell.selectedRoundIdx);
    hasHiring = round?.hire_sub_game_id != null;
    hasJob = hasHeist = hasEpilogue = round?.heist_sub_game_id != null;
  } else {
    hasJob      = events.some(e => e.type === 'job_known');
    hasHeist    = events.some(e => e.type === 'scene_start');
    hasEpilogue = events.some(e => e.type === 'game_done');
  }

  const current = window.location.pathname.replace(/^\//, '').split('?')[0] || 'hiring';

  const phases = [
    { label: 'Hiring',   path: 'hiring',   reachable: hasHiring   },
    { label: 'Job',      path: 'job',       reachable: hasJob      },
    { label: 'Heist',    path: 'heist',     reachable: hasHeist    },
    { label: 'Epilogue', path: 'epilogue',  reachable: hasEpilogue },
  ];

  nav.innerHTML = phases.map((p, i) => {
    const sep = i < phases.length - 1 ? '<span class="phase-sep">→</span>' : '';
    if (p.path === current) {
      return `<span class="phase-item phase-active">${p.label}</span>${sep}`;
    }
    if (p.reachable) {
      return `<a class="phase-item phase-done" href="${Shell.phaseUrl(p.path)}">${p.label}</a>${sep}`;
    }
    return `<span class="phase-item">${p.label}</span>${sep}`;
  }).join('');
}

// ── phase navigation ──────────────────────────────────────────────────────────
// Called by each page when it reaches its phase boundary (e.g. job_known,
// scene_start, game_done). In play mode we navigate immediately and carry the
// autoplay flag so the next page resumes playing. In step mode we stop and
// show a Continue button so the user can read the current page at their own pace.
function _atPhaseEnd(url) {
  if (_reviewMode) return;  // fast-forward pass — don't navigate
  // Always navigate. In play mode, carry the autoplay flag so the next page
  // resumes automatically; otherwise just navigate.
  if (_REPLAY_TIMER) {
    const sep = url.includes('?') ? '&' : '?';
    window.location = url + sep + 'autoplay=1';
  } else {
    window.location = url;
  }
}

function _replayUpdateCounter() {
  const el = document.getElementById('replay-counter');
  if (!el) return;
  el.textContent = `${_currentStage()} / ${_totalStages()}`;
}

function _prevPhaseUrl(stage) {
  const current = window.location.pathname.replace(/^\//, '');
  const phases   = ['hiring', 'job', 'heist', 'epilogue'];
  const idx      = phases.indexOf(current);
  if (idx <= 0) return null;
  // Pass the target stage so the previous page lands exactly one event back
  // instead of fast-forwarding to its own phase-start default.
  return Shell.phaseUrl(phases[idx - 1], { atStage: stage });
}

// Jump replay state to exactly `stage` stages processed across all AIs.
// Used by Back, AI-switch rewind, page-load auto-fast-forward.
function _jumpToStage(stage) {
  if (_REPLAY_TIMER) replayToggle();
  _REPLAY_INDEX = 0;
  _thoughtQueue.length = 0;
  if (_thoughtTimer) { clearTimeout(_thoughtTimer); _thoughtTimer = null; }
  for (const k of Object.keys(_hiredMarks)) delete _hiredMarks[k];
  _aiStreams.forEach((_, i) => _aiStreams[i] = []);
  _renderThinking();
  if (_currentOnEvent) { try { _currentOnEvent({ type: '_reset' }); } catch {} }

  if (stage > 0) {
    const targetIdx = _bufferIndexAfterStage(stage);
    _reviewMode = true;
    while (_REPLAY_INDEX < targetIdx && _REPLAY_INDEX < _REPLAY_EVENTS.length) {
      _processEvent(_REPLAY_EVENTS[_REPLAY_INDEX++], _currentOnEvent);
    }
    _reviewMode = false;
  }
  _replayUpdateCounter();
}

function replayBack() {
  if (_REPLAY_TIMER) replayToggle();
  const cur = _currentStage();
  const phaseStart = _phaseStartStage(_currentPhasePath()) || 1;
  if (cur <= phaseStart) {
    // At the start of this phase — hop to the previous page at stage (cur - 1)
    // so Back keeps moving one event backward even across page boundaries.
    if (cur <= 1) return;  // already at the very first event; nothing before it
    const prev = _prevPhaseUrl(cur - 1);
    if (prev) window.location = prev;
    return;
  }
  _jumpToStage(_prevCurrentAIStage(cur - 1));
}

// Stage where the current page's phase ENDS (= last visible event still
// rendered on this page). Beyond this, events affect the NEXT page only,
// so Back here has no visible effect — that's why we cap to this.
function _phaseEndStage(phase) {
  const phases = ['hiring', 'job', 'heist', 'epilogue'];
  const idx = phases.indexOf(phase);
  if (idx < 0 || idx === phases.length - 1) return _totalStages();
  const nextStart = _phaseStartStage(phases[idx + 1]);
  return nextStart ? Math.max(1, nextStart - 1) : _totalStages();
}

// Stage where the current page's content begins. Each page auto-fast-forwards
// to this stage on load so the user starts at their phase, not at the bid.
function _phaseStartStage(phase) {
  if (phase === 'hiring') return 1;
  let pred;
  // /job opens BEFORE the AI's pick lands — at casting_summary — so the user
  // sees the full job slate first and watches the AI choose.
  if      (phase === 'job')      pred = e => e.type === 'turn_end' && e.label === 'casting_summary';
  else if (phase === 'heist')    pred = e => e.type === 'scene_done';
  else if (phase === 'epilogue') pred = e => e.type === 'game_done';
  else return 1;
  // Scan the full buffer in order; first visible event matching pred
  // (across any AI) is the phase boundary.
  let n = 0;
  for (let i = 0; i < _REPLAY_EVENTS.length; i++) {
    if (!_isVisibleEvent(_REPLAY_EVENTS[i])) continue;
    n++;
    if (pred(_REPLAY_EVENTS[i])) return n;
  }
  return null;
}

// Journey mode: each phase's sub-game stream lacks the NEXT phase's in-stream
// trigger (the auction sub-game has no `casting_summary`; the round-heist
// sub-game has no `game_done`), so the normal page-driven phase nav can't fire
// across the sub-game boundary. Advance to the next journey phase when THIS
// phase's replay finishes. Job → Heist still happens in-stream on `scene_start`.
function _journeyMaybeAdvanceAtEnd() {
  if (!Shell.journeyMode) return;
  const nextAtEnd = { hiring: 'job', heist: 'epilogue' };
  const next = nextAtEnd[_currentPhasePath()];
  if (next) _atPhaseEnd(Shell.phaseUrl(next));
}

// Expose for HTML onclick attributes and cross-page calls
window.replayStep   = replayStep;
window.replayBack   = replayBack;
window.replayToggle = replayToggle;
window.replayReset  = replayReset;
window.Shell.atPhaseEnd = _atPhaseEnd;

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
window.initShell = async function({ gameId, campaignId, aiIdx, roundIdx, onEvent } = {}) {
  _currentOnEvent = onEvent || null;

  // 1. Load roster + job slate so tab fragments can render them
  try {
    const meta = await fetch('/api/meta').then(r => r.json());
    Shell.roster = meta.roster || [];
    Shell.roster.forEach(c => Shell.charById.set(c.id, c));
    Shell.jobs = meta.jobs || [];
  } catch (e) {
    console.error('shell: failed to load meta', e);
  }

  const urlParams = new URLSearchParams(window.location.search);
  const journeyCampaignId = campaignId ?? urlParams.get('campaign');
  const journeyAiIdx = aiIdx ?? urlParams.get('ai');
  const journeyRoundIdx = roundIdx ?? urlParams.get('round');
  const isJourney = journeyCampaignId != null && journeyCampaignId !== '';

  Shell.journeyMode = isJourney;
  Shell.journey = null;
  Shell.selectedRoundIdx = 0;
  Shell.replayGameId = null;
  Shell.replayAiIndices = new Set();

  let targetGame = null;
  try {
    if (isJourney) {
      const journey = await fetch(`/api/campaign-journey/${encodeURIComponent(journeyCampaignId)}`).then(r => {
        if (!r.ok) throw new Error(`fetch /api/campaign-journey/${journeyCampaignId}: ${r.status}`);
        return r.json();
      });
      Shell.journey = journey;
      Shell.aiList = (journey.teams || []).map((team, i) => {
        const label = _journeyTeamName(team);
        return {
          idx: Number(team.ai_idx ?? i),
          label,
          name: label,
          team_name: label,
          color: ['var(--ai-a)', 'var(--ai-b)', 'var(--ai-c)'][i] || 'var(--ai-a)',
        };
      });
      while (_aiStreams.length < Shell.aiList.length) _aiStreams.push([]);
      const selectedTeam = _selectedJourneyTeam(parseInt(journeyAiIdx || '0', 10));
      Shell.currentAI = selectedTeam?.ai_idx ?? 0;
      Shell.selectedRoundIdx = _selectedJourneyRound(parseInt(journeyRoundIdx || '0', 10));
      const currentPhase = _currentPhasePath();
      const selectedRound = _journeyRoundFor(selectedTeam, Shell.selectedRoundIdx);
      const selectedGameId = currentPhase === 'hiring'
        ? selectedRound?.hire_sub_game_id
        : selectedRound?.heist_sub_game_id;
      if (selectedGameId == null) {
        throw new Error(`missing ${currentPhase} sub-game for campaign ${journeyCampaignId}, ai ${Shell.currentAI}, round ${Shell.selectedRoundIdx}`);
      }
      targetGame = { id: selectedGameId, campaign_id: journey.campaign_id, round_idx: Shell.selectedRoundIdx, ai_idx: Shell.currentAI };
      Shell.replayGameId = selectedGameId;
    } else {
      // 2. Find this game in the games list → populate aiList
      const gid = gameId != null
        ? (typeof gameId === 'string' ? parseInt(gameId, 10) : gameId)
        : null;
      const games = await fetch('/api/games').then(r => r.json());
      if (gid != null) targetGame = games.find(g => g.id === gid);
      // Campaign sub-games (round replays) are excluded from /api/games but are
      // still accessible via /api/games/<id>/events. If the requested id isn't
      // found, use a stub so we load its events directly instead of falling back
      // to a different game.
      if (!targetGame && gid != null) targetGame = { id: gid, ais: [], status: 'done' };
      if (!targetGame) {
        targetGame = [...games].reverse().find(g => g.status === 'running')
          || [...games].reverse().find(g => g.status === 'done')
          || [...games].reverse()[0];
      }
      if (targetGame && targetGame.ais && targetGame.ais.length) {
        Shell.aiList = targetGame.ais.map((ai, i) => {
          const label = ai.name || ai.agent || ('AI ' + (i + 1));
          return {
            idx: i,
            label,
            name: label,
            color: ['var(--ai-a)', 'var(--ai-b)', 'var(--ai-c)'][i] || 'var(--ai-a)',
          };
        });
        while (_aiStreams.length < Shell.aiList.length) _aiStreams.push([]);
      } else if (targetGame && targetGame.ai_name) {
        // Per-AI campaign sub-game: single AI whose name is stored directly on
        // the game record. Events have ai_idx:null so the inference block won't
        // fire — patch the default aiList entry here instead.
        const colorIdx = targetGame.ai_idx ?? 0;
        Shell.aiList[0] = {
          idx: 0,
          label: targetGame.ai_name,
          name: targetGame.ai_name,
          color: ['var(--ai-a)', 'var(--ai-b)', 'var(--ai-c)'][colorIdx] || 'var(--ai-a)',
        };
      }
      // For campaign rounds: find the shared hiring sub-game and the per-AI
      // campaign games so we can (a) link the phasenav Hiring tab to the right
      // game and (b) get proper team names for old hiring records that lack `ais`.
      if (targetGame && targetGame.campaign_id != null && targetGame.round_idx != null) {
        const mates = games.filter(g =>
          g.campaign_id === targetGame.campaign_id &&
          g.round_idx   === targetGame.round_idx
        );
        const hiringGame = mates.find(g => g.is_hiring_sub);
        if (hiringGame) Shell.hiringSubGameId = hiringGame.id;
        // Per-AI sub-games carry the team name; sort by ai_idx so index 0 = AI A.
        const aiGames = mates
          .filter(g => g.is_campaign_sub && g.ai_name != null)
          .sort((a, b) => (a.ai_idx ?? 0) - (b.ai_idx ?? 0));
        if (aiGames.length) Shell.roundAINames = aiGames.map(g => g.ai_name);
      }
      Shell.replayGameId = targetGame && targetGame.id != null ? targetGame.id : null;
    }
  } catch (e) {
    console.error('shell: failed to load journey/game context', e);
    _addThought(0, 'scene', 'Replay load error', Shell.helpers.escapeHtml(String(e)));
    _setStatus('s-error', 'ERROR');
    return;
  }

  _mountThinkingBar();
  _renderAIPicker();
  _selectAI(Shell.currentAI);

  // 3. Always use replay mode. Load the recorded event buffer and expose
  //    step/play/reset controls. Live SSE is disabled — the user controls pace.
  _setStatus('s-idle', 'REPLAY');
  if (targetGame && targetGame.id != null) {
    try {
      const data = await fetch(`/api/games/${targetGame.id}/events`).then(r => r.json());
      _REPLAY_EVENTS = data.events || [];
      // Journey mode: a per-round HEIST sub-game is single-AI and tags every
      // event ai_idx:null, but Shell.currentAI holds the team's campaign index.
      // Re-attribute those null events to the selected team so the per-AI render
      // filter (aiIdx === Shell.currentAI) matches. The shared auction sub-game
      // tags its events 0/1/2, so when any tagged ai_idx is present we leave the
      // stream untouched.
      if (Shell.journeyMode && !_REPLAY_EVENTS.some(e => e.ai_idx != null)) {
        for (const e of _REPLAY_EVENTS) e.ai_idx = Shell.currentAI;
      }
      Shell.replayEvents = _REPLAY_EVENTS;
      Shell.replayAiIndices = new Set(_REPLAY_EVENTS.map(e => e.ai_idx ?? 0));
      _attachStrategyToStarts(_REPLAY_EVENTS);
      // Hiring sub-game records created before the `ais` field was added won't
      // have aiList populated. Infer the count from the event stream so all
      // crew columns and bid chips render correctly.
      const evtMaxAI = _REPLAY_EVENTS.reduce((m, e) => Math.max(m, e.ai_idx ?? -1), -1);
      if (evtMaxAI >= 0 && Shell.aiList.length <= evtMaxAI) {
        for (let i = Shell.aiList.length; i <= evtMaxAI; i++) {
          const name = Shell.roundAINames && Shell.roundAINames[i];
          const journeyTeam = _journeyTeamFor(i);
          const label = _isJourneyMode()
            ? _journeyTeamName(journeyTeam || { ai_name: name, name })
            : (name || ('AI ' + (i + 1)));
          Shell.aiList.push({ idx: i, label, name: label, color: ['var(--ai-a)','var(--ai-b)','var(--ai-c)'][i] || 'var(--ai-a)' });
        }
        while (_aiStreams.length < Shell.aiList.length) _aiStreams.push([]);
        _renderAIPicker();
        _selectAI(Shell.currentAI);
      }
      _computeVisibleByAI();
      _replayUpdateCounter();
      _updatePhasenav(targetGame.id, _REPLAY_EVENTS);
    } catch (e) {
      _addThought(0, 'scene', 'Replay load error', Shell.helpers.escapeHtml(String(e)));
    }
  }

  const _params = new URLSearchParams(window.location.search);
  const _phaseEnd = _phaseEndStage(_currentPhasePath());

  if (_params.get('review') === '1') {
    // Review mode: fast-forward to the END of THIS page's phase (not the end
    // of the whole game). Past that point, events only affect later pages
    // and Back would have no visible effect here.
    _jumpToStage(_phaseEnd);
    return;
  }

  // ?atStage=N — explicit target stage from Back navigation. Honored over the
  // default phase-start jump so "Back" can land on the exact previous event.
  // Capped to this page's phaseEnd so we never sit on a stage with no visible
  // effect on this page.
  const atStageParam = parseInt(_params.get('atStage') || '', 10);
  if (Number.isFinite(atStageParam) && atStageParam >= 0) {
    _jumpToStage(Math.min(atStageParam, _phaseEnd));
  } else {
    // Auto-fast-forward to the start of THIS page's phase so the user begins
    // at the content that's relevant here, not at the very first bid.
    const startStage = _phaseStartStage(_currentPhasePath());
    if (startStage && startStage > 1) _jumpToStage(startStage);
  }

  // If the previous page handed off in play mode, resume playing automatically.
  if (_params.get('autoplay') === '1') replayToggle();
};

// ── event processor ───────────────────────────────────────────────────────────
function _processEvent(e, onEvent) {
  // Rail-level handling (thought cards, bid cards, etc.)
  if (e.type === 'turn_end') _railFromTurnEnd(e);

  // Step 1 of auction bid rounds: show the strategy card now, before bids land.
  if (e.type === 'turn_start' && /^bid_round_\d+$/.test(e.label || '') && e._strategy) {
    const aiIdx = e.ai_idx ?? 0;
    _addThought(aiIdx, 'strategy', 'Strategy', Shell.helpers.escapeHtml(e._strategy));
  }

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
  if ((e.label === 'bid' || /^bid_round_\d+$/.test(e.label || '')) && e.parsed) {
    // Strategy: show at turn_end only for the legacy 'bid' label.
    // For bid_round_N, strategy already showed at turn_start (step 1); skip here.
    if (e.label === 'bid' && e.parsed.casting_strategy) {
      _addThought(aiIdx, 'strategy', 'Strategy', esc(e.parsed.casting_strategy));
    }
    // Bid cards for bid_round_N are driven by HiringTab via Shell.bidChipFired,
    // called when each chip starts flying (one card per chip, staggered in sync).
    // Only add bid cards here for the legacy 'bid' label (pre-auction backend).
    if (e.label === 'bid') {
      (e.parsed.bids || []).forEach(b => {
        const c = Shell.charById.get(b.character_id);
        if (!c) return;
        const amount = b.bid != null ? ' · $' + Number(b.bid).toLocaleString() : '';
        _addThought(aiIdx, 'bid', 'Bid · ' + c.name + amount, esc(b.rationale || '—'),
          { id: 'bid-' + aiIdx + '-' + b.character_id, charId: b.character_id });
      });
    }
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
  const expected = Shell.replayAiIndices && Shell.replayAiIndices.size
    ? Shell.replayAiIndices.size
    : Shell.aiList.length;
  if (_maybeFinishStream._seenDone.size < expected) return;
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
// _mountThinkingBar — called once by initShell. Injects #ai-picker and
// #thinking-section into #rail so pages don't need to duplicate the markup.
function _mountThinkingBar() {
  const rail = document.getElementById('rail');
  if (!rail || document.getElementById('thinking-section')) return;

  if (_isJourneyMode()) {
    const journey = Shell.journey || {};
    const team = _selectedJourneyTeam(Shell.currentAI);
    const roundIdx = _selectedJourneyRound(Shell.selectedRoundIdx);
    const rounds = Array.from({ length: Number(journey.num_rounds || 0) }, (_, i) => {
      const active = i === roundIdx ? ' active' : '';
      return `<button type="button" class="journey-round${active}" onclick="_selectRoundFromUI(${i})">R${i + 1}</button>`;
    }).join('');

    const controls = document.createElement('div');
    controls.id = 'journey-controls';
    controls.innerHTML = `
      <div class="journey-row">
        <span class="journey-label">Round</span>
        <div class="journey-rounds">${rounds}</div>
      </div>
      <div class="journey-row">
        <span class="journey-label">Team</span>
        <div class="journey-team">${Shell.helpers.escapeHtml(_journeyTeamName(team))}</div>
      </div>`;
    rail.appendChild(controls);
  }

  const picker = document.createElement('div');
  picker.id = 'ai-picker';
  picker.innerHTML =
    `<span class="ai-pick-label">${_isJourneyMode() ? 'Team' : 'Mind of'}</span><span id="ai-pills"></span>`;
  rail.appendChild(picker);

  const section = document.createElement('div');
  section.id = 'thinking-section';
  section.innerHTML = `
    <div class="thinking-header">
      <span class="thinking-avatar" id="thinking-avatar" style="background:var(--ai-a)">·</span>
      <span class="thinking-title" id="thinking-title">—</span>
      <span class="thinking-private">Private</span>
    </div>
    <div id="thinking-stream">
      <div class="thinking-empty">Waiting for the game…</div>
    </div>`;
  rail.appendChild(section);
}

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
window._selectAIFromUI = (idx) => {
  if (_isJourneyMode()) {
    window.location = _buildPhaseUrl(_currentPhasePath(), { aiIdx: idx });
    return;
  }
  const prev = Shell.currentAI;
  _selectAI(idx);
  // User-initiated switch: rewind to the start of the current phase so
  // they see this AI's full context for the phase they're looking at.
  if (idx !== prev) {
    const start = _phaseStartStage(_currentPhasePath()) || 1;
    _jumpToStage(start);
  }
};
window._selectRoundFromUI = (roundIdx) => {
  if (!_isJourneyMode()) return;
  window.location = _buildPhaseUrl(_currentPhasePath(), { roundIdx });
};

function _selectAI(idx) {
  Shell.currentAI = idx;
  document.querySelectorAll('.ai-pill').forEach(p =>
    p.classList.toggle('ap-active', parseInt(p.dataset.aiidx) === idx));
  const ai = Shell.aiList.find(a => a.idx === idx) || Shell.aiList[0];
  const av = document.getElementById('thinking-avatar');
  if (av) {
    const initials = String(ai.label || ai.name || '').trim()
      .split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
    av.textContent = initials || ['A', 'B', 'C'][idx] || '·';
    av.style.background = ai.color;
  }
  const tt = document.getElementById('thinking-title');
  if (tt) tt.textContent = ai.label;
  _renderThinking();
  _aiSubscribers.forEach(cb => { try { cb(idx); } catch (e) { console.error('AI subscriber error:', e); } });
}

function _addThought(aiIdx, kind, title, bodyHtml, opts) {
  const t = { aiIdx, kind, title, body: bodyHtml, ...(opts || {}) };
  while (_aiStreams.length <= aiIdx) _aiStreams.push([]);
  _aiStreams[aiIdx].unshift(t);
  if (_THOUGHT_CARD_DELAY_MS <= 0 || _reviewMode) {
    if (aiIdx === Shell.currentAI) _prependThought(t);
    // Chip fires at the same moment the card renders
    if (t.kind === 'bid' && t.charId != null) _flashCard(t.charId);
    return;
  }
  _thoughtQueue.push(t);
  if (!_thoughtTimer) _thoughtTimer = setTimeout(_drainOneThought, _THOUGHT_CARD_DELAY_MS);
}

function _drainOneThought() {
  const t = _thoughtQueue.shift();
  if (!t) { _thoughtTimer = null; return; }
  if (t.aiIdx === Shell.currentAI) _prependThought(t);
  // Chip fires at the same moment the card renders (regardless of which AI)
  if (t.kind === 'bid' && t.charId != null) _flashCard(t.charId);
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
  const showHired  = t.kind === 'bid' && !t.failed && t.charId != null
    && _hiredMarks[t.aiIdx] && _hiredMarks[t.aiIdx].has(t.charId);
  const showFailed = t.kind === 'bid' && t.failed;
  const lineHtml = Shell.helpers.thoughtCardHtml(t.kind, t.title, t.body, {
    id: t.id ? 'thought-' + t.id : '',
    hired: showHired,
    failed: showFailed,
  });
  const wrap = document.createElement('div');
  wrap.innerHTML = lineHtml;
  const card = wrap.firstElementChild;
  if (!card) return;
  stream.insertBefore(card, stream.firstChild);
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

// Called by HiringTab._flyBidToPortrait / flushPlaceQueue when a bid chip starts
// flying. Renders the bid thought card immediately (no queue delay) so it syncs
// with the chip animation. Idempotent — skips if a card for this bid already exists.
function _bidChipFired(aiIdx, charId, amount, rationale) {
  while (_aiStreams.length <= aiIdx) _aiStreams.push([]);
  // Idempotent check: skip if this bid was already recorded
  const tId = 'bid-' + aiIdx + '-' + charId;
  if (_aiStreams[aiIdx].some(t => t.id === tId)) return;
  const c = Shell.charById.get(charId) || Shell.charById.get(Number(charId));
  if (!c) return;
  const esc = Shell.helpers.escapeHtml;
  const amountStr = amount != null ? ' · $' + Number(amount).toLocaleString() : '';
  const t = {
    aiIdx, kind: 'bid',
    title: 'Bid · ' + c.name + amountStr,
    body: esc(rationale || '—'),
    id: tId, charId,
  };
  _aiStreams[aiIdx].unshift(t);
  if (aiIdx === Shell.currentAI) _prependThought(t);
  _flashCard(charId);
}

// Called by HiringTab.handleAuctionResolved when a bid's result is known.
// Adds a ✗ Failed badge to the card. Won bids get their badge later via _markHired.
function _markBidResult(aiIdx, charId, result) {
  if (result !== 'failed') return;  // 'won' is handled by _markHired on crew_known
  const arr = _aiStreams[aiIdx] || [];
  for (const t of arr) {
    if (t.kind === 'bid' && t.charId === charId) { t.failed = true; break; }
  }
  if (aiIdx !== Shell.currentAI) return;
  const card = document.getElementById('thought-bid-' + aiIdx + '-' + charId);
  if (!card) return;
  if (!card.querySelector('.thought-failed-badge'))
    card.insertAdjacentHTML('beforeend', '<div class="thought-failed-badge">✗ Failed</div>');
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
    const showHired  = t.kind === 'bid' && !t.failed && t.charId != null
      && (t.hired || (hiredHere && hiredHere.has(t.charId)));
    const showFailed = t.kind === 'bid' && t.failed;
    const lineHtml = Shell.helpers.thoughtCardHtml(t.kind, t.title, t.body, {
      id: t.id ? 'thought-' + t.id : '',
      hired: showHired,
      failed: showFailed,
    });
    const wrap = document.createElement('div');
    wrap.innerHTML = lineHtml;
    const card = wrap.firstElementChild;
    if (card) {
      card.style.animation = 'none';
      stream.appendChild(card);
    }
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
