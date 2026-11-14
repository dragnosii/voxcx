/* VoxCX : noyau de l'interface (état, appels API, en-tête, thème, graphiques) */
'use strict';

const ICONES = {
  grille: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  couches: '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
  tendance: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
  liste: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
  cal: '<rect x="3" y="5" width="18" height="16" rx="2.5"/><path d="M8 3v4M16 3v4M3 10h18"/>',
  hotel: '<path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 9h2a2 2 0 0 1 2 2v10M2 21h20M8 8h4M8 12h4M8 16h4"/>',
  dl: '<path d="M12 4v11M7 11l5 5 5-5M4 20h16"/>',
  soleil: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  lune: '<path d="M21 13.5A8.5 8.5 0 1 1 10.5 3a7 7 0 0 0 10.5 10.5z"/>',
  alerte: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  etoile: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  envoyer: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  fermer: '<path d="M6 6l12 12M18 6L6 18"/>',
  logo: '<path d="M4 16l5-6 4 4 7-9"/>',
};
function ico(nom, t = 16, sw = 1.7) {
  return `<svg width="${t}" height="${t}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONES[nom]}</svg>`;
}

const RENDU = {};
const PAGES = [
  { id: 'accueil', titre: 'Accueil', icone: 'grille' },
  { id: 'themes', titre: 'Thèmes', icone: 'couches' },
  { id: 'assistant', titre: 'Pose ta question', icone: 'chat' },
  { id: 'predictif', titre: 'Prédictif', icone: 'tendance' },
  { id: 'plan', titre: "Plan d'actions", icone: 'liste' },
];

// ---------------------------------------------------------------- état
const E = {
  meta: null,
  filtres: { debut: null, fin: null, hotels: null, villes: null, commune: true, masquer: false },
  mode: 'local',
  action: '2026-07-16',
  chat: [],
};
function sauver() { try { localStorage.setItem('voxcx_etat', JSON.stringify({ filtres: E.filtres, mode: E.mode, action: E.action })); } catch (e) {} }
function restaurer() {
  try {
    const s = JSON.parse(localStorage.getItem('voxcx_etat') || 'null');
    if (s) { Object.assign(E.filtres, s.filtres || {}); E.mode = s.mode || 'local'; E.action = s.action || E.action; }
  } catch (e) {}
}

// ---------------------------------------------------------------- utilitaires
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
function esc(t) { return String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function fr(n, d = 0) { return n == null ? '–' : Number(n).toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d }).replace(/ /g, ' ').replace(/ /g, ' '); }
function signe(n, d = 2) { return (n >= 0 ? '+' : '−') + fr(Math.abs(n), d); }
function dateFr(iso) { return iso ? iso.split('-').reverse().join('/') : ''; }
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const moisCourt = m => MOIS[+m.slice(5, 7) - 1] + ' ' + m.slice(2, 4);
const MOIS_LONG = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const moisLong = m => MOIS_LONG[+m.slice(5, 7) - 1] + ' ' + m.slice(0, 4);
function nomAuteur(a) { return E.filtres.masquer ? 'Auteur masqué' : (a || 'Auteur inconnu'); }
function toast(msg) { const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 3200); }
function qs() {
  const f = E.filtres, p = new URLSearchParams();
  if (f.debut) p.set('debut', f.debut);
  if (f.fin) p.set('fin', f.fin);
  if (f.hotels && f.hotels.length) p.set('hotels', f.hotels.join('|'));
  const villes = E.villeSel || f.villes;
  if (villes && villes.length) p.set('villes', villes.join('|'));
  return p.toString();
}
async function api(url, corps) {
  const opts = corps === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps) };
  const r = await fetch(url, opts);
  const j = await r.json().catch(() => ({ erreur: 'Réponse illisible du serveur' }));
  if (!r.ok || j.erreur) throw new Error(j.erreur || 'Erreur du serveur');
  return j;
}
const chargement = (txt = 'Chargement…') => `<div class="chargement"><i></i><span>${esc(txt)}</span></div>`;
const messageErreur = e => `<div class="erreur">Impossible de charger les données. ${esc(e.message || e)}</div>`;

function delta(v, dec = 2, unite = '', inverse = false, libelle = '') {
  if (v == null) return '';
  const haut = v > 0.0001, bas = v < -0.0001, bon = inverse ? bas : haut;
  const cls = !haut && !bas ? 'fl' : bon ? 'up' : 'dn';
  const fleche = haut ? '<svg viewBox="0 0 12 12" fill="currentColor"><path d="M6 2l4.5 6.5h-9z"/></svg>' : bas ? '<svg viewBox="0 0 12 12" fill="currentColor"><path d="M6 10L1.5 3.5h9z"/></svg>' : '';
  return `<span class="dl ${cls}">${fleche}${signe(v, dec)}${unite}</span>${libelle ? `<span>${esc(libelle)}</span>` : ''}`;
}

// ---------------------------------------------------------------- animations
function formaterNb(v, d, avecSigne) { const s = fr(Math.abs(v), d); return avecSigne ? (v < 0 ? '−' : '+') + s : (v < 0 ? '−' : '') + s; }
function animerNombres(racine = document) {
  $$('[data-n]', racine).forEach(el => {
    const cible = parseFloat(el.dataset.n), d = parseInt(el.dataset.d || '0', 10), avecSigne = el.dataset.pre === '+';
    const t0 = performance.now(), duree = 700;
    const f = t => {
      const k = Math.min(1, (t - t0) / duree), v = cible * (1 - Math.pow(1 - k, 3));
      el.textContent = formaterNb(v, d, avecSigne);
      if (k < 1) requestAnimationFrame(f); else el.textContent = formaterNb(cible, d, avecSigne);
    };
    requestAnimationFrame(f);
  });
  $$('.meter i', racine).forEach(m => requestAnimationFrame(() => requestAnimationFrame(() => { m.style.width = m.dataset.w; })));
}
function cascade(racine) { $$('.card', racine).forEach((c, i) => { c.style.animationDelay = (i * 0.04) + 's'; }); }

// ---------------------------------------------------------------- graphiques
let _gid = 0;
function observer(el, dessiner) {
  let t = null, largeur = 0;
  const f = () => { const w = el.clientWidth; if (w && Math.abs(w - largeur) > 1) { largeur = w; dessiner(w); } };
  f();
  if (window.ResizeObserver) new ResizeObserver(() => { clearTimeout(t); t = setTimeout(f, 80); }).observe(el);
}
function sparkline(vals, w = 84, h = 28) {
  const v = vals.filter(x => x != null);
  if (v.length < 2) return '';
  const mn = Math.min(...v), mx = Math.max(...v), r = mx - mn || 1, n = vals.length;
  const pts = vals.map((x, i) => x == null ? null : [2 + i * (w - 4) / (n - 1), h - 3 - (x - mn) / r * (h - 6)]).filter(Boolean);
  const dernier = pts[pts.length - 1];
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline points="${pts.map(p => p.join(',')).join(' ')}" fill="none" style="stroke:var(--muted)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${dernier[0]}" cy="${dernier[1]}" r="2.4" style="fill:var(--accent)"/></svg>`;
}
/* Courbe en aires avec survol, repère d'action et moyennes avant / après */
function courbe(el, serie, action, aa) {
  if (!serie.length) { el.innerHTML = '<div class="vide">Pas assez de données</div>'; return; }
  const id = 'g' + (++_gid), H = 290, m = { l: 44, r: 14, t: 16, b: 28 }, inset = 26;
  const dessiner = W => {
    const vals = serie.map(s => s.note);
    let mn = Math.min(...vals, aa ? aa.avant : 9, aa ? aa.apres : 9), mx = Math.max(...vals, aa ? aa.avant : 0, aa ? aa.apres : 0);
    const marge = Math.max(0.04, (mx - mn) * 0.3); mn -= marge; mx += marge;
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    const x = i => m.l + inset + (serie.length === 1 ? (pw - 2 * inset) / 2 : i * (pw - 2 * inset) / (serie.length - 1));
    const y = v => m.t + ph - (v - mn) / (mx - mn) * ph;
    let grille = '';
    for (let k = 0; k <= 4; k++) { const v = mn + (mx - mn) * k / 4, yy = y(v); grille += `<line x1="${m.l}" y1="${yy}" x2="${W - m.r}" y2="${yy}" style="stroke:var(--grid)" stroke-dasharray="${k ? '3 4' : '0'}"/><text x="${m.l - 8}" y="${yy + 4}" text-anchor="end">${fr(v, 2)}</text>`; }
    const etiq = serie.map((s, i) => `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${moisCourt(s.mois)}</text>`).join('');
    const pts = serie.map((s, i) => [x(i), y(s.note)]);
    const ligne = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    const aire = ligne + ` L${pts[pts.length - 1][0].toFixed(1)} ${m.t + ph} L${pts[0][0].toFixed(1)} ${m.t + ph} Z`;
    let repere = '', moyennes = '', xa = null;
    const t0 = new Date(serie[0].mois + '-15'), t1 = new Date(serie[serie.length - 1].mois + '-15'), ta = new Date(action);
    if (serie.length > 1 && ta >= t0 && ta <= t1) {
      xa = x(0) + (ta - t0) / (t1 - t0) * (x(serie.length - 1) - x(0));
      repere = `<rect x="${xa}" y="${m.t}" width="${W - m.r - xa}" height="${ph}" style="fill:var(--accent);opacity:.045"/><line x1="${xa}" y1="${m.t}" x2="${xa}" y2="${m.t + ph}" style="stroke:var(--amber)" stroke-width="1.5" stroke-dasharray="5 4"/>
        <text x="${xa + 6}" y="${m.t + 11}" style="fill:var(--amber);font-weight:500">Action · ${dateFr(action).slice(0, 5)}</text>`;
      if (aa) {
        moyennes = `<line x1="${m.l + 6}" y1="${y(aa.avant)}" x2="${xa - 4}" y2="${y(aa.avant)}" style="stroke:var(--muted)" stroke-width="1.2" stroke-dasharray="2 3"/><text x="${m.l + 8}" y="${y(aa.avant) - 6}">moy. ${fr(aa.avant, 2)}</text>
          <line x1="${xa + 4}" y1="${y(aa.apres)}" x2="${W - m.r - 6}" y2="${y(aa.apres)}" style="stroke:var(--muted)" stroke-width="1.2" stroke-dasharray="2 3"/><text x="${W - m.r - 8}" y="${y(aa.apres) - 6}" text-anchor="end">moy. ${fr(aa.apres, 2)}</text>`;
      }
    }
    el.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Évolution mensuelle de la note moyenne">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--accent);stop-opacity:.26"/><stop offset="1" style="stop-color:var(--accent);stop-opacity:0"/></linearGradient></defs>
      ${grille}${etiq}${repere}<path d="${aire}" fill="url(#${id})"/><path d="${ligne}" fill="none" style="stroke:var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>${moyennes}
      <line id="${id}-v" y1="${m.t}" y2="${m.t + ph}" style="stroke:var(--border2)" stroke-width="1" opacity="0"/><circle id="${id}-c" r="4.5" style="fill:var(--surface);stroke:var(--accent)" stroke-width="2" opacity="0"/>
      <circle cx="${pts[pts.length - 1][0]}" cy="${pts[pts.length - 1][1]}" r="3.5" style="fill:var(--accent)"/>
      <rect id="${id}-r" x="${m.l}" y="${m.t}" width="${pw}" height="${ph}" fill="transparent"/></svg><div class="tip" id="${id}-t"></div>`;
    const svg = el.querySelector('svg'), tip = $('#' + id + '-t', el), v = $('#' + id + '-v', el), c = $('#' + id + '-c', el);
    $('#' + id + '-r', el).addEventListener('mousemove', e => {
      const bb = svg.getBoundingClientRect(), mx0 = e.clientX - bb.left;
      let k = 0, best = 1e9; pts.forEach((p, i) => { const dd = Math.abs(p[0] - mx0); if (dd < best) { best = dd; k = i; } });
      const s = serie[k]; v.setAttribute('x1', pts[k][0]); v.setAttribute('x2', pts[k][0]); v.setAttribute('opacity', 1);
      c.setAttribute('cx', pts[k][0]); c.setAttribute('cy', pts[k][1]); c.setAttribute('opacity', 1);
      tip.innerHTML = `<b>${esc(moisLong(s.mois))}</b><span>Note moyenne</span> <b style="display:inline">${fr(s.note, 2)}</b><br><span>${fr(s.n)} avis</span>`;
      tip.style.opacity = 1; tip.style.left = Math.min(W - 150, Math.max(0, pts[k][0] + 12)) + 'px'; tip.style.top = Math.max(0, pts[k][1] - 56) + 'px';
    });
    $('#' + id + '-r', el).addEventListener('mouseleave', () => { tip.style.opacity = 0; v.setAttribute('opacity', 0); c.setAttribute('opacity', 0); });
  };
  observer(el, dessiner);
}
/* Carte de chaleur : couleur = score de 0 à 10 */
function carteChaleur(mat) {
  const col = v => {
    if (v == null) return 'background:transparent;color:var(--muted)';
    const t = Math.max(0, Math.min(1, (v - 5.5) / 3.5)), a = 0.16 + Math.abs(t - 0.5) * 0.7;
    const rgb = t < 0.5 ? (t < 0.25 ? 'var(--h-bad)' : 'var(--h-mid)') : 'var(--h-good)';
    return `background:rgba(${rgb},${a.toFixed(2)});color:var(--text)`;
  };
  const cols = `grid-template-columns: minmax(150px, 1.3fr) repeat(${mat.hotels.length}, minmax(64px, 1fr))`;
  const tete = `<div></div>` + mat.hotels.map(h => `<div class="hh">${esc(h.replace('Kenzi ', ''))}</div>`).join('');
  const lignes = mat.aspects.map((a, i) => `<div class="hl">${esc(a)}</div>` + mat.valeurs[i].map(v => `<div class="hc" style="${col(v)}" title="${esc(a)} · ${v == null ? 'trop peu d\'avis' : fr(v, 1) + ' / 10'}">${v == null ? '–' : fr(v, 1)}</div>`).join('')).join('');
  return `<div class="heat" style="${cols}">${tete}${lignes}</div>`;
}

// ---------------------------------------------------------------- fenêtres
function ouvrirTiroir(titre, html) {
  fermerTiroir();
  const m = document.createElement('div'); m.className = 'modal'; m.id = 'tiroir';
  m.innerHTML = `<div class="drawer" role="dialog" aria-label="${esc(titre)}"><div class="top2"><h3>${esc(titre)}</h3><button class="ibtn" id="x-tiroir" aria-label="Fermer">${ico('fermer')}</button></div>${html}</div>`;
  m.addEventListener('click', e => { if (e.target === m) fermerTiroir(); });
  $('#portail').appendChild(m); $('#x-tiroir').onclick = fermerTiroir;
}
function fermerTiroir() { const t = $('#tiroir'); if (t) t.remove(); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') { fermerTiroir(); fermerPops(); } });

// ---------------------------------------------------------------- thème et mode IA
function appliquerTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('voxcx_theme', t); } catch (e) {}
  const b = $('#btn-theme'); if (b) { b.innerHTML = ico(t === 'dark' ? 'soleil' : 'lune'); b.title = t === 'dark' ? 'Passer en thème clair' : 'Passer en thème sombre'; b.setAttribute('aria-label', b.title); }
}
function themeActuel() { return document.documentElement.getAttribute('data-theme') || 'dark'; }
function majMode() {
  const dispo = E.meta && E.meta.en_ligne_disponible;
  if (E.mode === 'en ligne' && !dispo) E.mode = 'local';
  $$('#seg-mode button').forEach(b => { b.classList.toggle('on', b.dataset.m === E.mode); if (b.dataset.m === 'en ligne') { b.disabled = !dispo; b.title = dispo ? '' : "Aucune clé d'API : ajoutez ANTHROPIC_API_KEY dans app/.env"; } });
  $('#mode-note').textContent = E.mode === 'en ligne'
    ? 'Claude rédige les réponses. Bascule automatique en local si le réseau tombe.'
    : (dispo ? 'Gratuit, sans Internet.' : "Gratuit, sans Internet. Mode en ligne : ajoutez une clé d'API dans app/.env.");
}

// ---------------------------------------------------------------- en-tête et filtres
let surChangement = () => {};
function fermerPops() { $$('.pop').forEach(p => p.remove()); }
document.addEventListener('click', e => { if (!e.target.closest('.pop') && !e.target.closest('[data-pop]')) fermerPops(); });

function enteteHTML(titre, sous, avecFiltres = true) {
  const f = E.filtres, m = E.meta;
  const nbH = (f.hotels && f.hotels.length) || m.hotels.length;
  const th = themeActuel();
  return `<header class="top"><div><h1>${esc(titre)}</h1><p id="sous-titre">${esc(sous)}</p></div>
    <div class="tools" id="tools">
      ${avecFiltres ? `<button class="btn-s" data-pop="periode">${ico('cal')}<span class="num">${dateFr(f.debut)} – ${dateFr(f.fin)}</span></button>
      <button class="btn-s" data-pop="hotels">${ico('hotel')}<span>${nbH} hôtel${nbH > 1 ? 's' : ''}</span></button>` : ''}
      <button class="ibtn" id="btn-theme" title="Changer de thème" aria-label="Changer de thème">${ico(th === 'dark' ? 'soleil' : 'lune')}</button>
      ${avecFiltres ? `<a class="btn-s" href="/api/export.csv?${qs()}" download>${ico('dl')}<span>Exporter</span></a>` : ''}
    </div></header>`;
}
function brancherEntete() {
  $('#btn-theme').onclick = () => appliquerTheme(themeActuel() === 'dark' ? 'light' : 'dark');
  $$('[data-pop]').forEach(b => b.onclick = e => { e.stopPropagation(); const k = b.dataset.pop, deja = $('.pop[data-k="' + k + '"]'); fermerPops(); if (!deja) ouvrirPop(k, b); });
}
function ouvrirPop(k, bouton) {
  const f = E.filtres, m = E.meta, p = document.createElement('div');
  p.className = 'pop'; p.dataset.k = k; p.style.left = Math.max(0, bouton.offsetLeft) + 'px';
  if (k === 'periode') {
    p.innerHTML = `<h4>Période</h4><div class="two"><label>Du<input type="date" id="f-debut" value="${f.debut}" min="${m.date_min}" max="${m.date_max}"></label>
      <label>Au<input type="date" id="f-fin" value="${f.fin}" min="${m.date_min}" max="${m.date_max}"></label></div>
      <label><input type="checkbox" id="f-commune" ${f.commune ? 'checked' : ''}>Fenêtre commune (depuis le ${dateFr(m.fenetre_commune)})</label>
      <span class="note">Kenzi Solazur est limité à 1 300 avis et ne remonte qu'au ${dateFr(m.fenetre_commune)} : cette option compare tous les hôtels sur la même période.</span>
      <button class="btn" id="f-ok">Appliquer</button>`;
    bouton.parentElement.appendChild(p);
    $('#f-commune').onchange = e => { $('#f-debut').value = e.target.checked ? m.fenetre_commune : m.date_min; };
    $('#f-ok').onclick = () => {
      f.debut = $('#f-debut').value || m.date_min; f.fin = $('#f-fin').value || m.date_max; f.commune = $('#f-commune').checked;
      if (f.debut > f.fin) [f.debut, f.fin] = [f.fin, f.debut];
      sauver(); fermerPops(); surChangement();
    };
  } else {
    const villes = [...new Set(m.hotels.map(h => h.ville))];
    const coches = new Set(f.hotels && f.hotels.length ? f.hotels : m.hotels.map(h => h.hotel));
    p.innerHTML = `<h4>Hôtels</h4>${villes.map(v => `<div style="display:flex;flex-direction:column;gap:6px"><span class="note" style="font-weight:600">${esc(v)}</span>${m.hotels.filter(h => h.ville === v).map(h => `<label><input type="checkbox" data-h="${esc(h.hotel)}" ${coches.has(h.hotel) ? 'checked' : ''}>${esc(h.hotel)}</label>`).join('')}</div>`).join('')}
      <h4>Confidentialité</h4><label><input type="checkbox" id="f-masquer" ${f.masquer ? 'checked' : ''}>Masquer les noms des auteurs d'avis</label>`;
    bouton.parentElement.appendChild(p);
    const maj = () => {
      const sel = $$('[data-h]', p).filter(c => c.checked).map(c => c.dataset.h);
      f.hotels = sel.length && sel.length < m.hotels.length ? sel : null; sauver(); clearTimeout(maj.t); maj.t = setTimeout(() => { fermerPops(); surChangement(); }, 350);
    };
    $$('[data-h]', p).forEach(c => c.onchange = maj);
    $('#f-masquer').onchange = e => { f.masquer = e.target.checked; sauver(); surChangement(); };
  }
}

// ---------------------------------------------------------------- navigation
function pageCourante() { const h = (location.hash || '#/accueil').replace('#/', ''); return PAGES.find(p => p.id === h) || PAGES[0]; }
function naviguer() {
  const p = pageCourante();
  $('#nav').innerHTML = '<div class="lab">Analyse</div>' + PAGES.map(x => `<a href="#/${x.id}" class="${x.id === p.id ? 'on' : ''}">${ico(x.icone)}<span>${esc(x.titre)}</span></a>`).join('');
  fermerPops(); fermerTiroir();
  if (p.id !== 'themes') E.villeSel = null;
  window.scrollTo({ top: 0 });
  surChangement = () => RENDU[p.id]();
  RENDU[p.id]();
}

async function demarrer() {
  restaurer();
  try { E.meta = await api('/api/meta'); } catch (e) { $('#main').innerHTML = messageErreur(e); return; }
  const m = E.meta, f = E.filtres;
  if (!f.debut) f.debut = f.commune ? m.fenetre_commune : m.date_min;
  if (!f.fin) f.fin = m.date_max;
  $$('#seg-mode button').forEach(b => b.onclick = () => { E.mode = b.dataset.m; sauver(); majMode(); });
  majMode();
  window.addEventListener('hashchange', naviguer);
  naviguer();
}
window.addEventListener('DOMContentLoaded', () => setTimeout(demarrer, 0));
