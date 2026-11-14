/* VoxCX : les cinq pages */
'use strict';

let jeton = 0;
const base = (titre, sous, filtres = true) => { $('#main').innerHTML = enteteHTML(titre, sous, filtres) + '<div id="contenu"></div>'; brancherEntete(); };
const contenu = h => { $('#contenu').innerHTML = h; };
const carte = (titre, sous, corps, classe = '', droite = '') => `<section class="card ${classe}"><div class="ch"><div><div class="ct">${titre}</div>${sous ? `<div class="cs">${sous}</div>` : ''}</div>${droite}</div>${corps}</section>`;

function listeSources(sources) {
  if (!sources.length) return '<div class="vide">Aucun avis à afficher.</div>';
  return sources.map(s => `<div class="source"><div class="mt"><b style="color:var(--text)">${esc(s.hotel)}</b><span>${esc(s.date)}</span><span>${s.note}/5</span><span>${esc(nomAuteur(s.auteur))}</span></div>${esc(s.texte) || '<i>(note sans commentaire)</i>'}</div>`).join('');
}
const ICONE_TON = { ok: ['tendance', 'var(--green)'], ko: ['alerte', 'var(--red)'], info: ['tendance', 'var(--blue)'], accent: ['etoile', 'var(--accent)'] };

// =========================================================== ACCUEIL
RENDU.accueil = async function () {
  const j = ++jeton;
  base('Vue d\'ensemble', 'Chargement des avis…');
  contenu(chargement());
  let d;
  try { d = await api('/api/accueil?' + qs() + '&action=' + E.action); } catch (e) { if (j === jeton) contenu(messageErreur(e)); return; }
  if (j !== jeton) return;
  if (d.vide) { contenu('<div class="vide">Aucun avis pour ces filtres. Élargissez la période ou la sélection d\'hôtels.</div>'); return; }
  $('#sous-titre').textContent = `Kenzi Hotels · ${d.n_hotels} hôtel${d.n_hotels > 1 ? 's' : ''} · ${fr(d.n_avis)} avis du ${d.periode.debut} au ${d.periode.fin}`;
  const k = d.kpis, S = d.serie;
  const kpi = (lib, val, pied, spark) => `<section class="card kpi s3"><span class="lbl">${lib}</span><span class="v">${val}</span><span class="d">${pied}</span><span class="sp">${sparkline(spark)}</span></section>`;
  const syn = d.insights.map((x, i) => {
    const [ic, coul] = ICONE_TON[x.ton] || ICONE_TON.info;
    return `<div><div class="h" style="color:${coul}">${ico(ic, 16, 1.8)}<span style="color:var(--text)">${esc(x.titre)}</span></div><p>${esc(x.texte)}</p>
      <div class="a"><button class="lnk" data-src="${i}">Voir les avis</button>${x.lien === 'plan' ? '<a class="lnk" href="#/plan">Voir le plan d\'actions</a>' : ''}</div></div>`;
  }).join('');
  const aa = d.avant_apres;
  const alertes = d.alertes.map(a => `<div class="al"><span class="dot" style="background:var(--${a.niveau === 'Critique' ? 'red' : 'amber'})"></span><div><b>${esc(a.hotel)}</b><span>${esc(a.texte)}</span></div></div>`).join('')
    || '<div class="al"><span class="dot" style="background:var(--green)"></span><div><b>Rien d\'anormal</b><span>Aucune hausse de plaintes sur les 8 dernières semaines</span></div></div>';
  const maxN = Math.max(...d.classement.map(c => c.note)), minN = Math.min(...d.classement.map(c => c.note));
  const lignes = d.classement.map((c, i) => `<tr><td style="width:34px"><span class="rk">${i + 1}</span></td><td><b style="font-weight:500">${esc(c.hotel)}</b><div class="note">${esc(c.ville)}</div></td>
      <td style="min-width:150px"><div style="display:flex;align-items:center;gap:10px"><span class="num" style="width:34px;font-weight:600">${fr(c.note, 2)}</span><div class="tb" style="flex:1"><i style="width:${(Math.max(0.08, (c.note - (minN - 0.35)) / (maxN - (minN - 0.35))) * 100).toFixed(0)}%;background:var(--${c.note < minN + 0.15 && d.classement.length > 3 ? 'red' : 'accent'})"></i></div></div></td>
      <td class="m">${sparkline(c.spark, 70, 24)}</td><td class="r">${delta(c.delta30, 2, '', false) || '<span class="note">–</span>'}</td><td class="r m num">${fr(c.n)}</td></tr>`).join('');
  const sents = d.sentiments.map(s => `<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px"><span style="flex:0 0 118px;font-size:13px">${esc(s.hotel.replace('Kenzi ', ''))}</span>
      <div class="tb st" style="flex:1;height:8px"><i style="width:${s.positif}%;background:var(--green)"></i><i style="width:${s.neutre}%;background:var(--muted);opacity:.55"></i><i style="width:${s.negatif}%;background:var(--red)"></i></div>
      <span class="num" style="flex:0 0 42px;text-align:right;font-weight:500">${fr(s.positif)} %</span></div>`).join('');

  contenu(`
  <div class="g">
    ${kpi('Note moyenne', `<span data-n="${k.note}" data-d="2">${fr(k.note, 2)}</span><small>/ 5</small>`, delta(k.delta30, 2, '', false, 'sur 30 jours'), S.map(s => s.note))}
    ${kpi('Indice de recommandation *', `<span data-n="${k.nps}" data-pre="+" data-d="0">${k.nps}</span>`, delta(k.delta_nps, 0, ' pts', false, 'sur 30 jours'), S.map(s => s.nps))}
    ${kpi('Avis négatifs', `<span data-n="${k.plaintes}" data-d="1">${fr(k.plaintes, 1)}</span><small>%</small>`, delta(k.delta_plaintes, 1, ' pts', true, 'sur 30 jours'), S.map(s => s.plaintes))}
    ${kpi('Réponses de l\'hôtel', `<span data-n="${k.reponse}" data-d="0">${fr(k.reponse)}</span><small>%</small>`, `délai médian ${fr(k.delai_h)} h`, S.map(s => s.reponse))}
  </div>
  ${carte('Synthèse de la semaine', 'Trois constats calculés automatiquement, chacun relié à des avis réels', `<div class="syn">${syn}</div>`)}
  <div class="g">
    ${carte('Évolution de la note', 'Note moyenne mensuelle, avant et après une date d\'action', `<div class="chart" id="graph"></div>
      ${aa ? `<div class="stat3"><div><div class="lbl">Avant l'action</div><div class="v">${fr(aa.avant, 2)}</div><div class="note">${fr(aa.n_avant)} avis</div></div>
        <div><div class="lbl">Après l'action</div><div class="v">${fr(aa.apres, 2)}</div><div class="note">${fr(aa.n_apres)} avis</div></div>
        <div><div class="lbl">Écart</div><div class="v">${delta(aa.ecart, 2)}</div><div class="note"><span class="b ${aa.significatif ? 'b-acc' : 'b-neu'}">${aa.significatif ? 'Significatif' : 'Non significatif'}</span> p = ${fr(aa.p, 3)}</div></div></div>`
        : '<p class="note" style="margin:10px 0 0">Choisissez une date d\'action située dans la période pour comparer avant et après.</p>'}
      <p class="note" style="margin:12px 0 0">Association observée, pas une preuve de cause : saison, tarifs et clientèle changent aussi.</p>`, 's8',
      `<label class="lbl" style="display:flex;align-items:center;gap:8px">Date d'action<input type="date" id="d-action" class="field" style="width:150px" value="${d.action}"></label>`)}
    ${carte('Alertes', 'Plaintes en hausse sur 8 semaines', alertes, 's4')}
  </div>
  <div class="g">
    ${carte('Classement des hôtels', 'Note moyenne sur la période, évolution mensuelle et variation sur 30 jours', `<table class="tbl"><thead><tr><th></th><th>Hôtel</th><th>Note</th><th>Évolution</th><th class="r">30 jours</th><th class="r">Avis</th></tr></thead><tbody>${lignes}</tbody></table>`, 's7')}
    ${carte('Répartition des sentiments', 'Part des commentaires par hôtel (modèle local)', `${sents}<div class="sentl"><span><i class="dot" style="background:var(--green)"></i>Positif</span><span><i class="dot" style="background:var(--muted);opacity:.6"></i>Neutre</span><span><i class="dot" style="background:var(--red)"></i>Négatif</span></div>`, 's5')}
  </div>
  <footer class="note">* Indice de recommandation estimé à partir des notes Google : 5 étoiles = promoteur, 3 étoiles ou moins = détracteur (approximation, ce n'est pas le NPS d'une enquête). Source : avis publics Google Maps, collecte automatisée du 16/10/2026.</footer>`);
  courbe($('#graph'), d.serie, d.action, aa);
  $$('[data-src]').forEach(b => b.onclick = () => { const x = d.insights[+b.dataset.src]; ouvrirTiroir(x.titre, `<p class="note" style="margin:0">${esc(x.texte)}</p>${listeSources(x.sources)}`); });
  $('#d-action').onchange = e => { E.action = e.target.value || E.action; sauver(); RENDU.accueil(); };
  animerNombres($('#contenu')); cascade($('#contenu'));
};

// =========================================================== THÈMES
RENDU.themes = async function (rang = 0) {
  const j = ++jeton;
  base('Thèmes abordés', 'Les sujets les plus cités dans les commentaires et ceux qui posent problème');
  contenu(chargement());
  let d;
  try { d = await api('/api/themes?' + qs() + '&rang=' + rang); } catch (e) { if (j === jeton) contenu(messageErreur(e)); return; }
  if (j !== jeton) return;
  if (d.vide) { contenu('<div class="vide">Le sentiment par aspect n\'est pas encore calculé.</div>'); return; }
  const lignes = d.sujets.map(s => `<tr class="clic" data-asp="${esc(s.aspect)}"><td style="font-weight:500">${esc(s.aspect)}</td><td class="m num">${fr(s.mentions)}</td>
      <td style="min-width:130px"><div class="tb"><i style="width:${Math.max(2, s.part * 100).toFixed(0)}%;background:var(--${s.part >= 0.3 ? 'red' : s.part >= 0.15 ? 'amber' : 'muted'})"></i></div></td>
      <td class="r num" style="font-weight:500;${s.part >= 0.3 ? 'color:var(--red)' : ''}">${fr(s.part * 100)} %</td></tr>`).join('');
  const niv = { 'Élevé': ['b-ko', 'Élevée'], 'Moyen': ['b-mid', 'Moyenne'], 'Faible': ['b-info', 'Faible'] };
  const prio = d.priorites.map((p, i) => `<div class="pr"><span class="rk">${i + 1}</span><div style="flex:1;min-width:0"><b>${esc(p.aspect)}</b><span class="s">${fr(p.negatives)} commentaires négatifs · ${p.tendance > 0.5 ? 'en hausse de ' + fr(p.tendance, 1) + ' pts' : p.tendance < -0.5 ? 'en baisse de ' + fr(Math.abs(p.tendance), 1) + ' pts' : 'stable'}</span>
      <div class="tb" style="margin-top:8px"><i style="width:${p.priorite}%;background:var(--${p.priorite >= 66 ? 'red' : p.priorite >= 33 ? 'amber' : 'blue'})"></i></div></div>
      <div style="text-align:right"><div class="num" style="font-weight:600;font-size:16px">${p.priorite}</div><span class="b ${(niv[p.niveau] || niv.Faible)[0]}">${(niv[p.niveau] || niv.Faible)[1]}</span></div></div>`).join('');
  const L = d.lecture;
  const lecture = L ? `<p style="margin:0;font-size:15px;line-height:2.1">${L.phrases.map(p => `<span class="${p.sens === 'positif' ? 'hl-p' : p.sens === 'négatif' ? 'hl-n' : 'hl-0'}">${esc(p.texte)}</span>${p.aspects.map(a => `<span class="tg">${esc(a)}</span>`).join('')} `).join('')}</p>
      <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:14px;align-items:center"><span class="b b-ok">Positif</span><span class="b b-ko">Négatif</span><span class="b b-neu">Neutre</span>
      <span class="note">${esc(L.hotel)} · ${esc(L.date)} · ${L.note}/5 · ${esc(nomAuteur(L.auteur))}</span><button class="lnk" id="autre-avis">Voir un autre avis</button></div>` : '<div class="vide">Aucun avis assez riche à afficher.</div>';
  const fiab = d.fiabilite.map(f => `« ${esc(f.aspect.split(' ')[0])} » ${fr(f.corr, 2)}`).join(' · ');
  contenu(`
  <div style="display:flex;flex-wrap:wrap;gap:8px"><button class="sel ${!E.villeSel ? 'on' : ''}" data-v="">Tous les hôtels</button>${E.meta.villes.map(v => `<button class="sel ${E.villeSel && E.villeSel[0] === v ? 'on' : ''}" data-v="${esc(v)}">${esc(v)}</button>`).join('')}</div>
  <div class="g">
    ${carte('Sujets abordés', 'Part de commentaires négatifs par sujet. Cliquez sur une ligne pour lire les phrases.', `<table class="tbl"><thead><tr><th>Sujet</th><th>Mentions</th><th>Part négative</th><th class="r"></th></tr></thead><tbody>${lignes}</tbody></table>`, 's7')}
    ${carte('Priorités', 'Classement selon le nombre de plaintes, leur gravité et leur évolution', `${prio || '<div class="vide">Pas assez de commentaires négatifs.</div>'}<div style="margin-top:10px"><a class="lnk" href="#/plan">Voir les actions proposées</a></div>`, 's5')}
  </div>
  ${carte('Carte de chaleur', 'Score moyen de 0 à 10 par sujet et par hôtel (– : moins de 5 mentions). Rouge : à corriger, vert : point fort.', carteChaleur(d.matrice))}
  ${carte('Comment l\'IA lit un avis', 'Chaque phrase est classée par sujet et par sentiment', `${lecture}${fiab ? `<p class="note" style="margin:14px 0 0">Fiabilité vérifiée avec les notes détaillées données par les clients sur Google (corrélation de rang) : ${fiab}.</p>` : ''}`)}
  <footer class="note">Source : avis publics Google Maps des hôtels Kenzi. Sentiment calculé par un modèle multilingue local (français, anglais, arabe, espagnol…). Limites : modèle généraliste, nuances comme « moyen » parfois mal classées.</footer>`);
  $$('[data-v]').forEach(b => b.onclick = () => { E.villeSel = b.dataset.v ? [b.dataset.v] : null; RENDU.themes(); });
  $$('[data-asp]').forEach(b => b.onclick = () => phrasesAspect(b.dataset.asp, 'négatif'));
  const ra = $('#autre-avis'); if (ra) ra.onclick = () => RENDU.themes(rang + 1);
  cascade($('#contenu'));
};
async function phrasesAspect(aspect, sens) {
  ouvrirTiroir(aspect, chargement('Recherche des phrases…'));
  try {
    const r = await api('/api/themes/phrases?' + qs() + '&aspect=' + encodeURIComponent(aspect) + '&sens=' + encodeURIComponent(sens));
    const corps = `<div style="display:flex;gap:8px"><button class="sel ${sens === 'négatif' ? 'on' : ''}" id="s-neg">Négatives</button><button class="sel ${sens === 'positif' ? 'on' : ''}" id="s-pos">Positives</button></div>` +
      (r.length ? r.map(x => `<div class="source"><div class="mt"><b style="color:var(--text)">${esc(x.hotel)}</b><span>${esc(x.date)}</span>${x.note ? `<span>${x.note}/5</span>` : ''}<span>${esc(nomAuteur(x.auteur))}</span></div>« ${esc(x.phrase)} »</div>`).join('') : '<div class="vide">Aucune phrase.</div>');
    const t = $('#tiroir'); if (!t) return;
    t.querySelector('.drawer').innerHTML = `<div class="top2"><h3>${esc(aspect)}</h3><button class="ibtn" id="x-tiroir" aria-label="Fermer">${ico('fermer')}</button></div>${corps}`;
    $('#x-tiroir').onclick = fermerTiroir; $('#s-neg').onclick = () => phrasesAspect(aspect, 'négatif'); $('#s-pos').onclick = () => phrasesAspect(aspect, 'positif');
  } catch (e) { const t = $('#tiroir .drawer'); if (t) t.innerHTML += messageErreur(e); }
}

// =========================================================== ASSISTANT
RENDU.assistant = function () {
  ++jeton;
  base('Pose ta question', 'Un assistant qui répond uniquement à partir des avis, en citant ses sources');
  const hotels = E.meta.hotels.map(h => h.hotel);
  const suggestions = ['Pourquoi les clients se plaignent-ils du bruit ?', 'Quels sont les points forts de Kenzi Menara Palace ?', 'Que disent les clients du petit-déjeuner ?', 'Y a-t-il des problèmes de propreté ?'];
  contenu(`<div class="g">
    <section class="card s8" style="display:flex;flex-direction:column;gap:16px;min-height:560px">
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center"><label class="btn-s" style="gap:8px">${ico('hotel')}<select id="a-hotel" style="background:transparent;border:0;color:inherit"><option value="">Tous les hôtels</option>${hotels.map(h => `<option>${esc(h)}</option>`).join('')}</select></label>
        <label class="btn-s" style="gap:8px"><input type="checkbox" id="a-neg" style="accent-color:var(--accent)">Avis négatifs seulement</label></div>
      <div class="chat" id="chat"></div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center"><span class="note">Essayer :</span>${suggestions.map(s => `<button class="sug" data-q="${esc(s)}">${esc(s)}</button>`).join('')}</div>
      <form class="in" id="form-q"><input type="text" id="q" aria-label="Votre question" placeholder="Posez une question sur vos avis clients…" autocomplete="off"><button type="submit" aria-label="Envoyer">${ico('envoyer', 18, 2)}</button></form>
    </section>
    ${carte('Sources utilisées', 'Avis réels sur lesquels repose la réponse', `<div id="sources"><div class="vide">Posez une question : les avis utilisés apparaîtront ici.</div></div>
      <p class="note" style="margin:14px 0 0">Garde-fous : refus de répondre sans avis pertinent, aucune donnée inventée, chaque échange enregistré dans le journal de gouvernance.</p>`, 's4')}
  </div>
  <footer class="note">Mode local : réponse construite à partir des avis retrouvés, sans génération de texte. Mode en ligne : Claude rédige la réponse à partir des mêmes avis.</footer>`);
  dessinerChat();
  $$('[data-q]').forEach(b => b.onclick = () => poser(b.dataset.q));
  $('#form-q').onsubmit = e => { e.preventDefault(); const v = $('#q').value.trim(); if (v) poser(v); };
};
function citer(t) { return esc(t).replace(/\[(\d+)\]/g, '<span class="cite">[$1]</span>'); }
function dessinerChat() {
  const c = $('#chat'); if (!c) return;
  if (!E.chat.length) { c.innerHTML = '<div class="vide">Posez une question sur vos avis, par exemple « Pourquoi les clients se plaignent-ils du bruit ? ».</div>'; return; }
  c.innerHTML = E.chat.map((m, i) => m.role === 'q' ? `<div class="mu">${esc(m.texte)}</div>` :
    `<div class="ma"><div class="meta"><span class="b b-info">Mode ${esc(m.mode)}</span><span>${m.sources.length} avis consultés · ${m.duree} s · confiance ${esc(m.confiance)}</span></div>
      <div class="corps">${m.attente ? chargement('Recherche dans les avis…') : citer(m.texte)}</div>
      ${m.attente || m.erreur ? '' : `<div style="display:flex;flex-wrap:wrap;gap:8px"><button class="btn2 g" data-fb="ok" data-i="${i}">Réponse correcte</button><button class="btn2" data-fb="ko" data-i="${i}">Signaler une erreur</button><a class="btn2" href="#/plan">Créer une action</a></div>`}</div>`).join('');
  $$('[data-fb]', c).forEach(b => b.onclick = async () => {
    const ok = b.dataset.fb === 'ok';
    await api('/api/journal', { evenement: ok ? 'validation' : 'signalement', auteur: 'Humain', detail: (E.chat[+b.dataset.i - 1] || {}).texte + (ok ? ' | réponse jugée correcte' : ' | erreur signalée') });
    toast(ok ? 'Enregistré dans le journal de gouvernance.' : 'Signalement enregistré.');
  });
  const dernier = [...E.chat].reverse().find(m => m.role === 'a' && !m.attente);
  const s = $('#sources');
  if (s && dernier) s.innerHTML = dernier.sources.length ? dernier.sources.map((x, i) => `<div class="src"><div class="mt"><span class="cite">[${i + 1}]</span><span>${esc(x.hotel)} · ${esc(x.date)}</span><span class="dl ${x.note <= 2 ? 'dn' : x.note === 3 ? 'fl' : 'up'}" style="margin-left:auto">${x.note}/5</span></div><p>${esc(x.texte)}</p></div>`).join('') : '<div class="vide">Aucune source.</div>';
}
async function poser(texte) {
  E.chat.push({ role: 'q', texte }); E.chat.push({ role: 'a', attente: true, texte: '', sources: [], mode: E.mode, duree: 0, confiance: '…' });
  dessinerChat(); const q = $('#q'); if (q) q.value = '';
  try {
    const r = await api('/api/assistant', { question: texte, hotel: $('#a-hotel') ? $('#a-hotel').value : '', negatifs: $('#a-neg') ? $('#a-neg').checked : false, k: 8, mode: E.mode, debut: E.filtres.debut });
    E.chat[E.chat.length - 1] = { role: 'a', texte: r.texte, sources: r.sources, mode: r.mode, duree: r.duree, confiance: r.confiance };
  } catch (e) { E.chat[E.chat.length - 1] = { role: 'a', erreur: true, texte: 'Désolé, une erreur est survenue : ' + e.message, sources: [], mode: E.mode, duree: 0, confiance: 'n/d' }; }
  if (pageCourante().id === 'assistant') dessinerChat();
}

// =========================================================== PRÉDICTIF
RENDU.predictif = async function () {
  const j = ++jeton;
  base('Détection des clients insatisfaits', 'L\'IA lit un avis, estime le risque d\'insatisfaction (3 étoiles ou moins) et la note probable', false);
  contenu(chargement('Chargement du modèle (la première fois, cela peut prendre une minute)…'));
  let d;
  try { d = await api('/api/predictif'); } catch (e) { if (j === jeton) contenu(messageErreur(e)); return; }
  if (j !== jeton) return;
  const noms = { 'Régression logistique (TF-IDF + sentiment XLM-R)': 'Mots + sentiment (retenu)', 'Sentiment XLM-R seul (modèle local)': 'Sentiment seul', 'Régression logistique (TF-IDF)': 'Mots seuls (régression)', 'Forêt aléatoire (TF-IDF)': 'Forêt aléatoire' };
  const bench = d.benchmark.map(b => `<div style="display:flex;align-items:center;gap:12px;padding:9px 0"><span style="flex:0 0 190px;font-size:13px;${b.retenu ? 'font-weight:600' : ''}">${esc(noms[b.modele] || b.modele)}</span>
      <div class="tb" style="flex:1;height:8px"><i style="width:${(b.f1 * 100).toFixed(1)}%;background:var(--${b.retenu ? 'accent' : 'muted'});${b.retenu ? '' : 'opacity:.55'}"></i></div><span class="num" style="flex:0 0 38px;text-align:right;font-weight:600">${fr(b.f1, 2)}</span></div>`).join('');
  const stat = { ok: ['b-ok', 'Écart faible'], mid: ['b-mid', 'À surveiller'], ko: ['b-ko', 'Écart important'] };
  const biais = d.biais.map(b => `<tr><td style="font-weight:500">${esc(b.critere)}</td><td class="m">${b.groupes.map(g => esc(g.nom) + ' (' + g.n + ')').join(', ')}</td><td class="r num">${fr(b.ecart, 2)}</td><td class="r"><span class="b ${stat[b.statut][0]}">${stat[b.statut][1]}</span></td></tr>`).join('');
  const kp = (l, v, p) => `<section class="card kpi s4"><span class="lbl">${l}</span><span class="v">${v}</span><span class="d">${p}</span></section>`;
  const exemple = 'Chambre bruyante, on n\'a pas pu dormir. Le personnel est gentil mais le petit-déjeuner était décevant pour le prix.';
  contenu(`
  <div class="g">
    ${kp('Fiabilité de la détection (score F1)', `<span data-n="${d.f1}" data-d="2">${fr(d.f1, 2)}</span>`, `sur ${fr(d.n_test)} avis récents, jamais vus par le modèle`)}
    ${kp('Erreur sur la note prévue', `<span data-n="${d.mae}" data-d="2">${fr(d.mae, 2)}</span><small>étoile</small>`, `contre ${fr(d.mae_ref, 2)} sans IA (simple moyenne)`)}
    ${kp('Avis utilisés pour apprendre', `<span data-n="${d.n_app}" data-d="0">${fr(d.n_app)}</span>`, `les plus anciens ; test depuis le ${dateFr(d.date_coupure)}`)}
  </div>
  <div class="g">
    ${carte('Tester un avis', 'Collez un avis en français, anglais ou arabe', `<textarea class="ta" id="t-texte" aria-label="Texte de l'avis">${esc(exemple)}</textarea>
      <div style="margin:12px 0 18px"><button class="btn" id="t-go">Analyser cet avis</button></div><div id="t-res"></div>`, 's7')}
    ${carte('Choix du modèle', 'Quatre modèles comparés sur les mêmes avis (score F1)', `${bench}<p class="note" style="margin:10px 0 0">Le modèle retenu est aussi celui qu'on sait expliquer mot par mot (méthode SHAP). Le seuil d'alerte est choisi sur le jeu de test : estimation un peu optimiste.</p>`, 's5')}
  </div>
  ${carte('Équité du modèle', 'Le modèle marche-t-il aussi bien pour tous les groupes de clients ? Écart de score F1 par rapport à l\'ensemble.', `<table class="tbl"><thead><tr><th>Critère</th><th>Groupes comparés (avis)</th><th class="r">Écart max.</th><th class="r">Verdict</th></tr></thead><tbody>${biais}</tbody></table>
    <p class="note" style="margin:12px 0 0">Les petits groupes donnent des mesures instables. Aucune décision automatique : chaque alerte est relue par un responsable. Le modèle ne reçoit ni le nom, ni la nationalité du client.</p>`)}`);
  animerNombres($('#contenu')); cascade($('#contenu'));
  const go = async () => {
    const txt = $('#t-texte').value.trim(); if (txt.length < 5) { toast('Écrivez au moins quelques mots.'); return; }
    $('#t-go').disabled = true; $('#t-res').innerHTML = chargement('Analyse en cours…');
    try {
      const r = await api('/api/predictif/tester', { texte: txt });
      const haut = r.risque >= r.seuil, ton = r.contributions.find(m => m.mot.startsWith('ton général')), mots = r.contributions.filter(m => !m.mot.startsWith('ton général')).sort((a, b) => b.valeur - a.valeur), mx = Math.max(...mots.map(m => Math.abs(m.valeur)), 0.01);
      const shap = mots.map(m => { const w = Math.abs(m.valeur) / mx * 36, pos = m.valeur > 0;
        return `<div class="lbl2" title="${esc(m.mot)}">${esc(m.mot)}</div><div class="track"><i style="${pos ? 'left:50%' : 'right:50%'};width:${w}%;background:var(--${pos ? 'red' : 'green'})"></i><em style="${pos ? 'left:calc(50% + ' + w + '% + 6px)' : 'right:calc(50% + ' + w + '% + 6px)'}">${signe(m.valeur)}</em></div>`; }).join('');
      $('#t-res').innerHTML = `<div class="g" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:24px">
        <div><div class="lbl">Risque d'insatisfaction</div><div style="display:flex;align-items:baseline;gap:10px"><span class="num" style="font-size:30px;font-weight:600">${fr(r.risque * 100)} %</span><span class="b ${haut ? 'b-ko' : 'b-ok'}">${haut ? 'Au-dessus du seuil' : 'Sous le seuil'}</span></div>
          <div class="meter"><i data-w="${(r.risque * 100).toFixed(1)}%" style="background:var(--${haut ? 'red' : 'green'})"></i><u style="left:${(r.seuil * 100).toFixed(1)}%"></u></div><div class="note">Trait : seuil d'alerte (${fr(r.seuil * 100)} %)</div>
          <div class="div"></div><div class="lbl">Note prévue</div><div class="num" style="font-size:24px;font-weight:600">${fr(r.note_prevue, 1)}<small style="font-size:14px;color:var(--muted);font-weight:500"> / 5</small></div></div>
        <div><div class="lbl" style="margin-bottom:8px">Ce qui pèse dans la décision</div>${ton ? `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;background:var(--surface2);margin-bottom:10px;font-size:13px"><span>Ton général de l'avis (modèle de sentiment)</span><span class="b ${ton.valeur > 0 ? 'b-ko' : 'b-ok'}">${ton.valeur > 0 ? 'négatif' : 'positif'}</span></div>` : ''}<div class="shap">${shap}</div><div class="note" style="margin-top:8px">Rouge : augmente le risque. Vert : le réduit.</div></div></div>`;
      animerNombres($('#t-res'));
    } catch (e) { $('#t-res').innerHTML = messageErreur(e); }
    $('#t-go').disabled = false;
  };
  $('#t-go').onclick = go; go();
};

// =========================================================== PLAN D'ACTIONS
RENDU.plan = async function () {
  const j = ++jeton;
  base('Plan d\'actions', 'L\'IA propose, un responsable décide. Tout est enregistré dans un journal.');
  $('#tools').insertAdjacentHTML('afterbegin', `<button class="btn" id="b-prop">${ico('plus', 15, 2.2)}<span>Proposer des actions</span></button>`);
  $('#b-prop').onclick = proposer;
  contenu(chargement());
  let d;
  try { d = await api('/api/plan?' + qs()); } catch (e) { if (j === jeton) contenu(messageErreur(e)); return; }
  if (j !== jeton) return;
  const col = (titre, statut, classe) => {
    const l = d.actions.filter(a => a.statut === statut);
    return `<div class="col s4"><div class="cth"><span>${titre}</span><span class="b ${classe}">${l.length}</span></div>${l.length ? l.map(carteAction).join('') : '<div class="vide">Aucune action</div>'}</div>`;
  };
  const refusees = d.actions.filter(a => a.statut === 'Refusée').length;
  contenu(`
  <div class="g">${col('À valider', 'À valider', 'b-mid')}${col('En cours', 'En cours', 'b-info')}${col('Terminé', 'Terminé', 'b-ok')}</div>
  <p class="note" style="margin:-4px 0 0">${d.actions.length ? `Actions générées à partir des priorités de l'écran « Thèmes ». Effort et coûts indicatifs, à ajuster avec les directions concernées.${refusees ? ` ${refusees} action${refusees > 1 ? 's' : ''} refusée${refusees > 1 ? 's' : ''} (conservée${refusees > 1 ? 's' : ''} dans le journal).` : ''}` : 'Aucune action pour l\'instant : cliquez sur « Proposer des actions » (l\'IA propose, vous décidez).'}</p>
  <div class="g">
    ${carte('Simulateur', 'Effet estimé de la correction d\'un sujet, d\'après le lien observé entre commentaires négatifs et note', `
      <div class="sl"><div class="h"><span>Sujet à corriger</span></div><select id="s-asp" class="field" aria-label="Sujet">${d.aspects.map(a => `<option>${esc(a)}</option>`).join('')}</select></div>
      <div class="sl"><div class="h"><span>Part des commentaires négatifs corrigés</span><em id="v-part">50 %</em></div><input type="range" id="s-part" min="10" max="100" step="10" value="50"></div>
      <div class="sl"><div class="h"><span>Coût de l'action (DH)</span></div><input type="number" id="s-cout" class="field" value="180000" min="0" step="10000"></div>
      <div id="s-res" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px"></div>
      <p class="note" style="margin:12px 0 0">Corrélation, pas certitude : à valider par la direction.</p>`, 's6')}
    ${carte('Expérience chronométrée', 'Chaque testeur analyse le même lot d\'avis à la main, puis avec VoxCX', `
      <div id="exp">${d.experience.map((x, i) => `<div class="tt" data-i="${i}"><span class="n">${esc(x.testeur)}</span><label>À la main (min)<input class="field" type="number" min="0" step="1" data-k="main" value="${x.main ?? ''}"></label><label>Avec l'outil (min)<input class="field" type="number" min="0" step="1" data-k="outil" value="${x.outil ?? ''}"></label></div>`).join('')}</div>
      <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:12px"><button class="btn-s" id="exp-ok">Enregistrer</button><span id="exp-res" class="note"></span></div>
      <p class="note" style="margin:12px 0 0">Aucune valeur n'est inventée : les chiffres viendront de la vraie expérience, à citer dans le rapport.</p>`, 's6')}
  </div>
  ${carte('Journal de gouvernance de l\'IA', 'Qui a proposé, qui a décidé, et quand', d.journal.length ? d.journal.map(x => `<div class="jr"><span class="d">${esc(x.date)}</span><span class="w2">${esc(x.detail || x.evenement)}</span><span class="b ${x.auteur === 'IA' ? 'b-info' : 'b-ok'}">${esc(x.auteur)}</span></div>`).join('') : '<div class="vide">Le journal se remplit au fil des questions, recommandations et décisions.</div>')}`);
  cascade($('#contenu'));
  $$('[data-act]').forEach(b => b.onclick = async () => { await api('/api/plan/statut', { id: +b.dataset.id, statut: b.dataset.act }); toast('Décision enregistrée dans le journal.'); RENDU.plan(); });
  const sim = async () => {
    $('#v-part').textContent = $('#s-part').value + ' %';
    if (!$('#s-asp').value) { $('#s-res').innerHTML = '<div class="vide" style="grid-column:span 3">Pas assez de commentaires négatifs pour simuler.</div>'; return; }
    try {
      const r = await api('/api/simulateur?' + qs(), { aspect: $('#s-asp').value, part: +$('#s-part').value, cout: +$('#s-cout').value });
      $('#s-res').innerHTML = r.ok ? `<div class="res"><span class="lbl">Gain de note</span><span class="v" style="color:var(--green)"><span data-n="${r.gain}" data-pre="+" data-d="3">${r.gain}</span></span><span class="note">étoile sur la moyenne</span></div>
        <div class="res"><span class="lbl">Évités</span><span class="v"><span data-n="${r.evites}" data-d="0">${r.evites}</span></span><span class="note">sur ${fr(r.observes)} commentaires négatifs</span></div>
        <div class="res"><span class="lbl">Coût unitaire</span><span class="v"><span data-n="${r.cout_par_evite}" data-d="0">${r.cout_par_evite}</span><small style="font-size:12px;color:var(--muted);font-weight:500"> DH</small></span><span class="note">par commentaire évité</span></div>` : '<div class="vide" style="grid-column:span 3">Simulation indisponible pour ce sujet.</div>';
      animerNombres($('#s-res'));
    } catch (e) { $('#s-res').innerHTML = messageErreur(e); }
  };
  ['s-asp', 's-part', 's-cout'].forEach(id => $('#' + id).addEventListener('input', () => { clearTimeout(sim.t); sim.t = setTimeout(sim, 250); }));
  sim();
  const resume = () => {
    const l = $$('.tt', $('#exp')).map(r => ({ m: parseFloat($('[data-k=main]', r).value), o: parseFloat($('[data-k=outil]', r).value) })).filter(x => x.m > 0 && x.o >= 0);
    const m = l.reduce((s, x) => s + x.m, 0) / (l.length || 1), o = l.reduce((s, x) => s + x.o, 0) / (l.length || 1);
    $('#exp-res').innerHTML = l.length ? `À la main <b>${fr(m)} min</b> · avec l'outil <b>${fr(o)} min</b> · temps gagné <b style="color:var(--green)">${fr(100 * (1 - o / m))} %</b> (${l.length} testeur${l.length > 1 ? 's' : ''})` : '';
  };
  $$('#exp input').forEach(i => i.addEventListener('input', resume)); resume();
  $('#exp-ok').onclick = async () => {
    const lignes = $$('.tt', $('#exp')).map((r, i) => ({ testeur: d.experience[i].testeur, avis: d.experience[i].avis, main: $('[data-k=main]', r).value, outil: $('[data-k=outil]', r).value }));
    await api('/api/experience', { lignes }); toast('Expérience enregistrée.');
  };
};
function carteAction(a) {
  const boutons = a.statut === 'À valider' ? `<button class="btn2 g" data-act="En cours" data-id="${a.id}">Valider</button><button class="btn2 r" data-act="Refusée" data-id="${a.id}">Refuser</button>`
    : a.statut === 'En cours' ? `<button class="btn2 g" data-act="Terminé" data-id="${a.id}">Marquer terminé</button>` : '';
  const niveau = a.priorite == null ? '' : `<span class="b ${a.priorite >= 66 ? 'b-ko' : a.priorite >= 33 ? 'b-mid' : 'b-info'}" style="align-self:flex-start">Priorité ${a.priorite} · ${esc(a.aspect)}</span>`;
  return `<div class="ac"><b>${esc(a.quoi)}</b><div class="m"><span>${esc(a.ou)}</span><span>${esc(a.qui)}</span><span>${esc(a.quand)}</span><span class="num">${fr(a.cout)} DH</span></div>${niveau}<span class="note">Objectif : ${esc(a.kpi)}</span>${boutons ? `<div class="bt">${boutons}</div>` : ''}</div>`;
}
async function proposer() {
  const b = $('#b-prop'); b.disabled = true;
  try { const r = await api('/api/plan/proposer?' + qs(), {}); toast(r.ajoutees ? `${r.ajoutees} action${r.ajoutees > 1 ? 's' : ''} proposée${r.ajoutees > 1 ? 's' : ''} : à valider.` : 'Toutes les priorités ont déjà une action.'); RENDU.plan(); }
  catch (e) { toast('Erreur : ' + e.message); b.disabled = false; }
}
