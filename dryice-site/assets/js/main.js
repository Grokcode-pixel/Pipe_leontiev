/* КРИО/73 — интерактив сайта. Без зависимостей. */
(() => {
  "use strict";

  /* ===== Настройки студии: заполните реальными данными ===== */
  const CONFIG = {
    phone: "+7 (900) 000-00-00",          // как показывать на сайте
    phoneRaw: "+79000000000",             // для ссылки tel:
    whatsapp: "79000000000",              // номер WhatsApp без «+»
    telegram: "kryo73",                   // имя пользователя Telegram без @
    vk: "https://vk.com/",                // страница ВКонтакте
    address: "г. Ульяновск, ул. Примерная, 1",
    hours: "Ежедневно 9:00–21:00",
    // Необязательно: адрес, куда отправлять заявки POST-запросом (JSON),
    // например Formspree или собственный бот. Пусто — заявка уходит через мессенджер.
    formEndpoint: "",
  };

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ---------- конфиг в разметку ---------- */
  $$("[data-cfg]").forEach((el) => {
    const v = CONFIG[el.dataset.cfg];
    if (v) el.textContent = v;
    if (el.dataset.cfgHref === "tel") el.href = `tel:${CONFIG.phoneRaw}`;
  });
  $("#tgLink").href = `https://t.me/${CONFIG.telegram}`;
  $("#waLink").href = `https://wa.me/${CONFIG.whatsapp}`;
  $("#vkLink").href = CONFIG.vk;
  $("#mapLink").href = `https://yandex.ru/maps/?text=${encodeURIComponent(CONFIG.address)}`;
  $("#year").textContent = new Date().getFullYear();

  /* ---------- навигация ---------- */
  const nav = $(".nav");
  const burger = $("#burger");
  const mnav = $("#mnav");
  const fab = $("#fab");
  const onScrollNav = () => {
    nav.classList.toggle("is-solid", window.scrollY > 40);
    const hero = $("#hero");
    const book = $("#book").getBoundingClientRect();
    const sr = $("#scrub").getBoundingClientRect();
    const inScrub = sr.top < window.innerHeight && sr.bottom > 0;
    fab.classList.toggle("is-on", window.scrollY > hero.offsetHeight * 0.8 && book.top > window.innerHeight && !inScrub);
  };
  burger.addEventListener("click", () => {
    const open = burger.getAttribute("aria-expanded") !== "true";
    burger.setAttribute("aria-expanded", String(open));
    burger.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    mnav.hidden = !open;
    nav.classList.add("is-solid");
  });
  mnav.addEventListener("click", (e) => {
    if (e.target.closest("a")) { burger.setAttribute("aria-expanded", "false"); mnav.hidden = true; }
  });

  /* ---------- волна криочистки на фото (canvas) ---------- */
  // «до» и «после» — один и тот же кадр; фронт очистки снимает грязь слева направо.
  const pics = {};
  const onPics = [];
  [["before", "assets/img/before.webp"], ["after", "assets/img/after.webp"]].forEach(([k, src]) => {
    const im = new Image();
    im.decoding = "async";
    im.onload = () => { pics[k] = im; if (pics.before && pics.after) onPics.forEach((f) => f()); };
    im.src = src;
  });
  function coverRect(img, w, h, zoom) {
    const s = Math.max(w / img.width, h / img.height) * zoom;
    const dw = img.width * s, dh = img.height * s;
    return { dx: (w - dw) / 2, dy: (h - dh) / 2, dw, dh };
  }
  const puff = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, "rgba(225,248,255,0.55)");
    gr.addColorStop(0.45, "rgba(170,235,255,0.2)");
    gr.addColorStop(1, "rgba(120,220,255,0)");
    g.fillStyle = gr;
    g.fillRect(0, 0, 128, 128);
    return c;
  })();

  function makeWipe(canvas) {
    const ctx = canvas.getContext("2d");
    let parts = [];
    let prevT = 0;
    return function draw(p, t, k) {
      const w = canvas.width, h = canvas.height;
      const dt = Math.min(48, t - prevT || 16) / 16;
      prevT = t;
      if (!pics.after || !pics.before) { ctx.fillStyle = "#090B0E"; ctx.fillRect(0, 0, w, h); return; }
      const r = coverRect(pics.after, w, h, 1.03 + p * 0.05);
      ctx.drawImage(pics.after, r.dx, r.dy, r.dw, r.dh);

      const x0 = -0.08 * w + p * 1.16 * w;
      const amp = 0.03 * w;
      const tt = reduce ? 0 : t;
      const fx = (y) => x0 + Math.sin((y / h) * 6 + tt * 0.0011) * amp * 0.5 + Math.sin((y / h) * 15 - tt * 0.0019) * amp * 0.22;
      const N = 48;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(w + 2, -2);
      for (let i = 0; i <= N; i++) { const y = (h * i) / N; ctx.lineTo(fx(y), y); }
      ctx.lineTo(w + 2, h + 2);
      ctx.closePath();
      ctx.clip();
      ctx.drawImage(pics.before, r.dx, r.dy, r.dw, r.dh);
      ctx.restore();

      const active = p > 0.005 && p < 0.995;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      if (active) {
        // полоса инея на фронте сублимации
        const line = () => {
          ctx.beginPath();
          for (let i = 0; i <= N; i++) { const y = (h * i) / N; if (i) ctx.lineTo(fx(y), y); else ctx.moveTo(fx(y), y); }
        };
        ctx.lineJoin = "round";
        line(); ctx.lineWidth = 34 * k; ctx.strokeStyle = "rgba(150,235,255,0.10)"; ctx.stroke();
        line(); ctx.lineWidth = 2.5 * k; ctx.strokeStyle = "rgba(210,250,255,0.9)";
        ctx.shadowColor = "#00E5FF"; ctx.shadowBlur = 22 * k; ctx.stroke();
        ctx.shadowBlur = 0;
        // струя и точка удара
        const iy = h * (0.5 + 0.3 * Math.sin(tt * 0.0015));
        const ix = fx(iy);
        const sx = ix + w * 0.22, sy = -h * 0.08;
        const jet = ctx.createLinearGradient(sx, sy, ix, iy);
        jet.addColorStop(0, "rgba(200,245,255,0)");
        jet.addColorStop(1, "rgba(220,250,255,0.5)");
        ctx.strokeStyle = jet; ctx.lineWidth = 7 * k; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ix, iy); ctx.stroke();
        const R = h * 0.14;
        const glow = ctx.createRadialGradient(ix, iy, 0, ix, iy, R);
        glow.addColorStop(0, "rgba(230,252,255,0.35)");
        glow.addColorStop(1, "rgba(0,229,255,0)");
        ctx.fillStyle = glow;
        ctx.fillRect(ix - R, iy - R, R * 2, R * 2);
        if (!reduce && parts.length < 90) {
          for (let i = 0; i < 1; i++) {
            parts.push({
              x: ix, y: iy, vx: (-0.6 - Math.random() * 1.6) * k, vy: (Math.random() - 0.5) * 1.2 * k,
              s: (30 + Math.random() * 60) * k, life: 0, span: 60 + Math.random() * 50,
            });
          }
        }
      }
      // пар от сублимации (обычное наложение, чтобы не пересвечивать)
      ctx.globalCompositeOperation = "source-over";
      parts = parts.filter((q) => q.life < q.span);
      for (const q of parts) {
        q.life += dt; q.x += q.vx * dt; q.y += q.vy * dt; q.s += 1.1 * k * dt; q.vx *= 0.985; q.vy -= 0.003 * dt;
        ctx.globalAlpha = Math.max(0, Math.sin(Math.min(1, q.life / q.span) * Math.PI) * 0.16);
        ctx.drawImage(puff, q.x - q.s / 2, q.y - q.s / 2, q.s, q.s);
      }
      ctx.restore();
    };
  }
  function fitCanvas(c, max = 2) {
    const dpr = Math.min(window.devicePixelRatio || 1, max);
    c.width = Math.max(1, Math.round(c.clientWidth * dpr));
    c.height = Math.max(1, Math.round(c.clientHeight * dpr));
    return dpr;
  }
  const visible = (el, cb) => new IntersectionObserver(([e]) => cb(e.isIntersecting)).observe(el);

  /* превью-карточка в hero: зацикленная очистка */
  const pv = $("#previewCanvas");
  const pbar = $("#previewBar");
  const pvDraw = makeWipe(pv);
  let pvK = fitCanvas(pv), pvOn = true, pvRun = false;
  const ease = (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);
  function previewLoop(t) {
    const ph = (t % 7000) / 7000;
    pvDraw(ease(Math.min(1, ph / 0.82)), t, pvK);
    pbar.style.width = `${ph * 100}%`;
    if (pvOn) requestAnimationFrame(previewLoop); else pvRun = false;
  }
  const pvStart = () => { if (!pvRun && !reduce) { pvRun = true; requestAnimationFrame(previewLoop); } };
  visible($("#hero"), (on) => { pvOn = on; if (on) pvStart(); });
  onPics.push(() => { if (reduce) pvDraw(0.55, 0, pvK); });

  /* скролл-сцена в разделе «Технология» */
  const scrub = $("#scrub");
  const sc = $("#scrubCanvas");
  const scDraw = makeWipe(sc);
  const STEPS = [
    ["Гранулы −78,5 °C", "Пистолет разгоняет сжатым воздухом гранулы сухого льда диаметром 1,5–3 мм."],
    ["Термический шок", "Слой масла и нагара резко охлаждается, становится хрупким и трескается."],
    ["Микроудар", "Гранула выбивает загрязнение из пор и стыков, не задевая металл, пластик и краску."],
    ["Сублимация", "Лёд сразу переходит в газ и расширяется примерно в 800 раз, отрывая остатки грязи. Ни капли влаги."],
  ];
  const hudClean = $("#hudClean");
  const segs = $$("#storyBar i");
  const stepBox = $(".story__text");
  let curStep = 0;
  let scK = fitCanvas(sc), scP = 0, scOn = false, scRun = false;
  function scrubProgress() {
    const r = scrub.getBoundingClientRect();
    const total = r.height - window.innerHeight;
    return Math.min(1, Math.max(0, -r.top / total));
  }
  function hud(p) {
    hudClean.textContent = `${Math.round(p * 100)}%`;
    const n = STEPS.length;
    const step = Math.min(n - 1, Math.floor(p * n * 0.999));
    segs.forEach((el, i) => el.style.setProperty("--f", Math.min(1, Math.max(0, p * n - i)).toFixed(3)));
    if (step !== curStep) {
      curStep = step;
      $("#stepIdx").textContent = `Шаг ${step + 1} из ${n}`;
      $("#stepTitle").textContent = STEPS[step][0];
      $("#stepText").textContent = STEPS[step][1];
      stepBox.animate?.([{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "none" }], { duration: reduce ? 1 : 500, easing: "ease-out" });
    }
  }
  function scrubLoop(t) {
    const target = scrubProgress();
    scP += (target - scP) * (reduce ? 1 : 0.14);
    if (Math.abs(target - scP) < 0.0005) scP = target;
    scDraw(scP, t, scK);
    hud(scP);
    if (scOn) requestAnimationFrame(scrubLoop); else scRun = false;
  }
  const scStart = () => { if (!scRun) { scRun = true; requestAnimationFrame(scrubLoop); } };
  visible(scrub, (on) => { scOn = on; if (on) scStart(); });
  onPics.push(() => scDraw(scrubProgress(), 0, scK));
  window.addEventListener("resize", () => { pvK = fitCanvas(pv); scK = fitCanvas(sc); scDraw(scP, performance.now(), scK); });

  /* ---------- туман в hero ---------- */
  function fog() {
    const c = $("#fog");
    const ctx = c.getContext("2d");
    let w, h, parts = [];
    const sprite = document.createElement("canvas");
    sprite.width = sprite.height = 256;
    const sg = sprite.getContext("2d");
    const g = sg.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0, "rgba(190,245,255,0.55)");
    g.addColorStop(0.4, "rgba(120,220,255,0.18)");
    g.addColorStop(1, "rgba(0,229,255,0)");
    sg.fillStyle = g; sg.fillRect(0, 0, 256, 256);
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = c.width = Math.round(c.clientWidth * dpr);
      h = c.height = Math.round(c.clientHeight * dpr);
      const n = Math.round(Math.min(46, (w * h) / 42000));
      parts = Array.from({ length: n }, () => spawn(true));
    }
    function spawn(any) {
      const s = (0.25 + Math.random() * 0.75) * Math.max(w, h) * 0.32;
      return {
        x: Math.random() * w,
        y: any ? h * (0.35 + Math.random() * 0.7) : h + s * 0.3,
        s, vx: (Math.random() - 0.3) * 0.25, vy: -(0.08 + Math.random() * 0.25),
        a: 0, max: 0.12 + Math.random() * 0.22, life: 0, span: 900 + Math.random() * 1200,
      };
    }
    let mx = 0.5;
    window.addEventListener("pointermove", (e) => { mx = e.clientX / window.innerWidth; }, { passive: true });
    function tick() {
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      for (let i = 0; i < parts.length; i++) {
        const p = parts[i];
        p.life++;
        p.x += p.vx + (mx - 0.5) * 0.35;
        p.y += p.vy;
        const t = p.life / p.span;
        p.a = p.max * Math.sin(Math.min(1, t) * Math.PI);
        if (t >= 1) parts[i] = spawn(false);
        ctx.globalAlpha = p.a;
        ctx.drawImage(sprite, p.x - p.s / 2, p.y - p.s / 2, p.s, p.s);
      }
      ctx.globalAlpha = 1;
      if (heroVisible) requestAnimationFrame(tick); else fogRunning = false;
    }
    let heroVisible = true, fogRunning = false;
    const start = () => { if (!fogRunning) { fogRunning = true; requestAnimationFrame(tick); } };
    new IntersectionObserver(([e]) => { heroVisible = e.isIntersecting; if (heroVisible) start(); }).observe($("#hero"));
    resize();
    window.addEventListener("resize", resize);
    start();
  }

  /* ---------- до / после ---------- */
  const baFrame = $(".ba__frame");
  $("#baRange").addEventListener("input", (e) => baFrame.style.setProperty("--pos", `${e.target.value}%`));

  /* ---------- вкладки ---------- */
  function tabs(buttons, onSelect) {
    buttons.forEach((b, i) => {
      b.addEventListener("click", () => select(i, true));
      b.addEventListener("keydown", (e) => {
        const dir = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (!dir) return;
        e.preventDefault();
        select((i + dir + buttons.length) % buttons.length, true);
      });
    });
    function select(i, focus) {
      buttons.forEach((b, k) => {
        const on = k === i;
        b.classList.toggle("is-on", on);
        b.setAttribute("aria-selected", String(on));
        b.tabIndex = on ? 0 : -1;
      });
      if (focus) buttons[i].focus();
      onSelect(i, buttons[i]);
    }
  }

  const ZONES = [
    { t: "Блок цилиндров и клапанная крышка", x: "Снимаем масляный «запотевший» слой вокруг прокладки клапанной крышки и пригоревший нагар с блока. Становятся видны реальные подтёки, если они есть.", c: ["Масло", "Нагар", "Пыль"], time: "≈ 30 мин" },
    { t: "Жгуты проводки и датчики", x: "Мягкий режим и микрогранула 1,5 мм. Очищаем катушки, разъёмы и гофру без влаги: контакты остаются сухими, фиксаторы целыми.", c: ["Реагенты", "Масляная пыль", "Окислы"], time: "≈ 25 мин" },
    { t: "Турбина, впуск и алюминий", x: "Корпус компрессора, патрубки интеркулера и дроссельный узел. Алюминий возвращает заводской цвет без абразива и полировки.", c: ["Сажа", "Масляный туман", "Потемнение"], time: "≈ 30 мин" },
    { t: "Пластик, патрубки и шумка капота", x: "Патрубки, хомуты, бачки и шумоизоляция капота. Пыль уходит из волокон, пластик не белеет и не сохнет, как после щелочной химии.", c: ["Пыль", "Листва", "Разводы"], time: "≈ 35 мин" },
  ];
  const zImgs = $$(".zones__imgs img");
  const zInfo = $(".zones__info");
  tabs($$(".ztab"), (i, btn) => {
    zImgs.forEach((im, k) => im.classList.toggle("is-on", k === i));
    $("#zpanel").setAttribute("aria-labelledby", btn.id);
    const z = ZONES[i];
    zInfo.animate?.([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: reduce ? 1 : 450, easing: "ease-out" });
    $("#zTitle").textContent = z.t;
    $("#zText").textContent = z.x;
    $("#zChips").textContent = z.c.join(" · ");
    $("#zTime").textContent = z.time;
  });

  const CASES = [
    { t: "Спорткары и мощные V8/V12", img: "assets/img/case_sport.webp", x: "Плотная компоновка, карбоновые крышки и много полированного алюминия. Работаем мягким режимом с микрогранулой, чтобы сохранить лак, карбон и анодирование.", l: ["Карбон и лакированные крышки без матовых пятен", "Впускные трассы и интеркулер до блеска", "Фотоотчёт для сервисной истории"], time: "3–4 ч", res: "Шоурум-вид мотора" },
    { t: "Премиум-седаны и внедорожники", img: "assets/img/case_premium.webp", x: "Много декоративных крышек, электроники и шумоизоляции. Снимаем пыль и реагенты из-под пластика, не снимая его, и консервируем резину.", l: ["Очистка под декоративными крышками", "Безопасно для пневмоподвески и блоков управления", "Консервация уплотнителей и патрубков"], time: "2,5–3 ч", res: "Чисто и сухо, как с завода" },
    { t: "Классика, янгтаймеры и реставрация", img: "assets/img/case_classic.webp", x: "Возвращаем исходный вид литью и окраске без пескоструя и растворителей. Подходит перед оценкой, выставкой или съёмкой и на этапе реставрации.", l: ["Снимаем многолетний нагар, а не родную краску", "Видны трещины и подтёки для дефектовки", "Бережно к старой проводке и резине"], time: "3–5 ч", res: "Аутентичный вид без перекраса" },
    { t: "Повседневные авто и предпродажная подготовка", img: "assets/img/case_daily.webp", x: "Чистый мотор продаёт машину: покупатель видит, что нет подтёков. А вам самим проще заметить течь масла или антифриза.", l: ["Удаление реагентов после зимы", "Подготовка к продаже и осмотру", "Помогает найти подтёки до ремонта"], time: "1,5–2 ч", res: "Аккуратный ухоженный мотор" },
  ];
  const cBody = $(".cpanel__body");
  const cImg = $("#cImg");
  tabs($$(".ctab"), (i, btn) => {
    const c = CASES[i];
    $("#cpanel").setAttribute("aria-labelledby", btn.id);
    cBody.classList.add("is-swap");
    cImg.classList.add("is-swap");
    setTimeout(() => {
      $("#cTitle").textContent = c.t;
      $("#cText").textContent = c.x;
      $("#cList").innerHTML = c.l.map((x) => `<li>${x}</li>`).join("");
      $("#cTime").textContent = c.time;
      $("#cRes").textContent = c.res;
      cImg.src = c.img;
      cBody.classList.remove("is-swap");
      cImg.classList.remove("is-swap");
    }, reduce ? 0 : 300);
  });

  /* ---------- 3D-наклон карточек ---------- */
  if (!reduce && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    $$(".tilt").forEach((card) => {
      const inner = card;
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        inner.style.setProperty("--ry", `${(x - 0.5) * 10}deg`);
        inner.style.setProperty("--rx", `${(0.5 - y) * 8}deg`);
        inner.style.setProperty("--gx", `${x * 100}%`);
        inner.style.setProperty("--gy", `${y * 100}%`);
      });
      card.addEventListener("pointerleave", () => {
        inner.style.setProperty("--ry", "0deg");
        inner.style.setProperty("--rx", "0deg");
      });
    });
  }

  /* ---------- появление блоков ---------- */
  const rvTargets = $$(".sec-head, .facts li, .ba, .zones__grid, .gitem, .specs > div, .ctabs, .cpanel, .plan, .qa details, .book, .contacts > div");
  if (!reduce && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.remove("is-pre"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    rvTargets.forEach((el, i) => {
      el.classList.add("rv");
      if (el.getBoundingClientRect().top > window.innerHeight) {
        el.classList.add("is-pre");
        el.style.transitionDelay = `${(i % 4) * 70}ms`;
        io.observe(el);
      }
    });
  }

  /* ---------- запись ---------- */
  const form = $("#bookForm");
  const fPlan = $("#fPlan");
  const fPhone = $("#fPhone");
  const fErr = $("#fErr");
  const sent = $("#sent");
  $$("[data-plan]").forEach((a) => a.addEventListener("click", () => { fPlan.value = a.dataset.plan; }));
  const fDate = $("#fDate");
  const today = new Date();
  fDate.min = today.toISOString().slice(0, 10);

  fPhone.addEventListener("input", () => {
    let d = fPhone.value.replace(/\D/g, "");
    if (d.startsWith("8")) d = "7" + d.slice(1);
    if (d && !d.startsWith("7")) d = "7" + d;
    d = d.slice(0, 11);
    const p = d.slice(1);
    let out = d ? "+7" : "";
    if (p.length) out += " (" + p.slice(0, 3);
    if (p.length >= 3) out += ")";
    if (p.length > 3) out += " " + p.slice(3, 6);
    if (p.length > 6) out += "-" + p.slice(6, 8);
    if (p.length > 8) out += "-" + p.slice(8, 10);
    fPhone.value = out;
    fPhone.removeAttribute("aria-invalid");
  });

  let message = "";
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const errs = [];
    if (!data.name.trim()) { errs.push("имя"); $("#fName").setAttribute("aria-invalid", "true"); }
    if (data.phone.replace(/\D/g, "").length !== 11) { errs.push("телефон полностью"); fPhone.setAttribute("aria-invalid", "true"); }
    if (errs.length) {
      fErr.textContent = `Укажите ${errs.join(" и ")}, чтобы мы могли перезвонить.`;
      fErr.hidden = false;
      return;
    }
    fErr.hidden = true;
    const date = data.date ? new Date(data.date + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) : "любая";
    message = [
      "Заявка на криочистку двигателя (КРИО/73, Ульяновск)",
      `Имя: ${data.name.trim()}`,
      `Телефон: ${data.phone}`,
      data.car.trim() && `Авто: ${data.car.trim()}`,
      `Пакет: ${data.plan}`,
      `Дата: ${date}`,
      data.msg.trim() && `Комментарий: ${data.msg.trim()}`,
    ].filter(Boolean).join("\n");

    if (CONFIG.formEndpoint) {
      try {
        const r = await fetch(CONFIG.formEndpoint, {
          method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ ...data, message }),
        });
        if (!r.ok) throw new Error(r.status);
        $(".sent__k").textContent = "Заявка отправлена";
        $("#sent h3").textContent = "Мы перезвоним в ближайшее время";
      } catch {
        $(".sent__k").textContent = "Не удалось отправить автоматически";
        $("#sent h3").textContent = "Отправьте заявку в мессенджер";
      }
    }
    $("#sentText").textContent = message;
    $("#sendWa").href = `https://wa.me/${CONFIG.whatsapp}?text=${encodeURIComponent(message)}`;
    $("#sendTg").href = `https://t.me/${CONFIG.telegram}`;
    form.hidden = true;
    sent.hidden = false;
    sent.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  });

  async function copyMessage(btn) {
    try {
      await navigator.clipboard.writeText(message);
      if (btn) { btn.textContent = "Скопировано"; setTimeout(() => (btn.textContent = "Скопировать"), 2000); }
    } catch {
      const r = document.createRange();
      r.selectNodeContents($("#sentText"));
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      if (btn) btn.textContent = "Выделено, нажмите Ctrl+C";
    }
  }
  $("#copyText").addEventListener("click", (e) => copyMessage(e.currentTarget));
  // Telegram не умеет подставлять текст в личный чат — копируем его заранее
  $("#sendTg").addEventListener("click", () => copyMessage(null));
  $("#sentBack").addEventListener("click", () => { sent.hidden = true; form.hidden = false; });

  /* ---------- параллакс фото-вставки ---------- */
  const bandImg = $(".band__img");
  function parallax() {
    if (reduce || !bandImg) return;
    const r = bandImg.parentElement.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight) return;
    const off = (r.top + r.height / 2 - window.innerHeight / 2) * -0.08;
    bandImg.style.setProperty("--par", `${off.toFixed(1)}px`);
  }

  /* ---------- старт ---------- */
  let ticking = false;
  window.addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { onScrollNav(); parallax(); ticking = false; });
  }, { passive: true });
  onScrollNav();
  parallax();
  if (!reduce) fog();
})();
