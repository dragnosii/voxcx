/* VoxCX 2 : interface. Tout texte venant du serveur passe par esc() avant d'être inséré dans la page. */
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fr = (x, d = 2) => (x == null ? "–" : Number(x).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }));
const reduit = matchMedia("(prefers-reduced-motion: reduce)").matches;
const etat = { moi: null, eid: null, vue: "matin", cache: {} };

function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("on"); clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove("on"), 2800); }

async function api(chemin, corps) {
  const opts = { credentials: "same-origin", headers: {} };
  if (corps !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    if (etat.moi && etat.moi.csrf) opts.headers["X-CSRF"] = etat.moi.csrf;
    opts.body = JSON.stringify(corps);
  }
  let r;
  try { r = await fetch(chemin, opts); } catch (e) { throw new Error("Le serveur ne répond pas. Vérifiez qu'il est lancé."); }
  let d = {};
  try { d = await r.json(); } catch (e) { /* réponse vide */ }
  if (r.status === 401 && etat.moi && etat.moi.connecte) { await charger(); throw new Error("Session expirée. Reconnectez-vous."); }
  if (!r.ok) throw new Error(d.erreur || "Une erreur est survenue.");
  return d;
}

const I = {
  matin: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  avis: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  rattrapage: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
  collecte: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 17h4v4"/>',
  analyse: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  actions: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
  abonnement: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
  admin: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  etab: '<path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6"/>',
};
const ico = (n) => `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${I[n]}</svg>`;
const etoiles = (n) => `<span class="etoiles ${n >= 4 ? "bon" : ""}" aria-label="${n} sur 5">${"★".repeat(n)}<span class="off">${"★".repeat(5 - n)}</span></span>`;
const date = (s) => (s ? s.slice(8, 10) + "/" + s.slice(5, 7) + "/" + s.slice(0, 4) : "");

/* ------------------------------------------------------------ démarrage */
async function charger() {
  etat.moi = await api("/api/moi");
  const etabs = etat.moi.etablissements || [];
  let memo = null;
  try { memo = localStorage.getItem("voxcx_eid"); } catch (e) { /* stockage indisponible */ }
  etat.eid = etabs.find((e) => e.id === memo) ? memo : etabs[0]?.id || null;
  const h = location.hash.slice(1);
  etat.vue = VUES[h] ? h : "matin";
  rendre();
}
addEventListener("hashchange", () => { const h = location.hash.slice(1); if (VUES[h] && etat.moi?.connecte) { etat.vue = h; rendre(); } });

function etab() { return (etat.moi.etablissements || []).find((e) => e.id === etat.eid); }

/* ------------------------------------------------------------ page publique */
function pagePublique(mode = "inscription") {
  $("#app").innerHTML = `
  <div class="public">
    <header><div class="marque">VoxCX <small>2.0</small></div><button class="btn" data-a="aller-connexion">Se connecter</button></header>
    <section class="heros">
      <div>
        <h1 id="titre-heros">Vos clients parlent. Répondez, rattrapez, progressez.</h1>
        <p class="accroche">VoxCX lit tous les avis de votre hôtel, riad ou restaurant, prépare vos réponses dans la langue du client et vous alerte quand un client est mécontent, avant qu'il ne l'écrive sur Google.</p>
      </div>
      <div class="carte" id="bloc-compte">
        <div class="onglets bascule" role="group" aria-label="Choisir">
          <button data-a="onglet" data-o="inscription" aria-pressed="${mode === "inscription"}">Essai gratuit 14 jours</button>
          <button data-a="onglet" data-o="connexion" aria-pressed="${mode === "connexion"}">J'ai un compte</button>
        </div>
        <form class="form" id="form-compte" novalidate>
          ${mode === "inscription" ? `<label class="champ">Votre nom<input type="text" id="f-nom" autocomplete="name" required maxlength="80"></label>` : ""}
          <label class="champ">E-mail<input type="email" id="f-email" autocomplete="email" required maxlength="190"></label>
          <label class="champ">Mot de passe${mode === "inscription" ? " (10 caractères minimum)" : ""}<input type="password" id="f-mot" autocomplete="${mode === "inscription" ? "new-password" : "current-password"}" required minlength="${mode === "inscription" ? 10 : 1}"></label>
          <p class="erreur" id="f-erreur" role="alert"></p>
          <button class="btn plein" type="submit">${mode === "inscription" ? "Créer mon compte" : "Me connecter"}</button>
          ${mode === "inscription" ? `<p class="discret">Sans carte bancaire. Vos données restent les vôtres.</p>` : ""}
        </form>
      </div>
    </section>
    <section class="atouts">
      <div class="carte"><h3>Tout votre historique, analysé</h3><p class="second">Connectez votre fiche : tous vos anciens avis sont importés et lus en quelques minutes.</p></div>
      <div class="carte"><h3>Les mécontents rattrapés</h3><p class="second">Un QR code sur la table. Une note basse ? Vous êtes alerté et vous rappelez le client le jour même.</p></div>
      <div class="carte"><h3>Des réponses en 1 clic</h3><p class="second">Français, anglais, espagnol, arabe : la réponse est prête, vous la relisez et vous publiez.</p></div>
    </section>
    <h2 style="margin-bottom:16px">Les offres</h2>
    <div class="offres" id="offres-publiques"><p class="chargement">Chargement des offres…</p></div>
  </div>`;
  animerTitre($("#titre-heros"));
  api("/api/offres").then((d) => { $("#offres-publiques").innerHTML = cartesOffres(d.offres, null, false); }).catch(() => {});
}

function cartesOffres(offres, actuelle, achetable) {
  return ["essai", "essentiel", "pro"].map((k) => {
    const o = offres[k];
    return `<div class="offre ${k === "essentiel" ? "vedette" : ""}">
      <h3>${esc(o.nom)}</h3>
      <div class="prix num">${o.prix ? fr(o.prix / 100, 0) + " DH" : "Gratuit"} <small>${o.prix ? "par mois" : "14 jours"}</small></div>
      <ul>${o.atouts.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
      ${achetable && k !== "essai" ? `<button class="btn ${k === actuelle ? "" : "plein"}" data-a="payer" data-o="${k}" ${k === actuelle ? "disabled" : ""}>${k === actuelle ? "Votre offre actuelle" : "Choisir " + esc(o.nom)}</button>` : ""}
    </div>`;
  }).join("");
}

function animerTitre(el) {
  if (!el || reduit) return;
  const t = el.textContent; el.setAttribute("aria-label", t); el.textContent = "";
  t.split(" ").forEach((m, i) => { if (i) el.appendChild(document.createTextNode(" ")); const s = document.createElement("span"); s.className = "mot"; s.setAttribute("aria-hidden", "true");
    for (const c of m) { const l = document.createElement("span"); l.className = "l"; l.textContent = c; s.appendChild(l); } el.appendChild(s); });
  const ls = [...el.querySelectorAll(".l")];
  const fixer = () => { ls.forEach((l) => { l.style.width = ""; l.style.fontVariationSettings = '"wght" 600'; });
    const fs = parseFloat(getComputedStyle(el).fontSize); ls.forEach((l) => { l.style.width = l.getBoundingClientRect().width / fs + "em"; });
    ls.forEach((l) => { l.style.fontVariationSettings = '"wght" 450'; }); };
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(fixer);
  const bouge = (e) => { if (!el.isConnected) { removeEventListener("pointermove", bouge); return; }
    for (const l of ls) { const r = l.getBoundingClientRect(); const d = Math.hypot(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2)); const k = Math.max(0, 1 - d / 240); l.style.fontVariationSettings = `"wght" ${Math.round(450 + k * k * 330)}`; } };
  addEventListener("pointermove", bouge, { passive: true });
}

/* ------------------------------------------------------------ coquille connectée */
const VUES = {
  matin: { nom: "Ce matin", ico: "matin", f: vueMatin },
  avis: { nom: "Répondre aux avis", ico: "avis", f: vueAvis },
  rattrapage: { nom: "Clients à rappeler", ico: "rattrapage", f: vueRattrapage },
  collecte: { nom: "Collecte et fiche", ico: "collecte", f: vueCollecte },
  analyse: { nom: "Poser une question", ico: "analyse", f: vueAnalyse },
  actions: { nom: "Actions", ico: "actions", f: vueActions },
  abonnement: { nom: "Abonnement", ico: "abonnement", f: vueAbonnement },
  admin: { nom: "Administration", ico: "admin", f: vueAdmin, admin: true },
};

function rendre() {
  if (!etat.moi.connecte) return pagePublique();
  const m = etat.moi;
  const etabs = m.etablissements || [];
  const nav = Object.entries(VUES).filter(([, v]) => !v.admin || m.utilisateur.role === "admin")
    .map(([k, v]) => `<button data-a="vue" data-v="${k}" ${etat.vue === k ? 'aria-current="page"' : ""}>${ico(v.ico)}<span>${v.nom}</span><span class="pastille" id="p-${k}" hidden></span></button>`).join("");
  $("#app").innerHTML = `
  <div class="mobile-barre"><div class="marque">VoxCX <small>2.0</small></div><button class="btn" data-a="menu" aria-label="Ouvrir le menu">Menu</button></div>
  <div class="coquille">
    <aside class="rail" id="rail">
      <div class="marque">VoxCX <small>2.0</small></div>
      <label class="discret">Établissement
        <select id="choix-etab">${etabs.map((e) => `<option value="${esc(e.id)}" ${e.id === etat.eid ? "selected" : ""}>${esc(e.nom)}</option>`).join("")}<option value="__nouveau">+ Ajouter un établissement</option></select>
      </label>
      <nav aria-label="Menu principal">${nav}</nav>
      <div class="bas">
        <span class="discret">${esc(m.utilisateur.nom)} · ${esc(m.abonnement?.nom || "")}</span>
        <span class="discret">IA : ${m.ia_en_ligne ? "en ligne (" + esc(m.modele_ia || "") + ")" : "mode local gratuit"}</span>
        <button class="btn" data-a="deconnexion">Se déconnecter</button>
      </div>
    </aside>
    <main class="contenu" id="contenu"></main>
  </div>`;
  if (!etabs.length && etat.vue !== "abonnement" && etat.vue !== "admin") return vueNouvelEtab();
  VUES[etat.vue].f();
  if (etat.eid) pastilles();
}

async function pastilles() {
  try {
    const t = etat.cache.tableau || (await api(`/api/etablissements/${etat.eid}/tableau`));
    etat.cache.tableau = t;
    const p = (id, n) => { const e = $("#p-" + id); if (e) { e.hidden = !n; e.textContent = n; } };
    p("avis", t.a_repondre); p("rattrapage", t.cas_ouverts);
  } catch (e) { /* silencieux */ }
}

function changerVue(v) { etat.vue = v; etat.cache = {}; try { history.replaceState(null, "", "#" + v); } catch (e) { /* */ } rendre(); scrollTo(0, 0); }

/* ------------------------------------------------------------ établissement */
function formEtab(e = {}) {
  const types = etat.moi.types || [];
  return `<form class="form" id="form-etab" novalidate>
    <label class="champ">Nom de l'établissement<input type="text" id="e-nom" maxlength="80" required value="${esc(e.nom || "")}" placeholder="Riad Yasmine"></label>
    <div class="grille2">
      <label class="champ">Ville<input type="text" id="e-ville" maxlength="60" required value="${esc(e.ville || "")}" placeholder="Marrakech"></label>
      <label class="champ">Type<select id="e-type">${types.map((t) => `<option ${t === e.type ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
    </div>
    <label class="champ">Lien pour laisser un avis Google (facultatif)<input type="url" id="e-lien" maxlength="300" value="${esc(e.lien_avis || "")}" placeholder="https://g.page/r/…/review"></label>
    <p class="discret">Les clients contents seront invités à publier leur avis avec ce lien.</p>
    <p class="erreur" id="e-erreur" role="alert"></p>
    <button class="btn plein" type="submit">${e.id ? "Enregistrer" : "Créer l'établissement"}</button>
  </form>`;
}

function vueNouvelEtab() {
  $("#contenu").innerHTML = `<div class="entete"><div><h1>Bienvenue ${esc(etat.moi.utilisateur.nom)}</h1><p>Commencez par ajouter votre établissement. Ensuite, connectez sa fiche pour importer tous ses avis.</p></div></div>
  <div class="carte" style="max-width:620px">${formEtab()}</div>`;
}

/* ------------------------------------------------------------ Ce matin */
async function vueMatin() {
  const c = $("#contenu");
  c.innerHTML = `<p class="chargement">Lecture de vos avis…</p>`;
  const t = await api(`/api/etablissements/${etat.eid}/tableau`).catch((e) => ({ erreur: e.message }));
  etat.cache.tableau = t;
  const e = etab();
  if (t.erreur) { c.innerHTML = `<div class="vide"><p>${esc(t.erreur)}</p></div>`; return; }
  if (t.vide) {
    c.innerHTML = `<div class="entete"><div><h1>${esc(e.nom)}</h1><p>Aucun avis pour l'instant.</p></div></div>
    <div class="vide"><h2>Connectez votre fiche pour démarrer</h2><p>Tous vos anciens avis seront importés et analysés. Vous pouvez aussi partager votre enquête client.</p>
    <button class="btn plein" data-a="vue" data-v="collecte">Connecter ma fiche</button></div>`;
    return;
  }
  const k = t.kpi, dn = k.note30 != null && k.note30_avant != null ? k.note30 - k.note30_avant : null;
  c.innerHTML = `
  <div class="entete"><div><h1>${esc(e.nom)}, ce matin</h1><p>${k.avis} avis analysés, du ${esc(t.debut)} au ${esc(t.fin)}. Voici ce qui demande votre attention.</p></div></div>
  <ol class="decisions">${t.decisions.length ? t.decisions.map((d) => `
    <li class="decision ${esc(d.niveau)}"><span class="bande"></span>
      <div><h3>${esc(d.titre)}</h3><p>${esc(d.texte)}</p></div>
      <button class="btn ${d.niveau === "urgent" ? "plein" : ""}" data-a="vue" data-v="${esc(d.vers)}">${d.vers === "rattrapage" ? "Voir les clients" : d.vers === "avis" ? "Répondre" : "Analyser"}</button></li>`).join("")
    : `<li class="vide"><p>Rien d'urgent aujourd'hui. Vos clients sont bien suivis.</p></li>`}</ol>
  <div class="chiffres">
    <div><b class="num">${fr(k.note)}</b><span>Note moyenne sur 5</span>${dn != null ? `<em class="${dn >= 0 ? "hausse" : "baisse"}">${dn >= 0 ? "+" : ""}${fr(dn)} sur 30 jours</em>` : ""}</div>
    <div><b class="num">${fr(k.mecontents_pct, 1)} %</b><span>Clients à 1 ou 2 étoiles</span></div>
    <div><b class="num">${k.delai_h == null ? "–" : k.delai_h + " h"}</b><span>Délai de réponse médian</span>${k.delai_h != null && k.delai_h > 48 ? `<em class="baisse">Visez moins de 24 h</em>` : ""}</div>
    <div><b class="num">${fr(k.taux_reponse, 0)} %</b><span>Avis qui ont une réponse</span></div>
  </div>
  <div class="pouls" id="pouls" style="margin-top:24px">
    <canvas id="grille" aria-hidden="true"></canvas>
    <div class="graphe"><div class="tete"><h2>Note moyenne, semaine par semaine</h2><span><i></i>Clients à 1 ou 2 étoiles</span></div>
      <svg id="courbe" role="img" aria-label="Note moyenne par semaine. Survolez une semaine pour voir le détail."></svg></div>
    <aside class="detail" id="detail" aria-live="polite"></aside>
  </div>
  <div class="carte" style="margin-top:24px"><h2 style="margin-bottom:12px">De quoi se plaignent vos clients ?</h2>
    <div class="tableau-defile"><table class="liste"><thead><tr><th>Sujet</th><th>Phrases négatives (total)</th><th>4 dernières semaines</th><th>4 semaines d'avant</th></tr></thead>
    <tbody>${t.sujets.map((s) => `<tr><td>${esc(s.sujet)}</td><td><div class="rangee"><span class="num">${s.total}</span><div class="barre-mini" style="flex:1"><i style="width:${Math.round(s.total / t.sujets[0].total * 100)}%"></i></div></div></td>
      <td class="num ${s.recents > s.avant ? "baisse" : ""}">${s.recents}</td><td class="num">${s.avant}</td></tr>`).join("")}</tbody></table></div></div>`;
  if (t.pouls.length) pouls(t.pouls, k.note);
}

function pouls(P, moy) {
  const svg = $("#courbe"), NS = "http://www.w3.org/2000/svg";
  let selI = P.reduce((m, x, i) => (x.note < P[m].note ? i : m), 0);
  const el = (t, a, p) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); (p || svg).appendChild(e); return e; };
  const detail = (i) => { const p = P[i], dl = p.note - moy;
    $("#detail").innerHTML = `<div class="discret">Semaine du ${esc(p.du)}</div>
      <div class="gros"><b class="num">${fr(p.note)}</b> <span class="${dl < 0 ? "baisse" : "hausse"}">${dl < 0 ? "" : "+"}${fr(dl)} par rapport à la moyenne</span></div>
      <div class="ligne-info"><span>Avis reçus</span><b class="num">${p.n}</b></div>
      <div class="ligne-info"><span>Clients à 1 ou 2 étoiles</span><b class="num">${p.ko}</b></div>
      <div class="ligne-info"><span>Sujet n°1 des plaintes</span><b>${esc(p.sujet || "aucun")}</b></div>
      ${p.citation ? `<blockquote>« ${esc(p.citation)} »</blockquote>` : ""}`; };
  const dessiner = () => {
    svg.innerHTML = ""; const W = svg.clientWidth, H = svg.clientHeight; if (!W) return;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const g = { l: 40, r: 14, t: 16, hb: 54 }, hL = H - g.t - g.hb - 46;
    const notes = P.map((p) => p.note), yMin = Math.min(4.2, Math.floor(Math.min(...notes) * 10) / 10 - 0.1), yMax = 5, maxKo = Math.max(1, ...P.map((p) => p.ko));
    const x = (i) => g.l + (W - g.l - g.r) * (P.length > 1 ? i / (P.length - 1) : 0.5), y = (v) => g.t + hL * (1 - (v - yMin) / (yMax - yMin)), yb0 = H - 20;
    const ax = el("g", { class: "axe" });
    for (let v = Math.ceil(yMin * 5) / 5; v <= 5.001; v += 0.2) { el("line", { x1: g.l, x2: W - g.r, y1: y(v), y2: y(v), "stroke-opacity": .7 }, ax); el("text", { x: g.l - 8, y: y(v) + 4, "text-anchor": "end" }, ax).textContent = fr(v, 1); }
    el("line", { x1: g.l, x2: W - g.r, y1: yb0, y2: yb0 }, ax);
    const pas = W < 520 ? 6 : 3;
    P.forEach((p, i) => { if (i % pas === 0) el("text", { x: x(i), y: H - 2, "text-anchor": i === 0 ? "start" : "middle" }, ax).textContent = p.du; });
    el("text", { x: g.l - 8, y: yb0 - g.hb + 10, "text-anchor": "end" }, ax).textContent = maxKo;
    if (moy >= yMin) { el("line", { class: "ref", x1: g.l, x2: W - g.r, y1: y(moy), y2: y(moy) }); el("text", { x: g.l + 6, y: y(moy) + 16, fill: "currentColor", "font-size": 12, opacity: .7 }).textContent = "moyenne " + fr(moy); }
    const d = "M" + P.map((p, i) => `${x(i)},${y(p.note)}`).join(" L");
    const ligne = el("path", { class: "ligne", d });
    if (!reduit && !dessiner.fait) { const L = ligne.getTotalLength(); ligne.style.setProperty("--l", L); ligne.classList.add("trace"); dessiner.fait = true; }
    const bw = Math.max(4, (W - g.l - g.r) / P.length * .42);
    P.forEach((p, i) => { const h = Math.max(2, p.ko / maxKo * g.hb); el("rect", { class: "ko", x: x(i) - bw / 2, y: yb0 - h, width: bw, height: h, rx: 2, opacity: i === selI ? 1 : .55 }); });
    const vise = el("line", { class: "vise", x1: x(selI), x2: x(selI), y1: g.t, y2: yb0 }), pt = el("circle", { class: "pt", cx: x(selI), cy: y(P[selI].note), r: 6 });
    const zone = el("rect", { x: 0, y: 0, width: W, height: H, fill: "transparent" });
    const placer = (i) => { detail(i); vise.setAttribute("x1", x(i)); vise.setAttribute("x2", x(i)); pt.setAttribute("cx", x(i)); pt.setAttribute("cy", y(P[i].note));
      svg.querySelectorAll("rect.ko").forEach((b, j) => b.setAttribute("opacity", j === i ? 1 : .55)); };
    const indice = (cx) => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(P.length - 1, Math.round((cx - r.left - g.l) / (W - g.l - g.r) * (P.length - 1)))); };
    zone.addEventListener("pointermove", (e) => placer(indice(e.clientX)));
    zone.addEventListener("click", (e) => { selI = indice(e.clientX); placer(selI); });
    zone.addEventListener("pointerleave", () => placer(selI));
    placer(selI);
  };
  dessiner();
  grille();
  const r = () => { if ($("#courbe")) { dessiner(); grille(); } else removeEventListener("resize", r); };
  addEventListener("resize", r);
}

function grille() {
  const gc = $("#grille"), pouls = $("#pouls"); if (!gc) return;
  const gx = gc.getContext("2d"); let gm = { x: -999, y: -999 }, anim = null;
  const css = getComputedStyle(document.documentElement), neon = css.getPropertyValue("--neon").trim(), sourd = css.getPropertyValue("--sourdine").trim();
  const peindre = () => { const r = gc.getBoundingClientRect(), dp = Math.min(2, devicePixelRatio || 1);
    gc.width = Math.round(r.width * dp); gc.height = Math.round(r.height * dp); gx.setTransform(dp, 0, 0, dp, 0, 0);
    for (let yy = 11; yy < r.height; yy += 22) for (let xx = 11; xx < r.width; xx += 22) {
      const dx = xx - gm.x, dy = yy - gm.y, d = Math.hypot(dx, dy), k = Math.max(0, 1 - d / 150);
      gx.globalAlpha = .1 + k * .7; gx.fillStyle = k > .05 ? neon : sourd; gx.beginPath();
      gx.arc(xx + (d ? dx / d * k * k * 10 : 0), yy + (d ? dy / d * k * k * 10 : 0), .9 + k * 1.4, 0, 6.283); gx.fill(); }
    anim = null; };
  if (!reduit) { pouls.addEventListener("pointermove", (e) => { const r = gc.getBoundingClientRect(); gm = { x: e.clientX - r.left, y: e.clientY - r.top }; if (!anim) anim = requestAnimationFrame(peindre); });
    pouls.addEventListener("pointerleave", () => { gm = { x: -999, y: -999 }; if (!anim) anim = requestAnimationFrame(peindre); }); }
  peindre();
}

/* ------------------------------------------------------------ Répondre aux avis */
async function vueAvis() {
  const c = $("#contenu");
  c.innerHTML = `<div class="entete"><div><h1>Répondre aux avis</h1><p>Les avis des ${90} derniers jours sans réponse, les plus graves d'abord. L'IA prépare un brouillon dans la langue du client : vous relisez, puis vous publiez.</p></div></div><div id="z-avis"><p class="chargement">Chargement…</p></div>`;
  const d = await api(`/api/etablissements/${etat.eid}/reponses`).catch((e) => ({ erreur: e.message }));
  if (d.erreur) { $("#z-avis").innerHTML = `<div class="vide">${esc(d.erreur)}</div>`; return; }
  etat.cache.avis = d.avis;
  if (!d.avis.length) { $("#z-avis").innerHTML = `<div class="vide"><h2>Tout est à jour</h2><p>Aucun avis récent n'attend de réponse. Les nouveaux avis arriveront ici automatiquement.</p></div>`; return; }
  $("#z-avis").innerHTML = `<div class="boite"><div class="recus" id="recus" role="listbox" aria-label="Avis à traiter"></div><article class="lecteur" id="lecteur"></article></div>`;
  etat.cache.sel = 0; listeAvis(); lecteur();
}
function listeAvis() {
  $("#recus").innerHTML = etat.cache.avis.map((a, i) => `<button class="recu" role="option" aria-selected="${i === etat.cache.sel}" data-a="choisir-avis" data-i="${i}">
    <span class="l1"><b>${esc(a.auteur)}</b><span>${date(a.date)}</span></span>
    <span class="l1">${etoiles(a.note)}<span>${esc((a.langue || "").toUpperCase())}${a.statut === "brouillon" ? " · brouillon prêt" : ""}</span></span>
    <span class="extrait">${esc(a.texte_fr || a.texte)}</span></button>`).join("");
}
function lecteur() {
  const a = etat.cache.avis[etat.cache.sel]; if (!a) return;
  const neg = JSON.parse(a.aspects_neg || "[]"), trad = a.texte_fr && a.texte_fr !== a.texte;
  $("#lecteur").innerHTML = `
    <div class="rangee" style="justify-content:space-between"><div><b>${esc(a.auteur)}</b> <span class="discret">· ${date(a.date)}</span></div>${etoiles(a.note)}</div>
    ${trad ? `<div class="bascule" role="group" aria-label="Langue"><button data-a="langue" data-l="o" aria-pressed="${!etat.cache.fr}">Original</button><button data-a="langue" data-l="f" aria-pressed="${!!etat.cache.fr}">Français</button></div>` : ""}
    <p class="texte">${esc(etat.cache.fr && trad ? a.texte_fr : a.texte)}</p>
    ${neg.length ? `<div class="rangee">${neg.map((s) => `<span class="etiq ko">${esc(s)}</span>`).join("")}</div>` : ""}
    <div class="rangee" style="justify-content:space-between;border-top:1px solid var(--trait);padding-top:14px">
      <h3>Votre réponse</h3>
      <div class="bascule" role="group" aria-label="Ton"><button data-a="ton" data-t="formel" aria-pressed="${etat.cache.ton !== "chaleureux"}">Formel</button><button data-a="ton" data-t="chaleureux" aria-pressed="${etat.cache.ton === "chaleureux"}">Chaleureux</button></div>
    </div>
    <label class="champ" for="reponse">Relisez et modifiez avant de publier</label>
    <textarea id="reponse" maxlength="3000" placeholder="Cliquez sur « Préparer la réponse » : le brouillon s'écrit ici.">${esc(a.brouillon || "")}</textarea>
    <div class="rangee">
      <button class="btn" data-a="brouillon">${a.brouillon ? "Refaire le brouillon" : "Préparer la réponse"}</button>
      <button class="btn plein" data-a="publier">Valider et publier</button>
      <button class="btn" data-a="ignorer">Ne pas répondre</button>
      <span class="discret" id="mode-ia"></span>
    </div>`;
}
async function brouillon() {
  const a = etat.cache.avis[etat.cache.sel], b = $('[data-a="brouillon"]'); b.disabled = true; b.textContent = "Rédaction…";
  try {
    const d = await api(`/api/avis/${a.id}/brouillon`, { ton: etat.cache.ton || "formel" });
    a.brouillon = d.texte; a.statut = "brouillon"; listeAvis(); lecteur();
    $("#mode-ia").textContent = d.mode === "en ligne" ? "Rédigé par l'IA en ligne" : "Réponse type (mode local)";
    const ta = $("#reponse");
    if (!reduit) { let i = 0; ta.value = ""; ta.classList.add("tape"); const it = setInterval(() => { i += 5; ta.value = d.texte.slice(0, i); if (i >= d.texte.length) { clearInterval(it); ta.classList.remove("tape"); } }, 12); }
  } catch (e) { toast(e.message); b.disabled = false; b.textContent = "Préparer la réponse"; }
}

/* ------------------------------------------------------------ Rattrapage */
async function vueRattrapage() {
  const c = $("#contenu");
  c.innerHTML = `<div class="entete"><div><h1>Clients à rappeler</h1><p>Ces clients ont donné une note de 3 ou moins dans votre enquête. Rappelez-les aujourd'hui : un client rattrapé publie rarement un avis négatif.</p></div></div><div id="z-cas"><p class="chargement">Chargement…</p></div>`;
  const d = await api(`/api/etablissements/${etat.eid}/rattrapage`).catch((e) => ({ erreur: e.message }));
  if (d.erreur) { $("#z-cas").innerHTML = `<div class="vide">${esc(d.erreur)}</div>`; return; }
  const q = d.enquetes;
  const resume = `<div class="chiffres" style="margin:0 0 22px"><div><b class="num">${q.n || 0}</b><span>Enquêtes reçues</span></div><div><b class="num">${q.m ? fr(q.m, 1) : "–"}</b><span>Note moyenne</span></div>
    <div><b class="num">${q.c || 0}</b><span>Clients contents invités sur Google</span></div><div><b class="num">${d.cas.filter((x) => x.statut === "rattrape").length}</b><span>Clients rattrapés</span></div></div>`;
  if (!d.cas.length) { $("#z-cas").innerHTML = resume + `<div class="vide"><h2>Aucun client à rappeler</h2><p>Partagez votre enquête (QR code ou WhatsApp) : les mécontents apparaîtront ici.</p><button class="btn plein" data-a="vue" data-v="collecte">Partager l'enquête</button></div>`; return; }
  const libelle = { ouvert: "À rappeler", rappele: "Rappelé", rattrape: "Rattrapé", perdu: "Perdu" };
  $("#z-cas").innerHTML = resume + `<div style="display:grid;gap:14px">${d.cas.map((x) => `
    <div class="carte cas">
      <div style="display:grid;gap:10px">
        <div class="rangee" style="justify-content:space-between"><span class="etiq ${x.statut === "ouvert" ? "ko" : x.statut === "rattrape" ? "ok" : ""}">${libelle[x.statut]}</span><span class="discret">${date(x.cree_le)}</span></div>
        <div>${etoiles(x.note)}</div>
        <p class="texte">${x.commentaire ? "« " + esc(x.commentaire) + " »" : '<span class="discret">Pas de commentaire.</span>'}</p>
        <p class="discret">Contact : ${x.contact ? esc(x.contact) : "le client n'a pas laissé de contact"}</p>
        <div class="rangee">${x.statut !== "rattrape" ? `<button class="btn plein" data-a="cas" data-id="${esc(x.id)}" data-s="rattrape">Client rattrapé</button>` : ""}
          ${x.statut === "ouvert" ? `<button class="btn" data-a="cas" data-id="${esc(x.id)}" data-s="rappele">J'ai appelé</button>` : ""}
          ${x.statut !== "perdu" && x.statut !== "rattrape" ? `<button class="btn" data-a="cas" data-id="${esc(x.id)}" data-s="perdu">Injoignable</button>` : ""}</div>
      </div>
      <div><h3 style="margin-bottom:8px">Que lui dire</h3><div class="conseil">${esc(x.suggestion)}</div></div>
    </div>`).join("")}</div>`;
}

/* ------------------------------------------------------------ Collecte */
async function vueCollecte() {
  const e = etab(), c = $("#contenu"), lien = `${location.origin}/e/${e.jeton_enquete}`;
  const msg = `Merci pour votre visite chez ${e.nom} ! Votre avis nous aide à nous améliorer (1 minute) : ${lien}`;
  c.innerHTML = `<div class="entete"><div><h1>Collecte et fiche</h1><p>Deux façons de recevoir l'avis de vos clients : importer votre fiche existante, et partager votre enquête après chaque visite.</p></div></div>
  <div class="grille2">
    <div class="carte" style="display:grid;gap:14px">
      <h2>1. Connecter votre fiche d'avis</h2>
      <p class="second">À la connexion, <b>tous vos anciens avis</b> sont importés et analysés. Ensuite, les nouveaux arrivent automatiquement.</p>
      <div id="z-import"></div>
    </div>
    <div class="carte" style="display:grid;gap:14px">
      <h2>2. Partager votre enquête</h2>
      <p class="second">Imprimez ce lien en QR code sur vos tables ou à la réception, ou envoyez-le par WhatsApp après le séjour.</p>
      <div class="lien-enquete"><code id="lien">${esc(lien)}</code><button class="btn" data-a="copier" data-cible="lien">Copier le lien</button></div>
      <label class="champ" for="msg-wa">Message WhatsApp prêt à envoyer</label>
      <textarea id="msg-wa" rows="3" readonly>${esc(msg)}</textarea>
      <div class="rangee"><button class="btn" data-a="copier" data-cible="msg-wa">Copier le message</button><a class="btn" href="/e/${esc(e.jeton_enquete)}" target="_blank" rel="noopener">Voir l'enquête</a></div>
      <p class="discret">Client content : il est invité à publier son avis sur Google. Client mécontent : vous êtes alerté dans « Clients à rappeler ».</p>
    </div>
  </div>
  <div class="carte" style="margin-top:18px;max-width:720px"><h2 style="margin-bottom:12px">Informations de l'établissement</h2>${formEtab(e)}
    <div style="border-top:1px solid var(--trait);margin-top:18px;padding-top:14px"><button class="btn danger" data-a="supprimer-etab">Supprimer cet établissement et ses données</button></div></div>`;
  etatImport();
}
async function etatImport() {
  const z = $("#z-import"); if (!z) return;
  const s = await api(`/api/etablissements/${etat.eid}/import`).catch(() => null); if (!s) return;
  if (s.import_statut === "en_cours") {
    const p = s.import_total ? Math.round(s.import_fait / s.import_total * 100) : 5;
    z.innerHTML = `<p><b>Import en cours</b> depuis ${esc(s.source_connectee)}</p><div class="progression" role="progressbar" aria-valuenow="${p}" aria-valuemin="0" aria-valuemax="100"><i style="width:${p}%"></i></div><p class="discret num">${s.import_fait} / ${s.import_total || "…"} avis</p>`;
    setTimeout(etatImport, 1500); return;
  }
  if (s.import_statut === "termine") {
    z.innerHTML = `<p><span class="etiq ok">Connectée</span> ${esc(s.source_connectee)}</p><p class="num">${s.import_total} avis importés et analysés.</p><button class="btn plein" data-a="vue" data-v="matin">Voir mon tableau</button>`;
    etat.cache = {}; return;
  }
  const f = await api("/api/fiches-demo").catch(() => ({ fiches: [] }));
  z.innerHTML = `${s.import_statut === "erreur" ? `<p class="erreur">L'import a échoué. Réessayez.</p>` : ""}
    <p class="discret">Démonstration : la connexion réelle passera par Google Business Profile, avec l'accord du propriétaire. Ici, on choisit une fiche du jeu de démonstration.</p>
    <label class="champ">Fiche à connecter<select id="fiche">${f.fiches.map((x) => `<option value="${esc(x.fiche)}">${esc(x.fiche)} (${esc(x.ville)}, ${x.avis} avis)</option>`).join("")}</select></label>
    <button class="btn plein" data-a="connecter" ${f.fiches.length ? "" : "disabled"}>Connecter et importer l'historique</button>`;
}

/* ------------------------------------------------------------ Analyse */
function vueAnalyse() {
  const ex = ["Pourquoi la note a baissé en août ?", "Que disent les clients du petit-déjeuner ?", "Quels problèmes reviennent dans les chambres ?", "Qu'est-ce que les clients aiment le plus ?"];
  $("#contenu").innerHTML = `<div class="entete"><div><h1>Poser une question à vos avis</h1><p>Écrivez votre question comme vous la poseriez à un collègue. La réponse cite les avis exacts sur lesquels elle s'appuie.</p></div></div>
  <form class="carte form" id="form-question">
    <label class="champ" for="q">Votre question</label>
    <div class="rangee"><input type="text" id="q" maxlength="300" placeholder="${esc(ex[0])}" style="flex:1;min-width:220px"><button class="btn plein" type="submit">Analyser</button></div>
    <div class="suggestions">${ex.map((q) => `<button type="button" data-a="suggestion" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>
  </form>
  <div id="z-reponse" style="margin-top:18px"></div>`;
}
async function poser(q) {
  const z = $("#z-reponse"); z.innerHTML = `<p class="chargement">Recherche dans vos avis…</p>`;
  try {
    const d = await api(`/api/etablissements/${etat.eid}/question`, { question: q });
    z.innerHTML = `<div class="carte" style="display:grid;gap:14px"><div class="rangee" style="justify-content:space-between"><h2>Réponse</h2><span class="etiq ${d.mode === "en ligne" ? "neon" : ""}">${d.mode === "en ligne" ? "IA en ligne" : "Mode local"}</span></div>
      <p class="reponse-ia">${esc(d.texte)}</p>
      ${d.sources.length ? `<h3>Les avis utilisés</h3><ol class="sources">${d.sources.map((s) => `<li><b>[${s.n}]</b> ${etoiles(s.note)} <span class="discret">${date(s.date)}</span><br>${esc(s.texte)}</li>`).join("")}</ol>` : ""}</div>`;
  } catch (e) { z.innerHTML = `<div class="vide">${esc(e.message)}</div>`; }
}

/* ------------------------------------------------------------ Actions */
async function vueActions() {
  const c = $("#contenu");
  c.innerHTML = `<div class="entete"><div><h1>Actions</h1><p>Transformez les plaintes en actions : un responsable, un objectif, puis vérifiez que les avis s'améliorent.</p></div></div>
  <form class="carte form" id="form-action"><div class="grille2">
    <label class="champ">Action<input type="text" id="x-titre" maxlength="160" required placeholder="Vérifier les serviettes à chaque arrivée"></label>
    <label class="champ">Sujet<select id="x-sujet">${["Chambre et literie", "Propreté", "Personnel et service", "Petit-déjeuner et restauration", "Arrivée et départ", "Bruit", "Prix et rapport qualité-prix", "Wi-Fi et équipements", "Piscine, spa et animations", "Autre"].map((s) => `<option>${esc(s)}</option>`).join("")}</select></label>
    <label class="champ">Responsable<input type="text" id="x-resp" maxlength="80" placeholder="Gouvernante"></label>
    <label class="champ">Objectif<input type="text" id="x-obj" maxlength="160" placeholder="Moins de plaintes de propreté en 30 jours"></label></div>
    <p class="erreur" id="x-erreur" role="alert"></p><button class="btn plein" type="submit" style="justify-self:start">Ajouter l'action</button></form>
  <div id="z-actions" style="margin-top:18px"><p class="chargement">Chargement…</p></div>`;
  const d = await api(`/api/etablissements/${etat.eid}/actions`).catch(() => ({ actions: [] }));
  const col = { a_lancer: "À lancer", en_cours: "En cours", termine: "Terminée" }, suiv = { a_lancer: ["en_cours", "Démarrer"], en_cours: ["termine", "Marquer comme terminée"] };
  $("#z-actions").innerHTML = d.actions.length ? `<div class="tableau-defile"><table class="liste"><thead><tr><th>Action</th><th>Sujet</th><th>Responsable</th><th>Objectif</th><th>État</th><th></th></tr></thead><tbody>
    ${d.actions.map((a) => `<tr><td>${esc(a.titre)}</td><td>${esc(a.sujet)}</td><td>${esc(a.responsable)}</td><td>${esc(a.objectif)}</td><td><span class="etiq ${a.statut === "termine" ? "ok" : ""}">${col[a.statut]}</span></td>
    <td>${suiv[a.statut] ? `<button class="btn" data-a="action" data-id="${esc(a.id)}" data-s="${suiv[a.statut][0]}">${suiv[a.statut][1]}</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
    : `<div class="vide"><p>Aucune action pour l'instant. Partez d'un sujet de plainte du tableau « Ce matin ».</p></div>`;
}

/* ------------------------------------------------------------ Abonnement */
async function vueAbonnement() {
  const m = etat.moi, a = m.abonnement, q = m.quota;
  const o = await api("/api/offres");
  $("#contenu").innerHTML = `<div class="entete"><div><h1>Abonnement</h1><p>Offre actuelle : <b>${esc(a?.nom || "aucune")}</b>${a ? `, ${a.actif ? "active jusqu'au " + date(a.fin) : "expirée"}` : ""}.</p></div></div>
  <div class="carte quota" style="max-width:520px;margin-bottom:20px"><div class="rangee" style="justify-content:space-between"><b>Actions IA ce mois-ci</b><span class="num">${q.utilise} / ${q.plafond}</span></div>
    <div class="progression"><i style="width:${q.plafond ? Math.min(100, q.utilise / q.plafond * 100) : 0}%"></i></div></div>
  ${o.paiement_demo ? `<p class="discret" style="margin-bottom:14px">Paiement de démonstration : aucun prélèvement réel. En production, le paiement passera par la page sécurisée d'un prestataire (CMI ou Stripe).</p>` : ""}
  <div class="offres">${cartesOffres(o.offres, a?.offre, true)}</div>`;
}

/* ------------------------------------------------------------ Administration */
async function vueAdmin() {
  const c = $("#contenu"); c.innerHTML = `<p class="chargement">Chargement…</p>`;
  const d = await api("/api/admin/vue").catch((e) => ({ erreur: e.message }));
  if (d.erreur) { c.innerHTML = `<div class="vide">${esc(d.erreur)}</div>`; return; }
  const rev = d.revenus.reduce((s, r) => s + (r.total || 0), 0), t = d.totaux;
  c.innerHTML = `<div class="entete"><div><h1>Administration</h1><p>Vue de la plateforme. Paiement : ${d.paiement_demo ? "démonstration" : "réel"}.</p></div></div>
  <div class="carte" style="margin-bottom:22px;display:grid;gap:14px"><div class="rangee" style="justify-content:space-between"><h2>Modèle d'IA</h2>
    <span class="etiq ${d.ia_en_ligne ? "ok" : ""}">${d.openrouter ? "Clé OpenRouter détectée" : d.ia_en_ligne ? "Clé Anthropic détectée" : "Aucune clé : mode local gratuit"}</span></div>
    <p class="second">Choisissez la qualité des réponses rédigées par l'IA. Prix OpenRouter en dollars par million de jetons (entrée / sortie).</p>
    <div class="offres">${Object.entries(d.niveaux).map(([k, n]) => `<div class="offre ${k === d.niveau ? "vedette" : ""}"><h3>${esc(n.nom)}</h3><p class="discret">${esc(n.modele)}</p>
      <p class="num">${esc(n.prix)}<br><span class="discret">Une réponse à un avis : ${esc(n.par_reponse)}</span></p>
      <button class="btn ${k === d.niveau ? "" : "plein"}" data-a="niveau" data-n="${k}" ${k === d.niveau ? "disabled" : ""}>${k === d.niveau ? "Niveau actuel" : "Utiliser ce niveau"}</button></div>`).join("")}</div>
    ${d.openrouter ? "" : `<p class="discret">Ajoutez OPENROUTER_API_KEY dans le fichier app/.env puis relancez le serveur.</p>`}</div>
  <div class="chiffres" style="margin:0 0 22px"><div><b class="num">${d.comptes.length}</b><span>Comptes</span></div><div><b class="num">${t.etab}</b><span>Établissements</span></div>
    <div><b class="num">${t.avis}</b><span>Avis gérés</span></div><div><b class="num">${fr(rev / 100, 0)} DH</b><span>Encaissé (démo)</span></div></div>
  <div class="carte"><h2 style="margin-bottom:12px">Comptes</h2><div class="tableau-defile"><table class="liste"><thead><tr><th>Nom</th><th>E-mail</th><th>Rôle</th><th>Offre</th><th>Fin</th><th>Établ.</th><th>IA ce mois</th></tr></thead><tbody>
    ${d.comptes.map((u) => `<tr><td>${esc(u.nom)}</td><td>${esc(u.email)}</td><td>${esc(u.role)}</td><td>${esc(u.offre || "")}</td><td>${date(u.fin)}</td><td class="num">${u.etablissements}</td><td class="num">${u.ia_mois}</td></tr>`).join("")}</tbody></table></div></div>
  <div class="grille2" style="margin-top:18px">
    <div class="carte"><h2 style="margin-bottom:12px">Consommation IA du mois</h2>${d.conso.length ? `<table class="liste"><tbody>${d.conso.map((x) => `<tr><td>${esc(x.type)}</td><td>${esc(x.mode)}</td><td class="num">${x.n}</td></tr>`).join("")}</tbody></table>` : '<p class="discret">Aucun appel ce mois-ci.</p>'}</div>
    <div class="carte"><h2 style="margin-bottom:12px">Journal</h2><div style="max-height:320px;overflow:auto"><table class="liste"><tbody>${d.journal.map((j) => `<tr><td class="discret num">${esc(j.date)}</td><td>${esc(j.evenement)}</td><td class="discret">${esc(j.detail)}</td></tr>`).join("")}</tbody></table></div></div>
  </div>`;
}

/* ------------------------------------------------------------ événements */
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-a]"); if (!b) return;
  const a = b.dataset.a;
  try {
    if (a === "aller-connexion" || a === "onglet") { pagePublique(b.dataset.o || "connexion"); return; }
    if (a === "vue") { changerVue(b.dataset.v); $("#rail")?.classList.remove("ouvert"); return; }
    if (a === "menu") { $("#rail").classList.toggle("ouvert"); return; }
    if (a === "deconnexion") { await api("/api/deconnexion", {}); etat.moi = { connecte: false }; location.hash = ""; pagePublique("connexion"); return; }
    if (a === "choisir-avis") { etat.cache.sel = +b.dataset.i; etat.cache.fr = false; listeAvis(); lecteur(); return; }
    if (a === "langue") { etat.cache.fr = b.dataset.l === "f"; const v = $("#reponse").value; lecteur(); $("#reponse").value = v; return; }
    if (a === "ton") { etat.cache.ton = b.dataset.t; const v = $("#reponse").value; lecteur(); $("#reponse").value = v; return; }
    if (a === "brouillon") { await brouillon(); return; }
    if (a === "publier") {
      const av = etat.cache.avis[etat.cache.sel], t = $("#reponse").value.trim();
      if (t.length < 10) { toast("Écrivez ou préparez d'abord une réponse."); return; }
      await api(`/api/avis/${av.id}/publier`, { texte: t }); toast("Réponse validée et enregistrée");
      etat.cache.avis.splice(etat.cache.sel, 1); etat.cache.sel = 0; etat.cache.tableau = null;
      if (!etat.cache.avis.length) return vueAvis(); listeAvis(); lecteur(); pastilles(); return;
    }
    if (a === "ignorer") { const av = etat.cache.avis[etat.cache.sel]; await api(`/api/avis/${av.id}/ignorer`, {}); toast("Avis retiré de la file");
      etat.cache.avis.splice(etat.cache.sel, 1); etat.cache.sel = 0; etat.cache.tableau = null; if (!etat.cache.avis.length) return vueAvis(); listeAvis(); lecteur(); pastilles(); return; }
    if (a === "cas") { await api(`/api/cas/${b.dataset.id}/statut`, { statut: b.dataset.s }); toast(b.dataset.s === "rattrape" ? "Bravo, client rattrapé" : "Cas mis à jour"); etat.cache.tableau = null; vueRattrapage(); pastilles(); return; }
    if (a === "connecter") { await api(`/api/etablissements/${etat.eid}/connecter`, { fiche: $("#fiche").value }); toast("Import lancé"); etatImport(); return; }
    if (a === "copier") { const el = $("#" + b.dataset.cible), v = el.value ?? el.textContent;
      try { await navigator.clipboard.writeText(v); toast("Copié"); } catch (e) { const r = document.createRange(); r.selectNodeContents(el); getSelection().removeAllRanges(); getSelection().addRange(r); toast("Sélectionné : Ctrl + C pour copier"); } return; }
    if (a === "suggestion") { $("#q").value = b.dataset.q; poser(b.dataset.q); return; }
    if (a === "action") { await api(`/api/actions/${b.dataset.id}/statut`, { statut: b.dataset.s }); toast("Action mise à jour"); vueActions(); return; }
    if (a === "niveau") { await api("/api/admin/niveau-ia", { niveau: b.dataset.n }); toast("Niveau d'IA changé"); await charger(); return; }
    if (a === "payer") { b.disabled = true; await api("/api/abonnement/payer", { offre: b.dataset.o }); toast("Abonnement activé (démonstration)"); await charger(); return; }
    if (a === "supprimer-etab") {
      if (b.dataset.confirme !== "1") { b.dataset.confirme = "1"; b.textContent = "Cliquez encore pour confirmer la suppression définitive"; return; }
      await api(`/api/etablissements/${etat.eid}/supprimer`, {}); toast("Établissement supprimé"); try { localStorage.removeItem("voxcx_eid"); } catch (e) { /* */ } etat.vue = "matin"; await charger(); return;
    }
  } catch (e) { toast(e.message); b.disabled = false; }
});

document.addEventListener("change", (ev) => {
  if (ev.target.id === "choix-etab") {
    const v = ev.target.value;
    if (v === "__nouveau") { $("#contenu").innerHTML = `<div class="entete"><div><h1>Ajouter un établissement</h1></div></div><div class="carte" style="max-width:620px">${formEtab()}</div>`; return; }
    etat.eid = v; try { localStorage.setItem("voxcx_eid", v); } catch (e) { /* */ } etat.cache = {}; rendre();
  }
});

document.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  if (f.id === "form-compte") {
    const inscr = !!$("#f-nom"), err = $("#f-erreur"); err.textContent = "";
    const corps = { email: $("#f-email").value.trim(), mot: $("#f-mot").value };
    if (inscr) corps.nom = $("#f-nom").value.trim();
    if (!corps.email || !corps.mot || (inscr && !corps.nom)) { err.textContent = "Remplissez tous les champs."; return; }
    if (inscr && corps.mot.length < 10) { err.textContent = "Le mot de passe doit contenir au moins 10 caractères."; return; }
    try { await api(inscr ? "/api/inscription" : "/api/connexion", corps); await charger(); } catch (e) { err.textContent = e.message; }
  }
  if (f.id === "form-etab") {
    const err = $("#e-erreur"); err.textContent = "";
    const corps = { nom: $("#e-nom").value.trim(), ville: $("#e-ville").value.trim(), type: $("#e-type").value, lien_avis: $("#e-lien").value.trim() };
    if (corps.nom.length < 2 || corps.ville.length < 2) { err.textContent = "Indiquez le nom et la ville."; return; }
    if (corps.lien_avis && !corps.lien_avis.startsWith("https://")) { err.textContent = "Le lien doit commencer par https://"; return; }
    const modif = f.closest("#contenu") && etab() && $("#lien");
    try {
      if (modif) { await api(`/api/etablissements/${etat.eid}/modifier`, corps); toast("Enregistré"); await charger(); }
      else { const d = await api("/api/etablissements", corps); try { localStorage.setItem("voxcx_eid", d.id); } catch (e) { /* */ } toast("Établissement créé"); location.hash = "collecte"; await charger(); }
    } catch (e) { err.textContent = e.message; }
  }
  if (f.id === "form-question") { const q = $("#q").value.trim(); if (q.length >= 3) poser(q); }
  if (f.id === "form-action") {
    const t = $("#x-titre").value.trim(); if (t.length < 3) { $("#x-erreur").textContent = "Décrivez l'action."; return; }
    try { await api(`/api/etablissements/${etat.eid}/actions`, { titre: t, sujet: $("#x-sujet").value, responsable: $("#x-resp").value.trim(), objectif: $("#x-obj").value.trim() }); toast("Action ajoutée"); vueActions(); }
    catch (e) { $("#x-erreur").textContent = e.message; }
  }
});

charger().catch((e) => { $("#app").innerHTML = `<div class="vide" style="margin:32px">${esc(e.message)}</div>`; });
