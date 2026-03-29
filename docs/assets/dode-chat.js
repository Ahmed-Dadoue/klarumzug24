(function () {
  const DODE_NAME = "Dode";
  const WHATSAPP_PHONE = "491636157234";
  const CONTACT_EMAIL = "info@klarumzug24.de";
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const conversation = [];
  const pageLang = (document.documentElement.lang || "de").toLowerCase();
  const isEnglish = pageLang.startsWith("en");
  const conversationStorageKey = "dode_conversation_id";
  let initialized = false;

  function generateConversationId() {
    return "conv_" + Math.random().toString(16).slice(2, 14);
  }

  function getConversationId() {
    try {
      const existing = window.sessionStorage.getItem(conversationStorageKey);
      if (existing) {
        return existing;
      }
      const created = generateConversationId();
      window.sessionStorage.setItem(conversationStorageKey, created);
      return created;
    } catch (_) {
      return generateConversationId();
    }
  }

  const dictionary = {
    de: {
      openWhatsapp: "WhatsApp oeffnen",
      greetingHtml:
        "Hallo, ich bin <strong>Dode</strong>. Ich helfe Ihnen schnell bei Preis, Kontakt, WhatsApp und allgemeinen Fragen rund um Ihren Umzug.",
      greetingText:
        "Hallo, ich bin Dode. Ich helfe Ihnen schnell bei Preis, Kontakt, WhatsApp und allgemeinen Fragen rund um Ihren Umzug.",
      fabLabel: "Dode Chat oeffnen",
      panelLabel: "Dode Chat",
      subtitle: "Ihr Klarumzug24 Assistent",
      closeLabel: "Chat schliessen",
      inputPlaceholder: "Fragen Sie Dode...",
      inputAria: "Nachricht an Dode",
      sendLabel: "Nachricht senden",
      note: "Dode hilft bei Preis, Kontakt, WhatsApp und allgemeinen Umzugsfragen.",
      typing: "Dode schreibt...",
      quickActions: ["Preis berechnen", "Kontakt", "WhatsApp", "Leistungen", "Einsatzgebiet"],
      pageLabels: {
        "index.html": "Startseite",
        "index-en.html": "Home",
        "umzugsrechner.html": "Umzugsrechner",
        "umzugsrechner-en.html": "Moving calculator",
        "kontakt.html": "Kontaktformular",
        "kontakt-en.html": "Contact form",
        "ueber-uns.html": "Ueber uns",
        "ueber-uns-en.html": "About us",
        "agb.html": "AGB",
        "agb-en.html": "Terms",
        "datenschutz.html": "Datenschutz",
        "datenschutz-en.html": "Privacy policy",
        "impressum.html": "Impressum",
        "impressum-en.html": "Legal notice"
      },
      fallbackReplies: {
        hello: "Hallo, ich bin <strong>Dode</strong>. Ich helfe Ihnen bei Preis, Kontakt, WhatsApp, Leistungen und allgemeinen Fragen zu Klarumzug24.",
        price: 'Fuer eine schnelle Preis-Schaetzung nutzen Sie bitte unseren <a href="umzugsrechner.html">Umzugsrechner</a>. Wenn Sie lieber direkt anfragen moechten, koennen Sie danach sofort ueber die Seite senden oder mich nach <strong>WhatsApp</strong> fragen.',
        contact: 'Sie erreichen Klarumzug24 unter <a href="tel:+491636157234">+49 163 615 7234</a> oder per E-Mail an <a href="mailto:info@klarumzug24.de">info@klarumzug24.de</a>. Fuer eine schriftliche Anfrage gibt es auch das <a href="kontakt.html">Kontaktformular</a>.',
        whatsapp: 'Sie koennen direkt per WhatsApp schreiben: <a href="https://wa.me/491636157234" target="_blank" rel="noopener">WhatsApp oeffnen</a>. Dort koennen Sie auch Bilder oder weitere Details senden.',
        services: "Klarumzug24 unterstuetzt bei Privat- und Firmenumzuegen, Nah- und Fernumzuegen, Montage, Demontage, Transport und auf Wunsch auch zusaetzlichen Services wie Verpackung oder Entsorgung.",
        region: "Klarumzug24 arbeitet in Bordesholm, Schleswig-Holstein und der gesamten Region. Wenn Sie einen laengeren Umzug planen, koennen Sie trotzdem direkt anfragen.",
        timing: 'Kurzfristige oder Express-Anfragen sind moeglich, je nach Verfuegbarkeit. Am schnellsten ist in solchen Faellen eine Nachricht ueber <a href="https://wa.me/491636157234" target="_blank" rel="noopener">WhatsApp</a> oder das <a href="kontakt.html">Kontaktformular</a>.',
        photos: 'Fotos koennen Sie im <a href="kontakt.html">Kontaktformular</a> hochladen. Besonders praktisch ist zusaetzlich WhatsApp, wenn Sie mehrere Bilder senden moechten.',
        legal: 'Die rechtlichen Informationen finden Sie hier: <a href="agb.html">AGB</a>, <a href="datenschutz.html">Datenschutz</a> und <a href="impressum.html">Impressum</a>.',
        thanks: "Gern. Wenn Sie moechten, zeige ich Ihnen sofort den besten naechsten Schritt: Preis berechnen, Kontakt aufnehmen oder WhatsApp.",
        generic: 'Dazu kann ich Ihnen direkt diese Wege empfehlen: <a href="umzugsrechner.html">Preis berechnen</a>, <a href="kontakt.html">Anfrage senden</a> oder <a href="https://wa.me/491636157234" target="_blank" rel="noopener">WhatsApp</a>.'
      },
      keywords: {
        hello: ["hallo", "hi", "hey", "moin", "guten tag"],
        price: ["preis", "kosten", "angebot", "schaetzung", "rechner"],
        contact: ["kontakt", "email", "telefon", "anrufen"],
        whatsapp: ["whatsapp", "chat"],
        services: ["leistung", "service", "montage", "transport", "entsorgung", "umzug"],
        region: ["bordesholm", "kiel", "schleswig", "region", "gebiet", "einsatz"],
        timing: ["termin", "kurzfristig", "express", "schnell"],
        photos: ["foto", "bild", "upload"],
        legal: ["agb", "datenschutz", "impressum"],
        thanks: ["danke", "super", "perfekt"]
      }
    },
    en: {
      openWhatsapp: "Open WhatsApp",
      greetingHtml:
        "Hello, I am <strong>Dode</strong>. I can help you quickly with pricing, contact details, WhatsApp and general questions about your move.",
      greetingText:
        "Hello, I am Dode. I can help you quickly with pricing, contact details, WhatsApp and general questions about your move.",
      fabLabel: "Open Dode chat",
      panelLabel: "Dode chat",
      subtitle: "Your Klarumzug24 assistant",
      closeLabel: "Close chat",
      inputPlaceholder: "Ask Dode...",
      inputAria: "Message to Dode",
      sendLabel: "Send message",
      note: "Dode helps with pricing, contact details, WhatsApp and general moving questions.",
      typing: "Dode is typing...",
      quickActions: ["Calculate price", "Contact", "WhatsApp", "Services", "Service area"],
      pageLabels: {
        "index.html": "Home",
        "index-en.html": "Home",
        "umzugsrechner.html": "Moving calculator",
        "umzugsrechner-en.html": "Moving calculator",
        "kontakt.html": "Contact form",
        "kontakt-en.html": "Contact form",
        "ueber-uns.html": "About us",
        "ueber-uns-en.html": "About us",
        "agb.html": "Terms",
        "agb-en.html": "Terms",
        "datenschutz.html": "Privacy policy",
        "datenschutz-en.html": "Privacy policy",
        "impressum.html": "Legal notice",
        "impressum-en.html": "Legal notice"
      },
      fallbackReplies: {
        hello: "Hello, I am <strong>Dode</strong>. I can help with pricing, contact details, WhatsApp, services and general questions about Klarumzug24.",
        price: 'For a quick estimate, please use our <a href="umzugsrechner-en.html">moving calculator</a>. If you prefer to contact us directly, you can send your request there right away or ask me for <strong>WhatsApp</strong>.',
        contact: 'You can reach Klarumzug24 at <a href="tel:+491636157234">+49 163 615 7234</a> or by email at <a href="mailto:info@klarumzug24.de">info@klarumzug24.de</a>. For written requests, you can also use the <a href="kontakt-en.html">contact form</a>.',
        whatsapp: 'You can contact us directly via WhatsApp: <a href="https://wa.me/491636157234" target="_blank" rel="noopener">Open WhatsApp</a>. You can also send photos and additional details there.',
        services: "Klarumzug24 supports private and business moves, local and long-distance moves, assembly, disassembly, transport and, if needed, additional services such as packing or disposal.",
        region: "Klarumzug24 operates in Bordesholm, Schleswig-Holstein and the surrounding region. If you are planning a longer-distance move, you can still contact us directly.",
        timing: 'Short-notice and express requests may be possible depending on availability. In urgent cases, the fastest option is <a href="https://wa.me/491636157234" target="_blank" rel="noopener">WhatsApp</a> or the <a href="kontakt-en.html">contact form</a>.',
        photos: 'You can upload photos in the <a href="kontakt-en.html">contact form</a>. WhatsApp is also practical if you want to send multiple images.',
        legal: 'You can find the legal information here: <a href="agb-en.html">Terms</a>, <a href="datenschutz-en.html">Privacy policy</a> and <a href="impressum-en.html">Legal notice</a>.',
        thanks: "You are welcome. If you like, I can show you the best next step right away: calculate a price, contact us or open WhatsApp.",
        generic: 'I can recommend these next steps: <a href="umzugsrechner-en.html">calculate a price</a>, <a href="kontakt-en.html">send a request</a> or <a href="https://wa.me/491636157234" target="_blank" rel="noopener">WhatsApp</a>.'
      },
      keywords: {
        hello: ["hello", "hi", "hey", "good morning", "good afternoon"],
        price: ["price", "cost", "quote", "estimate", "calculator"],
        contact: ["contact", "email", "phone", "call"],
        whatsapp: ["whatsapp", "chat"],
        services: ["service", "services", "assembly", "transport", "disposal", "move", "moving"],
        region: ["bordesholm", "kiel", "schleswig", "region", "area", "service area"],
        timing: ["appointment", "date", "short notice", "express", "urgent", "fast"],
        photos: ["photo", "photos", "image", "upload"],
        legal: ["terms", "privacy", "legal notice", "imprint"],
        thanks: ["thanks", "thank you", "perfect", "great"]
      }
    }
  };

  const t = isEnglish ? dictionary.en : dictionary.de;
  const pagePairs = {
    "index.html": { de: "index.html", en: "index-en.html" },
    "index-en.html": { de: "index.html", en: "index-en.html" },
    "umzugsrechner.html": { de: "umzugsrechner.html", en: "umzugsrechner-en.html" },
    "umzugsrechner-en.html": { de: "umzugsrechner.html", en: "umzugsrechner-en.html" },
    "kontakt.html": { de: "kontakt.html", en: "kontakt-en.html" },
    "kontakt-en.html": { de: "kontakt.html", en: "kontakt-en.html" },
    "ueber-uns.html": { de: "ueber-uns.html", en: "ueber-uns-en.html" },
    "ueber-uns-en.html": { de: "ueber-uns.html", en: "ueber-uns-en.html" },
    "agb.html": { de: "agb.html", en: "agb-en.html" },
    "agb-en.html": { de: "agb.html", en: "agb-en.html" },
    "datenschutz.html": { de: "datenschutz.html", en: "datenschutz-en.html" },
    "datenschutz-en.html": { de: "datenschutz.html", en: "datenschutz-en.html" },
    "impressum.html": { de: "impressum.html", en: "impressum-en.html" },
    "impressum-en.html": { de: "impressum.html", en: "impressum-en.html" }
  };

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function matchesAny(text, keywords) {
    return keywords.some((keyword) => text.includes(keyword));
  }

  function currentFileName() {
    const raw = window.location.pathname.split("/").pop() || "index.html";
    return raw === "" ? "index.html" : raw;
  }

  function pageLabel(path) {
    const cleaned = String(path || "").replace(/^\//, "");
    return t.pageLabels[cleaned] || cleaned;
  }

  function injectLanguageSwitcher() {
    const navList = document.querySelector("#navMenu .navbar-nav");
    if (!navList || navList.querySelector(".language-switcher")) {
      return;
    }

    const current = currentFileName();
    const pair = pagePairs[current] || pagePairs["index.html"];
    const item = document.createElement("li");
    item.className = "nav-item language-switcher";
    item.innerHTML = [
      '<a class="nav-link gold' + (isEnglish ? '' : ' active') + '" href="' + pair.de + '">DE</a>',
      '<span>/</span>',
      '<a class="nav-link gold' + (isEnglish ? ' active' : '') + '" href="' + pair.en + '">EN</a>'
    ].join("");
    navList.appendChild(item);
  }

  function htmlToText(html) {
    const div = document.createElement("div");
    div.innerHTML = html;
    return (div.textContent || div.innerText || "").trim();
  }

  function normalizeReplyText(text) {
    return String(text || "")
      .replace(
        /<a\b[^>]*href=["']https?:\/\/wa\.me\/491636157234\/?["'][^>]*>(.*?)<\/a>/gi,
        t.openWhatsapp
      )
      .replace(
        /<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gi,
        "$2"
      )
      .replace(/https?:\/\/wa\.me\/491636157234\/?/gi, t.openWhatsapp);
  }

  function linkifyText(text) {
    let html = escapeHtml(normalizeReplyText(text))
      .replace(/\b(?:WhatsApp oeffnen|Open WhatsApp)\b/g, '<a href="https://wa.me/491636157234" target="_blank" rel="noopener">' + t.openWhatsapp + '</a>')
      .replace(
        /\+49[\s-]*163[\s-]*615[\s-]*7234\b/g,
        '<a href="tel:+491636157234">+49 163 615 7234</a>'
      )
      .replace(
        /(https?:\/\/[^\s<]+)/g,
        '<a href="$1" target="_blank" rel="noopener">$1</a>'
      )
      .replace(
        /\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g,
        '<a href="mailto:$1">$1</a>'
      )
      .replace(
        /(^|[\s(])((?:\/)?(?:umzugsrechner(?:-en)?|kontakt(?:-en)?|ueber-uns(?:-en)?|agb(?:-en)?|datenschutz(?:-en)?|impressum(?:-en)?|index(?:-en)?)\.html)\b/g,
        (_, prefix, path) => {
          const cleaned = path.replace(/^\//, "");
          const href = cleaned;
          return prefix + '<a href="/' + href + '">' + pageLabel(cleaned) + '</a>';
        }
      )
      .replace(/\n/g, "<br>");

    return html;
  }

  function buildFallbackReply(rawText) {
    const text = rawText.toLowerCase();
    const replies = t.fallbackReplies;
    const keywords = t.keywords;

    if (matchesAny(text, keywords.hello)) return { html: replies.hello };
    if (matchesAny(text, keywords.price)) return { html: replies.price };
    if (matchesAny(text, keywords.contact)) return { html: replies.contact };
    if (matchesAny(text, keywords.whatsapp)) return { html: replies.whatsapp };
    if (matchesAny(text, keywords.services)) return { html: replies.services };
    if (matchesAny(text, keywords.region)) return { html: replies.region };
    if (matchesAny(text, keywords.timing)) return { html: replies.timing };
    if (matchesAny(text, keywords.photos)) return { html: replies.photos };
    if (matchesAny(text, keywords.legal)) return { html: replies.legal };
    if (matchesAny(text, keywords.thanks)) return { html: replies.thanks };
    return { html: replies.generic };
  }

  function addMessage(container, role, html) {
    const message = document.createElement("div");
    message.className = "dode-message " + role;
    message.innerHTML = html;
    container.appendChild(message);
    container.scrollTop = container.scrollHeight;
  }

  function addUserMessage(container, text) {
    addMessage(container, "user", escapeHtml(text));
  }

  function addBotText(container, text) {
    addMessage(container, "bot", linkifyText(text));
  }

  function createTypingMessage(container) {
    const message = document.createElement("div");
    message.className = "dode-message bot";
    message.textContent = t.typing;
    container.appendChild(message);
    container.scrollTop = container.scrollHeight;
    return message;
  }

  async function fetchAiReply(messages) {
    const endpoints = isLocalHost
      ? ["http://127.0.0.1:8000/api/chat"]
      : ["/api/chat", "https://api.klarumzug24.de/api/chat"];

    let lastError = null;

    for (const endpoint of endpoints) {
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: getConversationId(),
            lang: isEnglish ? "en" : "de",
            page: window.location.pathname,
            messages: messages.slice(-12),
          }),
        });

        let result = null;
        try {
          result = await response.json();
        } catch (_) {
          result = null;
        }

        if (!response.ok || result?.ok === false) {
          throw new Error(result?.message || ("HTTP " + response.status));
        }

        const reply = result?.data?.reply || result?.reply || "";
        if (!reply.trim()) {
          throw new Error("empty reply");
        }
        return reply.trim();
      } catch (error) {
        lastError = error;
      }
    }

    throw lastError || new Error("Dode is unavailable");
  }

  async function sendText(container, input, rawText) {
    const text = String(rawText || "").trim();
    if (!text) return;

    addUserMessage(container, text);
    conversation.push({ role: "user", content: text });
    const typingMessage = createTypingMessage(container);

    if (input) {
      input.value = "";
    }

    try {
      const reply = await fetchAiReply(conversation);
      typingMessage.remove();
      addBotText(container, reply);
      conversation.push({ role: "assistant", content: reply });
    } catch (_) {
      const fallback = buildFallbackReply(text);
      typingMessage.remove();
      addMessage(container, "bot", fallback.html);
      conversation.push({ role: "assistant", content: htmlToText(fallback.html) });
    }
  }

  function buildWidget() {
    injectLanguageSwitcher();

    const wrapper = document.createElement("div");
    wrapper.innerHTML = [
      '<button class="dode-fab" type="button" aria-label="' + t.fabLabel + '">',
      '  <i class="fa-solid fa-comments"></i>',
      '  <span>' + DODE_NAME + '</span>',
      '</button>',
      '<section class="dode-panel" aria-label="' + t.panelLabel + '">',
      '  <div class="dode-header">',
      '    <div class="dode-header-main">',
      '      <div class="dode-avatar">D</div>',
      '      <div>',
      '        <h2 class="dode-title">' + DODE_NAME + '</h2>',
      '        <p class="dode-subtitle">' + t.subtitle + '</p>',
      '      </div>',
      '    </div>',
      '    <button class="dode-close" type="button" aria-label="' + t.closeLabel + '"><i class="fa-solid fa-xmark"></i></button>',
      '  </div>',
      '  <div class="dode-body" aria-live="polite"></div>',
      '  <div class="dode-footer">',
      '    <div class="dode-input-row">',
      '      <input class="dode-input" type="text" placeholder="' + t.inputPlaceholder + '" aria-label="' + t.inputAria + '">',
      '      <button class="dode-send" type="button" aria-label="' + t.sendLabel + '"><i class="fa-solid fa-paper-plane"></i></button>',
      '    </div>',
      '    <div class="dode-note">' + t.note + '</div>',
      '  </div>',
      '</section>'
    ].join('');

    document.body.appendChild(wrapper);

    const fab = wrapper.querySelector('.dode-fab');
    const panel = wrapper.querySelector('.dode-panel');
    const closeButton = wrapper.querySelector('.dode-close');
    const body = wrapper.querySelector('.dode-body');
    const input = wrapper.querySelector('.dode-input');
    const sendButton = wrapper.querySelector('.dode-send');

    function renderGreeting() {
      if (initialized) return;
      initialized = true;

      addMessage(body, 'bot', t.greetingHtml);
      conversation.push({ role: 'assistant', content: t.greetingText });

      const quickActions = document.createElement('div');
      quickActions.className = 'dode-quick-actions';

      t.quickActions.forEach((label) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'dode-chip';
        button.textContent = label;
        button.addEventListener('click', () => {
          void sendText(body, input, label);
        });
        quickActions.appendChild(button);
      });

      body.appendChild(quickActions);
    }

    function openPanel() {
      panel.classList.add('is-open');
      renderGreeting();
      input.focus();
    }

    function closePanel() {
      panel.classList.remove('is-open');
    }

    fab.addEventListener('click', () => {
      if (panel.classList.contains('is-open')) {
        closePanel();
      } else {
        openPanel();
      }
    });

    closeButton.addEventListener('click', closePanel);
    sendButton.addEventListener('click', () => {
      void sendText(body, input, input.value);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        void sendText(body, input, input.value);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWidget);
  } else {
    buildWidget();
  }
})();
