/* Leitura dos IMEIs a partir da foto da caixa: códigos de barras (ZXing) e, se faltar algum, texto (OCR). */
(function () {
  "use strict";
  // Pasta das bibliotecas: "static/vendor/" no programa do computador; a página do celular define window.LEITOR_BASE.
  const BASE = new URL(window.LEITOR_BASE || "static/vendor/", document.baseURI).href;

  function luhn(num) {
    let soma = 0;
    for (let i = 0; i < num.length; i++) {
      let d = +num[num.length - 1 - i];
      if (i % 2 === 1) { d *= 2; if (d > 9) d -= 9; }
      soma += d;
    }
    return soma % 10 === 0;
  }
  const imeiValido = (n) => /^\d{15}$/.test(n) && luhn(n);

  /** IMEIs válidos num texto (conteúdo de código de barras ou linha de OCR), na ordem. */
  function encontrar(texto) {
    const achados = [];
    for (const g of String(texto || "").match(/\d[\d \-]{13,22}\d/g) || []) {
      const n = g.replace(/\D/g, "");
      if (imeiValido(n) && !achados.includes(n)) achados.push(n);
    }
    // Código de barras com o número "colado" a outros dígitos (ex.: IMEI1IMEI2 num QR)
    const so = String(texto || "").replace(/\D/g, "");
    if (!achados.length && so.length === 30) {
      for (const n of [so.slice(0, 15), so.slice(15)]) if (imeiValido(n)) achados.push(n);
    }
    return achados;
  }

  function carregarImagem(arquivo) {
    return new Promise((ok, falha) => {
      const url = URL.createObjectURL(arquivo);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); ok(img); };
      img.onerror = () => { URL.revokeObjectURL(url); falha(new Error("Não consegui abrir a foto.")); };
      img.src = url;
    });
  }

  function paraCanvas(img, maximo) {
    const w0 = img.naturalWidth || img.width, h0 = img.naturalHeight || img.height;
    const esc = Math.min(1, maximo / Math.max(w0, h0));
    const c = document.createElement("canvas");
    c.width = Math.round(w0 * esc); c.height = Math.round(h0 * esc);
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, c.width, c.height);
    return c;
  }

  function girar90(src) {
    const c = document.createElement("canvas");
    c.width = src.height; c.height = src.width;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.translate(c.width, 0); ctx.rotate(Math.PI / 2);
    ctx.drawImage(src, 0, 0);
    return c;
  }

  // Leitor de códigos (zxing-cpp em WebAssembly): acha todos os códigos da foto de uma vez, inclusive girados.
  let preparado = false;
  function preparar() {
    if (preparado) return;
    window.ZXingWASM.prepareZXingModule({
      overrides: { locateFile: (arq, prefixo) => (arq.endsWith(".wasm") ? BASE + "zxing_reader.wasm" : prefixo + arq) },
    });
    preparado = true;
  }
  const OPCOES = {
    formats: ["Code128", "Code39", "Code93", "ITF", "EAN13", "QRCode", "DataMatrix"],
    tryHarder: true, tryRotate: true, tryInvert: true, tryDownscale: true, maxNumberOfSymbols: 20,
  };

  async function lerImagem(canvas) {
    preparar();
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const dados = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const res = await window.ZXingWASM.readBarcodes(dados, OPCOES);
    return res.filter((r) => r.isValid).map((r) => {
      const p = r.position;
      const cx = (p.topLeft.x + p.topRight.x + p.bottomLeft.x + p.bottomRight.x) / 4;
      const cy = (p.topLeft.y + p.topRight.y + p.bottomLeft.y + p.bottomRight.y) / 4;
      // Posição "no sentido da etiqueta": desfaz o giro do código, para o IMEI 1 (de cima) vir primeiro
      // mesmo quando a foto foi tirada de lado ou de cabeça para baixo.
      const a = ((r.orientation || 0) * Math.PI) / 180;
      const lado = Math.max(canvas.width, canvas.height); // posição em fração da foto, igual em qualquer tamanho
      return { texto: r.text, y: (-cx * Math.sin(a) + cy * Math.cos(a)) / lado, x: (cx * Math.cos(a) + cy * Math.sin(a)) / lado };
    });
  }

  /** Leitor de códigos do próprio aparelho (Chrome no Android), usado se o outro não achar nada. */
  async function lerNativo(canvas) {
    if (!("BarcodeDetector" in window)) return [];
    try {
      const det = new window.BarcodeDetector();
      const lado = Math.max(canvas.width, canvas.height);
      return (await det.detect(canvas)).map((c) => ({
        texto: c.rawValue,
        y: (c.boundingBox.y + c.boundingBox.height / 2) / lado,
        x: (c.boundingBox.x + c.boundingBox.width / 2) / lado,
      }));
    } catch (_) { return []; }
  }

  /** Procura os códigos na foto em alguns tamanhos (código pequeno precisa da foto grande, e vice-versa). */
  async function lerCodigos(img, progresso) {
    const achados = new Map(); // imei -> posição para ordenar (de cima para baixo)
    const tamanhos = [2000, 3200, 1000];
    for (let i = 0; i < tamanhos.length; i++) {
      if (i > 0 && Math.max(img.naturalWidth, img.naturalHeight) <= tamanhos[i - 1] && tamanhos[i] > tamanhos[i - 1]) continue;
      const canvas = paraCanvas(img, tamanhos[i]);
      let lidos = [];
      try { lidos = await lerImagem(canvas); } catch (e) { console.warn("leitor de códigos indisponível", e); }
      if (!lidos.length) lidos = await lerNativo(canvas);
      for (const r of lidos) {
        encontrar(r.texto).forEach((n, k) => {
          if (!achados.has(n)) achados.set(n, { y: r.y, x: r.x + k });
        });
      }
      if (progresso) progresso((i + 1) / tamanhos.length);
      if (achados.size >= 2) break;
    }
    // Ordena de cima para baixo (e da esquerda para a direita quando estão na mesma altura)
    const lista = [...achados.entries()].map(([n, v]) => ({ n, ...v }));
    lista.sort((a, b) => (Math.abs(a.y - b.y) > 0.01 ? a.y - b.y : a.x - b.x));
    return lista.map((e) => e.n);
  }

  // --- OCR (só quando os códigos de barras não bastam) ---
  let ocrWorker = null;
  function carregarScript(src) {
    return new Promise((ok, falha) => {
      const s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = () => falha(new Error("Não consegui carregar " + src));
      document.head.appendChild(s);
    });
  }
  async function lerTexto(canvas, progresso) {
    if (!window.Tesseract) await carregarScript(BASE + "tesseract/tesseract.min.js");
    if (!ocrWorker) {
      ocrWorker = await window.Tesseract.createWorker("eng", 1, {
        workerPath: BASE + "tesseract/worker.min.js",
        corePath: BASE + "tesseract/tesseract-core-lstm.wasm.js",
        langPath: BASE + "tesseract",
        gzip: true,
        logger: (m) => { if (progresso && m.status === "recognizing text") progresso(m.progress); },
      });
    }
    const achados = [];
    for (const src of [canvas, girar90(canvas)]) {
      const { data } = await ocrWorker.recognize(src);
      for (const linha of String(data.text || "").split(/\n/)) {
        for (const n of encontrar(linha)) if (!achados.includes(n)) achados.push(n);
      }
      if (achados.length >= 2) break;
    }
    return achados;
  }

  /**
   * Lê a foto e devolve { imeis: [...], metodo }.
   * etapa(texto, fração) recebe o andamento para mostrar na tela.
   */
  async function lerFoto(arquivo, etapa) {
    const img = await carregarImagem(arquivo);
    etapa("Procurando os códigos de barras…", 0);
    let imeis = await lerCodigos(img, (p) => etapa("Procurando os códigos de barras…", p));
    let metodo = "código de barras";
    if (imeis.length < 2 && !window.LEITOR_SEM_OCR) {
      etapa("Lendo os números impressos (OCR)…", 0);
      try {
        const doTexto = await lerTexto(paraCanvas(img, 1800), (p) => etapa("Lendo os números impressos (OCR)…", p));
        const novos = doTexto.filter((n) => !imeis.includes(n));
        if (novos.length) metodo = imeis.length ? "código de barras + OCR" : "OCR";
        imeis = imeis.concat(novos);
      } catch (e) {
        console.warn("OCR falhou", e);
      }
    }
    return { imeis, metodo, miniatura: paraCanvas(img, 600).toDataURL("image/jpeg", 0.7) };
  }

  window.Leitor = { lerFoto, lerImagem, encontrar, imeiValido, luhn };
})();
