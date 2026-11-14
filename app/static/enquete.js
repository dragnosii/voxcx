"use strict";
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const jeton = location.pathname.split("/").pop();
const z = $("#enquete");
let note = 0, etab = null;

async function demarrer() {
  try {
    const r = await fetch(`/api/public/enquete/${encodeURIComponent(jeton)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.erreur || "Lien invalide.");
    etab = d; formulaire();
  } catch (e) { z.innerHTML = `<div class="vide"><p>${esc(e.message)}</p></div>`; }
}

function formulaire() {
  z.innerHTML = `
    <div><p class="discret">${esc(etab.type)} · ${esc(etab.ville)}</p><h1>Comment s'est passée votre visite chez ${esc(etab.nom)} ?</h1></div>
    <form class="form" id="f" novalidate>
      <fieldset style="border:0;padding:0;margin:0;display:grid;gap:8px"><legend class="second" style="margin-bottom:8px">Votre note</legend>
        <div class="notes" role="group" aria-label="Note de 1 à 5">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-n="${n}" aria-pressed="false">${n}</button>`).join("")}</div>
        <div class="notes-leg"><span>Pas du tout satisfait</span><span>Très satisfait</span></div></fieldset>
      <label class="champ" for="c">Dites-nous en plus (facultatif)</label>
      <textarea id="c" rows="4" maxlength="1500" placeholder="Ce qui vous a plu, ce qui peut être amélioré…"></textarea>
      <label class="coche"><input type="checkbox" id="ok"> J'accepte que l'établissement me recontacte au sujet de ma visite.</label>
      <label class="champ" id="z-contact" hidden>Téléphone ou e-mail<input type="text" id="contact" maxlength="120" autocomplete="tel"></label>
      <p class="erreur" id="err" role="alert"></p>
      <button class="btn plein" type="submit">Envoyer mon avis</button>
      <p class="discret">Vos réponses servent uniquement à améliorer l'accueil de cet établissement. Elles ne sont ni vendues ni publiées.</p>
    </form>`;
}

z.addEventListener("click", (e) => {
  const b = e.target.closest("[data-n]"); if (!b) return;
  note = +b.dataset.n;
  z.querySelectorAll("[data-n]").forEach((x) => x.setAttribute("aria-pressed", x === b));
});
z.addEventListener("change", (e) => { if (e.target.id === "ok") $("#z-contact").hidden = !e.target.checked; });
z.addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = $("#err"); err.textContent = "";
  if (!note) { err.textContent = "Choisissez une note de 1 à 5."; return; }
  const corps = { note, commentaire: $("#c").value.trim(), consentement: $("#ok").checked, contact: $("#contact").value.trim() };
  const bouton = z.querySelector('button[type="submit"]'); bouton.disabled = true;
  try {
    const r = await fetch(`/api/public/enquete/${encodeURIComponent(jeton)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.erreur || "Envoi impossible. Réessayez.");
    if (d.resultat === "content") {
      z.innerHTML = `<div class="merci"><div class="rond" aria-hidden="true">✓</div><h1>Merci beaucoup !</h1>
        <p class="second">Votre avis fait plaisir à toute l'équipe de ${esc(etab.nom)}.</p>
        ${d.lien_avis ? `<p>Vous avez 30 secondes ? Partagez-le sur Google, cela aide énormément.</p><a class="btn plein" href="${esc(d.lien_avis)}" rel="noopener noreferrer">Publier mon avis sur Google</a>` : ""}</div>`;
    } else {
      z.innerHTML = `<div class="merci"><div class="rond" aria-hidden="true">✓</div><h1>Merci pour votre franchise</h1>
        <p class="second">${corps.consentement && corps.contact ? "Le responsable a été prévenu et va vous recontacter rapidement." : "Le responsable a été prévenu et va en tenir compte."}</p></div>`;
    }
  } catch (x) { err.textContent = x.message; bouton.disabled = false; }
});

demarrer();
