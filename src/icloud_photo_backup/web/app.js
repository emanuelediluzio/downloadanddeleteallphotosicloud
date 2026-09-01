// Interfaccia web di iCloud Photo Backup & Cleaner
"use strict";

const TOKEN = new URLSearchParams(location.search).get("t") || "";

const griglia = document.getElementById("griglia");
const contatore = document.getElementById("contatore");
const banda = document.getElementById("banda");

let elementi = [];            // elementi attualmente mostrati
let selezionati = new Set();  // id selezionati
let ultimoCliccato = null;    // per la selezione con Shift

// ---------------------------------------------------------------- utilità
async function chiamaApi(percorso, opzioni = {}) {
  const risposta = await fetch(percorso, {
    ...opzioni,
    headers: { "X-Token": TOKEN, ...(opzioni.headers || {}) },
  });
  if (!risposta.ok) throw new Error(`Errore ${risposta.status}`);
  return risposta.json();
}

function aggiornaContatore() {
  const n = selezionati.size;
  contatore.textContent = n === 1 ? "1 selezionato" : `${n} selezionati`;
  document.getElementById("btn-scarica").disabled = n === 0;
  document.getElementById("btn-elimina").disabled = n === 0;
}

// ------------------------------------------------------- caricamento dati
async function caricaElementi() {
  const da = document.getElementById("data-da").value;
  const a = document.getElementById("data-a").value;
  const tipo = document.getElementById("tipo").value;

  const parametri = new URLSearchParams({ tipo });
  if (da) parametri.set("da", da);
  if (a) parametri.set("a", a);

  griglia.innerHTML = '<div class="vuoto">Caricamento…</div>';
  const dati = await chiamaApi(`/api/elementi?${parametri}`);
  elementi = dati.elementi;
  selezionati.clear();
  ultimoCliccato = null;
  disegnaGriglia();
  aggiornaContatore();
}

function disegnaGriglia() {
  if (!elementi.length) {
    griglia.innerHTML = '<div class="vuoto">Nessun elemento corrisponde ai filtri scelti.</div>';
    return;
  }

  griglia.innerHTML = "";
  const frammento = document.createDocumentFragment();

  elementi.forEach((el, posizione) => {
    const cella = document.createElement("div");
    cella.className = "cella";
    cella.dataset.id = el.id;
    cella.dataset.posizione = posizione;

    const img = document.createElement("img");
    img.loading = "lazy";
    img.dataset.src = `/api/miniatura/${el.id}?t=${encodeURIComponent(TOKEN)}`;
    img.alt = el.nome;
    cella.appendChild(img);

    if (el.tipo === "video") {
      const segno = document.createElement("button");
      segno.type = "button";
      segno.className = "segno-video";
      segno.title = "Riproduci l'anteprima";
      segno.textContent = "▶ video";
      segno.dataset.id = el.id;
      cella.appendChild(segno);
    }

    const etichetta = document.createElement("div");
    etichetta.className = "etichetta";
    etichetta.innerHTML =
      `<span class="nome"></span><span class="data"></span>`;
    etichetta.querySelector(".nome").textContent = el.nome;
    etichetta.querySelector(".data").textContent = el.data_breve;
    cella.appendChild(etichetta);

    frammento.appendChild(cella);
  });

  griglia.appendChild(frammento);
  avviaCaricamentoPigro();
}

// Le miniature si scaricano solo quando entrano nello schermo
function avviaCaricamentoPigro() {
  const osservatore = new IntersectionObserver((voci) => {
    voci.forEach((voce) => {
      if (!voce.isIntersecting) return;
      const img = voce.target;
      if (img.dataset.src) {
        img.src = img.dataset.src;
        delete img.dataset.src;
        img.onload = () => img.classList.add("visibile");
        img.onerror = () => { img.alt = "⚠️"; };
      }
      osservatore.unobserve(img);
    });
  }, { rootMargin: "300px" });

  griglia.querySelectorAll("img[data-src]").forEach((img) => osservatore.observe(img));
}

// ------------------------------------------------------------- selezione
function applicaClassi() {
  griglia.querySelectorAll(".cella").forEach((cella) => {
    cella.classList.toggle("selezionata", selezionati.has(Number(cella.dataset.id)));
  });
  aggiornaContatore();
}

griglia.addEventListener("click", (evento) => {
  const bottoneVideo = evento.target.closest(".segno-video");
  if (bottoneVideo) {
    evento.stopPropagation();
    apriAnteprimaVideo(Number(bottoneVideo.dataset.id));
    return;
  }

  const cella = evento.target.closest(".cella");
  if (!cella) return;

  const id = Number(cella.dataset.id);
  const posizione = Number(cella.dataset.posizione);

  if (evento.shiftKey && ultimoCliccato !== null) {
    // Selezione di un intervallo continuo
    const [inizio, fine] = [ultimoCliccato, posizione].sort((x, y) => x - y);
    for (let i = inizio; i <= fine; i++) selezionati.add(elementi[i].id);
  } else if (evento.ctrlKey || evento.metaKey) {
    selezionati.has(id) ? selezionati.delete(id) : selezionati.add(id);
    ultimoCliccato = posizione;
  } else {
    selezionati.has(id) ? selezionati.delete(id) : selezionati.add(id);
    ultimoCliccato = posizione;
  }

  applicaClassi();
});

// Selezione trascinando un rettangolo sullo sfondo
let trascinamento = null;

griglia.addEventListener("mousedown", (evento) => {
  if (evento.button !== 0) return;
  if (evento.target.closest(".cella")) return; // sulle celle vince il click

  trascinamento = {
    x: evento.pageX,
    y: evento.pageY,
    aggiunge: evento.shiftKey || evento.ctrlKey || evento.metaKey,
    inizialiSelezionati: new Set(selezionati),
  };
  banda.hidden = false;
  evento.preventDefault();
});

window.addEventListener("mousemove", (evento) => {
  if (!trascinamento) return;

  const x = Math.min(trascinamento.x, evento.pageX);
  const y = Math.min(trascinamento.y, evento.pageY);
  const larghezza = Math.abs(evento.pageX - trascinamento.x);
  const altezza = Math.abs(evento.pageY - trascinamento.y);

  Object.assign(banda.style, {
    left: `${x}px`, top: `${y}px`,
    width: `${larghezza}px`, height: `${altezza}px`,
  });

  const rettangolo = { sinistra: x, alto: y, destra: x + larghezza, basso: y + altezza };
  selezionati = new Set(trascinamento.aggiunge ? trascinamento.inizialiSelezionati : []);

  griglia.querySelectorAll(".cella").forEach((cella) => {
    const r = cella.getBoundingClientRect();
    const cellaRett = {
      sinistra: r.left + scrollX, alto: r.top + scrollY,
      destra: r.right + scrollX, basso: r.bottom + scrollY,
    };
    const siIntersecano =
      cellaRett.sinistra < rettangolo.destra && cellaRett.destra > rettangolo.sinistra &&
      cellaRett.alto < rettangolo.basso && cellaRett.basso > rettangolo.alto;
    if (siIntersecano) selezionati.add(Number(cella.dataset.id));
  });

  applicaClassi();
});

window.addEventListener("mouseup", () => {
  if (!trascinamento) return;
  trascinamento = null;
  banda.hidden = true;
});

// Ctrl+A / Cmd+A per selezionare tutto
window.addEventListener("keydown", (evento) => {
  if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === "a") {
    evento.preventDefault();
    selezionaTutti();
  }
  if (evento.key === "Escape") {
    selezionati.clear();
    applicaClassi();
  }
});

function selezionaTutti() {
  elementi.forEach((el) => selezionati.add(el.id));
  applicaClassi();
}

// -------------------------------------------------------------- comandi
document.getElementById("btn-filtra").addEventListener("click", caricaElementi);

document.getElementById("btn-azzera").addEventListener("click", () => {
  document.getElementById("data-da").value = "";
  document.getElementById("data-a").value = "";
  document.getElementById("tipo").value = "tutti";
  caricaElementi();
});

document.getElementById("btn-tutti").addEventListener("click", selezionaTutti);

document.getElementById("btn-nessuno").addEventListener("click", () => {
  selezionati.clear();
  applicaClassi();
});

document.getElementById("btn-scarica").addEventListener("click", () => {
  avviaOperazione("scarica");
});

// --- eliminazione con doppia conferma ---
const modaleElimina = document.getElementById("modale-elimina");
const spuntaElimina = document.getElementById("modale-spunta");
const confermaElimina = document.getElementById("modale-conferma");

document.getElementById("btn-elimina").addEventListener("click", () => {
  document.getElementById("modale-quanti").textContent = selezionati.size;
  spuntaElimina.checked = false;
  confermaElimina.disabled = true;
  modaleElimina.hidden = false;
});

spuntaElimina.addEventListener("change", () => {
  confermaElimina.disabled = !spuntaElimina.checked;
});

document.getElementById("modale-annulla").addEventListener("click", () => {
  modaleElimina.hidden = true;
});

confermaElimina.addEventListener("click", () => {
  modaleElimina.hidden = true;
  avviaOperazione("elimina");
});

// ------------------------------------------------------------- upload
document.getElementById("btn-carica").addEventListener("click", () => {
  document.getElementById("input-file").click();
});

document.getElementById("input-file").addEventListener("change", async (evento) => {
  await caricaFile([...evento.target.files]);
  evento.target.value = "";
});

async function caricaFile(listaFile) {
  if (!listaFile.length) return;

  const modulo = new FormData();
  listaFile.forEach((f) => modulo.append("file", f));

  mostraAvanzamento("Caricamento su iCloud", listaFile.length);
  aggiornaAvanzamento(0, listaFile.length, "Invio in corso…");

  try {
    const esito = await chiamaApi("/api/carica", { method: "POST", body: modulo });
    aggiornaAvanzamento(listaFile.length, listaFile.length, "");
    const messaggi = [
      `Caricati: ${esito.caricati.length}`,
      ...esito.falliti.map((f) => `Fallito ${f.nome}: ${f.errore}`),
    ];
    scriviMessaggi(messaggi);
  } catch (e) {
    scriviMessaggi([`Errore: ${e.message}`]);
  }

  document.getElementById("avanzamento-chiudi").hidden = false;
}

// --- trascina-e-rilascia: trascina i file ovunque nella pagina per caricarli ---
const zonaTrascinamento = document.getElementById("zona-trascinamento");
let contatoreTrascinamento = 0; // dragenter/dragleave si accavallano sui figli, serve un contatore

function eventoContieneFile(evento) {
  return evento.dataTransfer && [...evento.dataTransfer.types].includes("Files");
}

window.addEventListener("dragenter", (evento) => {
  if (!eventoContieneFile(evento)) return;
  evento.preventDefault();
  contatoreTrascinamento++;
  zonaTrascinamento.hidden = false;
});

window.addEventListener("dragover", (evento) => {
  if (!eventoContieneFile(evento)) return;
  evento.preventDefault(); // necessario per permettere il drop
});

window.addEventListener("dragleave", (evento) => {
  if (!eventoContieneFile(evento)) return;
  contatoreTrascinamento = Math.max(0, contatoreTrascinamento - 1);
  if (contatoreTrascinamento === 0) zonaTrascinamento.hidden = true;
});

window.addEventListener("drop", async (evento) => {
  if (!eventoContieneFile(evento)) return;
  evento.preventDefault();
  contatoreTrascinamento = 0;
  zonaTrascinamento.hidden = true;
  await caricaFile([...evento.dataTransfer.files]);
});

// -------------------------------------------------- operazioni lunghe
const modaleAvanzamento = document.getElementById("modale-avanzamento");

function mostraAvanzamento(titolo, totale) {
  document.getElementById("avanzamento-titolo").textContent = titolo;
  document.getElementById("avanzamento-messaggi").innerHTML = "";
  document.getElementById("avanzamento-chiudi").hidden = true;
  aggiornaAvanzamento(0, totale, "");
  modaleAvanzamento.hidden = false;
}

function aggiornaAvanzamento(fatti, totale, corrente) {
  const percentuale = totale ? (fatti / totale) * 100 : 0;
  document.getElementById("avanzamento-barra").style.width = `${percentuale}%`;
  document.getElementById("avanzamento-testo").textContent = `${fatti} / ${totale}`;
  document.getElementById("avanzamento-corrente").textContent = corrente || "";
}

function scriviMessaggi(messaggi) {
  const contenitore = document.getElementById("avanzamento-messaggi");
  contenitore.innerHTML = "";
  messaggi.slice(-40).forEach((m) => {
    const riga = document.createElement("div");
    riga.textContent = m;
    contenitore.appendChild(riga);
  });
  contenitore.scrollTop = contenitore.scrollHeight;
}

async function avviaOperazione(azione) {
  const ids = [...selezionati];
  const titolo = azione === "scarica" ? "Scaricamento in corso" : "Eliminazione da iCloud";
  mostraAvanzamento(titolo, ids.length);

  let risposta;
  try {
    risposta = await chiamaApi("/api/operazione", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ azione, ids, conferma: azione === "elimina" ? true : undefined }),
    });
  } catch (e) {
    scriviMessaggi([`Errore: ${e.message}`]);
    document.getElementById("avanzamento-chiudi").hidden = false;
    return;
  }

  const timer = setInterval(async () => {
    let stato;
    try {
      stato = await chiamaApi(`/api/operazione/${risposta.id}`);
    } catch {
      return;
    }

    aggiornaAvanzamento(stato.fatti, stato.totale, stato.corrente);
    if (stato.messaggi.length) scriviMessaggi(stato.messaggi);

    if (stato.finita) {
      clearInterval(timer);
      const riepilogo = [
        `Completati: ${stato.riusciti}`,
        stato.saltati ? `Già presenti: ${stato.saltati}` : null,
        stato.falliti ? `Falliti: ${stato.falliti}` : null,
      ].filter(Boolean);
      scriviMessaggi([...stato.messaggi, "———", ...riepilogo]);
      document.getElementById("avanzamento-chiudi").hidden = false;
      if (azione === "elimina") caricaElementi();
    }
  }, 600);
}

document.getElementById("avanzamento-chiudi").addEventListener("click", () => {
  modaleAvanzamento.hidden = true;
});

// ------------------------------------------------------- anteprima video
const modaleVideo = document.getElementById("modale-video");
const playerVideo = document.getElementById("player-video");
const videoErrore = document.getElementById("video-errore");

function apriAnteprimaVideo(id) {
  videoErrore.hidden = true;
  playerVideo.hidden = false;
  playerVideo.src = `/api/video/${id}?t=${encodeURIComponent(TOKEN)}`;
  modaleVideo.hidden = false;
  playerVideo.play().catch(() => {}); // l'autoplay puo' essere bloccato dal browser, non e' un errore
}

function chiudiAnteprimaVideo() {
  playerVideo.pause();
  playerVideo.removeAttribute("src");
  playerVideo.load();
  modaleVideo.hidden = true;
}

playerVideo.addEventListener("error", () => {
  playerVideo.hidden = true;
  videoErrore.hidden = false;
});

document.getElementById("video-chiudi").addEventListener("click", chiudiAnteprimaVideo);

modaleVideo.addEventListener("click", (evento) => {
  if (evento.target === modaleVideo) chiudiAnteprimaVideo(); // click sullo sfondo
});

// ---------------------------------------------------------------- avvio
(async function inizializza() {
  try {
    const info = await chiamaApi("/api/stato");
    document.getElementById("sottotitolo").textContent =
      `${info.totale} elementi su iCloud · destinazione: ${info.destinazione}`;
    await caricaElementi();
  } catch (e) {
    document.getElementById("messaggio-vuoto").textContent =
      "Impossibile contattare il server. Riapri il link mostrato nel terminale.";
  }
})();
