/* Tela: foto → IMEIs → conferência → impressão (agora ou pela fila). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const CHAVE_FILA = "etiquetas-imei-fila";
  const CHAVE_AUTO = "etiquetas-imei-auto";
  let cfg = null;
  let fila = [];

  // ---------- utilidades ----------
  const ler = (k, padrao) => { try { const v = localStorage.getItem(k); return v == null ? padrao : JSON.parse(v); } catch (_) { return padrao; } };
  const gravar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* sem armazenamento */ } };
  const digitos = (s) => String(s || "").replace(/\D/g, "");

  let toastTimer;
  function aviso(msg, erro) {
    const t = $("toast");
    t.textContent = msg; t.className = "toast" + (erro ? " erro" : ""); t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), erro ? 6000 : 3000);
  }

  async function api(rota, corpo) {
    const op = corpo === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
    let r;
    try { r = await fetch(rota, op); } catch (_) { throw new Error("Sem conexão com o programa no computador. Ele está aberto?"); }
    const d = await r.json().catch(() => ({ ok: false, erro: "Resposta inválida do servidor." }));
    if (!d.ok) throw new Error(d.erro || "Erro");
    return d;
  }

  // ---------- campos de IMEI ----------
  function validar(n) {
    const campo = $("imei" + n), dica = $("dica" + n);
    const v = digitos(campo.value);
    campo.classList.remove("valido", "invalido"); dica.className = "dica"; dica.textContent = "";
    if (!v) return n === 2 || false;
    if (v.length !== 15) {
      campo.classList.add("invalido"); dica.classList.add("bad");
      dica.textContent = `${v.length} dígitos — o IMEI tem 15.`;
      return false;
    }
    if (!Leitor.luhn(v)) {
      campo.classList.add("invalido"); dica.classList.add("warn");
      dica.textContent = "Dígito verificador não confere. Confira o número (dá para imprimir mesmo assim).";
      return true;
    }
    campo.classList.add("valido"); dica.classList.add("ok"); dica.textContent = "IMEI válido ✓";
    return true;
  }

  function itemAtual() {
    return {
      imei1: digitos($("imei1").value), imei2: digitos($("imei2").value),
      descricao: $("descricao").value.trim(), copias: Math.max(1, parseInt($("copias").value, 10) || 1),
    };
  }

  function conferir(item) {
    const ok1 = validar(1), ok2 = validar(2);
    if (!item.imei1 && !item.imei2) { aviso("Leia ou digite pelo menos um IMEI.", true); return false; }
    if (!ok1 || !ok2) { aviso("Corrija o IMEI marcado em vermelho.", true); return false; }
    return true;
  }

  function limparCampos() {
    $("imei1").value = ""; $("imei2").value = ""; $("copias").value = "1";
    validar(1); validar(2); $("fotoBox").hidden = true; previa();
  }

  function preencher(imeis) {
    $("imei1").value = imeis[0] || ""; $("imei2").value = imeis[1] || "";
    validar(1); validar(2); previa();
  }

  // ---------- foto ----------
  async function processarFoto(arquivo) {
    if (!arquivo) return;
    const st = $("status"), barra = $("barra"), prog = barra.firstElementChild;
    ["btnFoto", "btnGaleria", "btnCamera"].forEach((id) => ($(id).disabled = true));
    barra.hidden = false; prog.style.width = "0";
    try {
      const r = await Leitor.lerFoto(arquivo, (txt, p) => { st.textContent = txt; prog.style.width = Math.round(p * 100) + "%"; });
      $("miniatura").src = r.miniatura; $("fotoBox").hidden = false;
      const chips = $("chips"); chips.innerHTML = "";
      if (!r.imeis.length) {
        st.textContent = "Não achei IMEI nesta foto. Tente mais perto, com a etiqueta reta e bem iluminada (sem reflexo), ou digite.";
        $("achadosTxt").textContent = "Nenhum IMEI encontrado.";
        return;
      }
      preencher(r.imeis);
      $("achadosTxt").textContent = `${r.imeis.length} IMEI(s) por ${r.metodo}` + (r.imeis.length > 2 ? " — toque para escolher:" : ":");
      r.imeis.forEach((n) => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "chip"; b.textContent = n; b.title = "Toque para usar como IMEI 1; segure Shift (ou toque de novo) para IMEI 2";
        b.onclick = (ev) => {
          const alvo = ev.shiftKey || digitos($("imei1").value) === n ? 2 : 1;
          $("imei" + alvo).value = n; validar(alvo); previa();
        };
        chips.appendChild(b);
      });
      if (r.imeis.length === 1) {
        st.textContent = "Achei só 1 IMEI. Se o celular tiver 2, tire outra foto mais de perto ou digite o segundo.";
      } else {
        st.textContent = "Pronto! Confira os números ao lado.";
        if ($("auto").checked && r.imeis.length === 2) imprimirAgora();
      }
    } catch (e) {
      st.textContent = e.message || String(e);
    } finally {
      barra.hidden = true;
      ["btnFoto", "btnGaleria", "btnCamera"].forEach((id) => ($(id).disabled = false));
    }
  }

  // Câmera ao vivo (só funciona em localhost ou HTTPS — útil no computador com webcam)
  let stream = null;
  async function abrirCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } } });
      $("video").srcObject = stream; await $("video").play(); $("camBox").hidden = false;
    } catch (e) { aviso("Não consegui abrir a câmera: " + e.message, true); }
  }
  function fecharCamera() {
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null; $("camBox").hidden = true;
  }
  function capturar() {
    const v = $("video"), c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    c.toBlob((b) => processarFoto(b), "image/jpeg", 0.95);
  }

  // ---------- impressão ----------
  // --- Pelo computador: monta as etiquetas em milímetros e abre a janela de impressão ---
  const svgNS = "http://www.w3.org/2000/svg";
  function elemento(pai, esq, topo, larg, alt, filho) {
    const d = document.createElement("div"); d.className = "el";
    Object.assign(d.style, { left: esq + "mm", top: topo + "mm", width: larg + "mm", height: alt + "mm" });
    if (typeof filho === "string") { d.textContent = filho; d.style.fontSize = alt + "mm"; } else d.appendChild(filho);
    pai.appendChild(d);
  }
  function codigoBarras(num, largMax, alt) {
    const svg = document.createElementNS(svgNS, "svg");
    JsBarcode(svg, num, { format: "CODE128", width: 1, height: 10, displayValue: false, margin: 0, background: "#ffffff" });
    const modulos = parseFloat(svg.getAttribute("width"));
    const modMm = Math.min(0.25, largMax / modulos); // 0,25 mm = 2 pontos a 203 dpi ou 3 pontos a 300 dpi: barras nítidas
    svg.setAttribute("viewBox", `0 0 ${modulos} 10`); svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("width", modulos * modMm + "mm"); svg.setAttribute("height", alt + "mm");
    return { svg, larg: modulos * modMm };
  }
  function desenharEtiqueta(pai, e, x0, W, H) {
    const margem = Math.max(0.5, W * 0.03), area = W - 2 * margem, topo = H * 0.06;
    let y = topo;
    if (e.d) { const h = Math.max(1.5, H * 0.085); elemento(pai, x0 + margem, y, area, h, e.d); y += h + H * 0.03; }
    const n = e.linhas.length, hTxt = Math.max(1.5, H * 0.09), folga = H * 0.015, entre = H * 0.06;
    const hBarra = Math.max(2.5, (H - y - topo - entre * (n - 1)) / n - hTxt - folga);
    for (const [rot, num] of e.linhas) {
      const cb = codigoBarras(num, W * 0.92, hBarra);
      elemento(pai, x0 + (W - cb.larg) / 2, y, cb.larg, hBarra, cb.svg);
      y += hBarra + folga;
      elemento(pai, x0 + margem, y, area, hTxt, `${rot}: ${num}`);
      y += hTxt + entre;
    }
  }
  function imprimirNoComputador(itens) {
    const etqs = montarEtiquetas(itens, cfg.layout);
    if (!etqs.length) throw new Error("Nenhuma etiqueta para imprimir.");
    const cols = cfg.colunas, W = cfg.largura_mm, H = cfg.altura_mm, gap = cfg.espaco_colunas_mm;
    const larguraPag = cfg.margem_esquerda_mm + cols * W + (cols - 1) * gap;
    $("estiloPagina").textContent = `@page{size:${larguraPag}mm ${H}mm;margin:0}`;
    const box = $("impressao"); box.innerHTML = "";
    for (let i = 0; i < etqs.length; i += cols) {
      const pag = document.createElement("div"); pag.className = "pagina";
      Object.assign(pag.style, { width: larguraPag + "mm", height: H + "mm" });
      const conteudo = document.createElement("div"); conteudo.className = "el";
      Object.assign(conteudo.style, { left: 0, top: cfg.ajuste_vertical_mm + "mm", width: "100%", height: "100%", overflow: "visible" });
      for (let c = 0; c < cols && etqs[i + c]; c++) desenharEtiqueta(conteudo, etqs[i + c], cfg.margem_esquerda_mm + c * (W + gap), W, H);
      pag.appendChild(conteudo); box.appendChild(pag);
    }
    window.print();
    return etqs.length;
  }

  async function imprimir(itens, botao) {
    if (cfg && cfg.modo === "computador") {
      try { const n = imprimirNoComputador(itens); aviso(`${n} etiqueta(s) enviadas para a janela de impressão.`); return true; }
      catch (e) { aviso(e.message, true); return false; }
    }
    const txt = botao.textContent; botao.disabled = true; botao.textContent = "Enviando…";
    try {
      const r = await api("api/imprimir", { itens });
      aviso(`✓ ${r.etiquetas} etiqueta(s) ${r.destino}`);
      return true;
    } catch (e) { aviso(e.message, true); return false; }
    finally { botao.disabled = false; botao.textContent = txt; }
  }

  async function imprimirAgora() {
    const item = itemAtual();
    if (!conferir(item)) return;
    if (await imprimir([item], $("btnImprimir"))) {
      limparCampos();
      $("status").textContent = "Impresso. Pode fotografar a próxima caixa.";
    }
  }

  function adicionarFila() {
    const item = itemAtual();
    if (!conferir(item)) return;
    const repetido = fila.some((f) => (item.imei1 && (f.imei1 === item.imei1 || f.imei2 === item.imei1)));
    fila.push({ ...item, id: Date.now() + Math.random() });
    salvarFila(); limparCampos();
    aviso(repetido ? "Adicionado (atenção: esse IMEI já estava na fila)." : "Adicionado à fila.");
    $("status").textContent = "Pode fotografar a próxima caixa.";
  }

  function salvarFila() { gravar(CHAVE_FILA, fila); desenharFila(); previa(); }

  function desenharFila() {
    const ul = $("fila"); ul.innerHTML = "";
    const total = fila.reduce((s, f) => s + f.copias * (cfg && cfg.layout === "separado" && f.imei1 && f.imei2 ? 2 : 1), 0);
    $("filaQtd").textContent = fila.length ? `(${fila.length} celular(es), ${total} etiqueta(s))` : "";
    ["btnImprimirFila", "btnBaixar", "btnLimparFila"].forEach((id) => ($(id).disabled = !fila.length));
    if (!fila.length) { ul.innerHTML = '<li class="vazio">Nenhum celular na fila. Use “Adicionar à fila” para imprimir vários de uma vez.</li>'; return; }
    fila.forEach((f, i) => {
      const li = document.createElement("li");
      const nums = document.createElement("div"); nums.className = "nums";
      nums.innerHTML = `<div>${i + 1}. ${f.imei1 || "—"}</div><div>&nbsp;&nbsp;&nbsp;${f.imei2 || "—"}</div>`;
      if (f.descricao) { const d = document.createElement("div"); d.className = "desc"; d.textContent = f.descricao; nums.appendChild(d); }
      const acoes = document.createElement("div"); acoes.className = "linha"; acoes.style.flex = "0 0 auto";
      const qtd = document.createElement("input"); qtd.type = "number"; qtd.min = 1; qtd.value = f.copias; qtd.title = "Cópias";
      qtd.onchange = () => { f.copias = Math.max(1, parseInt(qtd.value, 10) || 1); salvarFila(); };
      const rem = document.createElement("button"); rem.textContent = "✕"; rem.title = "Tirar da fila";
      rem.onclick = () => { fila.splice(i, 1); salvarFila(); };
      acoes.append(qtd, rem); li.append(nums, acoes); ul.appendChild(li);
    });
  }

  async function baixarZpl() {
    try {
      const r = await api("api/zpl", { itens: fila });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([r.zpl], { type: "text/plain" }));
      a.download = "etiquetas-imei.txt"; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    } catch (e) { aviso(e.message, true); }
  }

  // ---------- prévia (aproximada; a impressão usa o ZPL do servidor) ----------
  function montarEtiquetas(itens, layout) {
    const lista = [];
    for (const it of itens) {
      let a = it.imei1, b = it.imei2;
      if (!a && b) { a = b; b = ""; }
      if (!a) continue;
      const grupo = layout === "separado"
        ? [{ linhas: [["IMEI 1", a]], d: it.descricao }].concat(b ? [{ linhas: [["IMEI 2", b]], d: it.descricao }] : [])
        : [{ linhas: b ? [["IMEI 1", a], ["IMEI 2", b]] : [["IMEI", a]], d: it.descricao }];
      for (let c = 0; c < (it.copias || 1); c++) lista.push(...grupo);
    }
    return lista;
  }

  function previa() {
    if (!cfg) return;
    const atual = itemAtual();
    const usarAtual = atual.imei1 || atual.imei2;
    const exemplo = { imei1: "490154203237518", imei2: "356938035643809", descricao: atual.descricao, copias: 1 };
    const itens = usarAtual ? [atual] : (fila.length ? fila : [exemplo]);
    const etqs = montarEtiquetas(itens, cfg.layout);
    const cols = cfg.colunas;
    const larguraMm = cfg.margem_esquerda_mm + cols * cfg.largura_mm + (cols - 1) * cfg.espaco_colunas_mm;
    const esc = Math.max(2.5, Math.min(5, ($("previa").clientWidth - 24) / larguraMm)); // px por mm, cabe no celular
    const W = cfg.largura_mm * esc, H = cfg.altura_mm * esc;
    const box = $("previa"); box.innerHTML = "";
    const fileiras = Math.min(3, Math.ceil(etqs.length / cols));
    for (let r = 0; r < fileiras; r++) {
      const f = document.createElement("div"); f.className = "fileira";
      f.style.gap = cfg.espaco_colunas_mm * esc + "px"; f.style.paddingLeft = cfg.margem_esquerda_mm * esc + "px";
      for (let c = 0; c < cols; c++) {
        const e = etqs[r * cols + c];
        const div = document.createElement("div"); div.className = "etq" + (e ? "" : " vazia");
        div.style.width = W + "px"; div.style.height = H + "px";
        if (e) {
          if (e.d) { const d = document.createElement("div"); d.className = "d"; d.textContent = e.d; div.appendChild(d); }
          div.style.fontSize = esc * 2 + "px";
          for (const [rot, num] of e.linhas) {
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            JsBarcode(svg, num, { format: "CODE128", width: 2, height: 50, displayValue: false, margin: 0 });
            svg.removeAttribute("width"); svg.removeAttribute("height"); svg.setAttribute("preserveAspectRatio", "none");
            svg.style.width = Math.round(W * 0.84) + "px";
            const t = document.createElement("div"); t.className = "t"; t.textContent = `${rot}: ${num}`;
            div.append(svg, t);
          }
        }
        f.appendChild(div);
      }
      box.appendChild(f);
    }
    const extra = Math.ceil(etqs.length / cols) - fileiras;
    $("previaTxt").textContent = (usarAtual ? "Celular na tela" : fila.length ? "Fila" : "Exemplo") +
      ` · ${cfg.largura_mm}×${cfg.altura_mm} mm, ${cols} coluna(s)` + (extra > 0 ? ` · +${extra} fileira(s)` : "");
    $("tamanho").textContent = `${cfg.largura_mm}×${cfg.altura_mm} mm, ${cols} coluna(s)`;
  }

  // ---------- configurações ----------
  function preencherCfg() {
    const form = $("cfg");
    for (const el of form.elements) if (el.name && cfg[el.name] !== undefined) el.value = cfg[el.name];
    const larg = cfg.margem_esquerda_mm + cfg.colunas * cfg.largura_mm + (cfg.colunas - 1) * cfg.espaco_colunas_mm;
    $("papelTxt").textContent = `${+larg.toFixed(1)}×${cfg.altura_mm} mm`;
    mostrarModo();
  }
  function mostrarModo() {
    const modo = $("cfg").elements.modo.value;
    $("cfg").querySelectorAll("[data-modo]").forEach((d) => (d.hidden = !d.dataset.modo.split(" ").includes(modo)));
  }
  async function salvarCfg() {
    const dados = {};
    for (const el of $("cfg").elements) if (el.name) dados[el.name] = el.value;
    try {
      cfg = (await api("api/config", { config: dados })).config;
      preencherCfg(); desenharFila(); previa(); aviso("Configurações salvas.");
    } catch (e) { aviso(e.message, true); }
  }
  async function carregarImpressoras() {
    try {
      const r = await api("api/impressoras");
      $("listaImpressoras").innerHTML = r.impressoras.map((n) => `<option value="${n.replace(/"/g, "&quot;")}">`).join("");
    } catch (_) { /* opcional */ }
  }

  // ---------- eventos ----------
  $("btnFoto").onclick = () => $("arquivo").click();
  $("btnGaleria").onclick = () => $("galeria").click();
  $("arquivo").onchange = (e) => { processarFoto(e.target.files[0]); e.target.value = ""; };
  $("galeria").onchange = (e) => { processarFoto(e.target.files[0]); e.target.value = ""; };
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia && !/Android|iPhone|iPad/i.test(navigator.userAgent)) {
    $("btnCamera").hidden = false;
  }
  $("btnCamera").onclick = abrirCamera;
  $("btnFecharCam").onclick = fecharCamera;
  $("btnCapturar").onclick = capturar;

  [1, 2].forEach((n) => {
    const campo = $("imei" + n);
    campo.addEventListener("input", () => {
      validar(n); previa();
      // Leitor USB ou digitação: ao completar 15 dígitos no IMEI 1, pula para o IMEI 2
      if (n === 1 && digitos(campo.value).length === 15 && document.activeElement === campo) $("imei2").focus();
    });
    campo.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      if (n === 1) $("imei2").focus(); else if (fila.length) adicionarFila(); else imprimirAgora();
    });
  });
  $("descricao").addEventListener("input", previa);
  $("copias").addEventListener("input", previa);
  $("btnInverter").onclick = () => { const a = $("imei1").value; $("imei1").value = $("imei2").value; $("imei2").value = a; validar(1); validar(2); previa(); };
  $("btnLimpar").onclick = limparCampos;
  $("btnImprimir").onclick = imprimirAgora;
  $("btnFila").onclick = adicionarFila;
  $("btnImprimirFila").onclick = async () => { if (await imprimir(fila, $("btnImprimirFila"))) { fila = []; salvarFila(); } };
  $("btnBaixar").onclick = baixarZpl;
  $("btnLimparFila").onclick = () => { if (confirm("Tirar todos os celulares da fila?")) { fila = []; salvarFila(); } };
  $("auto").checked = !!ler(CHAVE_AUTO, false);
  $("auto").onchange = () => gravar(CHAVE_AUTO, $("auto").checked);
  $("cfg").elements.modo.onchange = mostrarModo;
  $("cfg").addEventListener("change", salvarCfg); // salva sozinho a cada mudança
  $("btnSalvarCfg").onclick = salvarCfg;
  $("btnTeste").onclick = async () => {
    if (cfg.modo === "computador") {
      imprimirNoComputador([{ imei1: "490154203237518", imei2: "356938035643809", descricao: "TESTE DE IMPRESSAO", copias: cfg.layout === "par" ? cfg.colunas : 1 }]);
      return;
    }
    try { const r = await api("api/teste", {}); aviso("Teste " + r.destino); } catch (e) { aviso(e.message, true); }
  };
  $("detCfg").addEventListener("toggle", () => { if ($("detCfg").open) carregarImpressoras(); });

  // ---------- início ----------
  fila = ler(CHAVE_FILA, []).filter((f) => f && (f.imei1 || f.imei2));
  api("api/config").then((r) => { cfg = r.config; preencherCfg(); desenharFila(); previa(); })
    .catch((e) => aviso(e.message, true));
})();
