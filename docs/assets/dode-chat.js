(function () {
  const DODE_NAME = "Dode";
  const WHATSAPP_PHONE = "491636157234";
  const CONTACT_EMAIL = "info@klarumzug24.de";
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const conversation = [];
  let initialized = false;

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function matchesAny(text, keywords) {
    return keywords.some((keyword) => text.includes(keyword));
  }

  function pageLabel(path) {
    const labels = {
      "/umzugsrechner.html": "Umzugsrechner",
      "umzugsrechner.html": "Umzugsrechner",
      "/kontakt.html": "Kontaktformular",
      "kontakt.html": "Kontaktformular",
      "/ueber-uns.html": "Ueber uns",
      "ueber-uns.html": "Ueber uns",
      "/agb.html": "AGB",
      "agb.html": "AGB",
      "/datenschutz.html": "Datenschutz",
      "datenschutz.html": "Datenschutz",
      "/impressum.html": "Impressum",
      "impressum.html": "Impressum",
      "/index.html": "Startseite",
      "index.html": "Startseite",
    };
    return labels[path] || path;
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
        "WhatsApp oeffnen"
      )
      .replace(
        /<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gi,
        "$2"
      )
      .replace(/https?:\/\/wa\.me\/491636157234\/?/gi, "WhatsApp oeffnen");
  }

  function linkifyText(text) {
    let html = escapeHtml(normalizeReplyText(text))
      .replace(
        /\bWhatsApp oeffnen\b/g,
        '<a href="https://wa.me/491636157234" target="_blank" rel="noopener">WhatsApp oeffnen</a>'
      )
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
        /(^|[\s(])((?:\/)?(?:umzugsrechner|kontakt|ueber-uns|agb|datenschutz|impressum|index)\.html)\b/g,
        (_, prefix, path) => {
          const href = path.startsWith("/") ? path : "/" + path;
          return prefix + '<a href="' + href + '">' + pageLabel(path) + "</a>";
        }
      )
      .replace(/\n/g, "<br>");

    return html;
  }

  function buildFallbackReply(rawText) {
    const text = rawText.toLowerCase();

    if (matchesAny(text, ["hallo", "hi", "hey", "moin", "guten tag"])) {
      return {
        html: "Hallo, ich bin <strong>" + DODE_NAME + "</strong>. Ich helfe Ihnen bei Preis, Kontakt, WhatsApp, Leistungen und allgemeinen Fragen zu Klarumzug24.",
      };
    }

    if (matchesAny(text, ["preis", "kosten", "angebot", "schaetzung", "rechner"])) {
      return {
        html: 'Fuer eine schnelle Preis-Schaetzung nutzen Sie bitte unseren <a href="umzugsrechner.html">Umzugsrechner</a>. Wenn Sie lieber direkt anfragen moechten, koennen Sie danach sofort ueber die Seite senden oder mich nach <strong>WhatsApp</strong> fragen.',
      };
    }

    if (matchesAny(text, ["kontakt", "email", "telefon", "anrufen"])) {
      return {
        html: 'Sie erreichen Klarumzug24 unter <a href="tel:+491636157234">+49 163 615 7234</a> oder per E-Mail an <a href="mailto:' + CONTACT_EMAIL + '">' + CONTACT_EMAIL + '</a>. Fuer eine schriftliche Anfrage gibt es auch das <a href="kontakt.html">Kontaktformular</a>.',
      };
    }

    if (matchesAny(text, ["whatsapp", "chat"])) {
      return {
        html: 'Sie koennen direkt per WhatsApp schreiben: <a href="https://wa.me/' + WHATSAPP_PHONE + '" target="_blank" rel="noopener">WhatsApp oeffnen</a>. Dort koennen Sie auch Bilder oder weitere Details senden.',
      };
    }

    if (matchesAny(text, ["leistung", "service", "montage", "transport", "entsorgung", "umzug"])) {
      return {
        html: "Klarumzug24 unterstuetzt bei Privat- und Firmenumzuegen, Nah- und Fernumzuegen, Montage, Demontage, Transport und auf Wunsch auch zusaetzlichen Services wie Verpackung oder Entsorgung.",
      };
    }

    if (matchesAny(text, ["bordesholm", "kiel", "schleswig", "region", "gebiet", "einsatz"])) {
      return {
        html: "Klarumzug24 arbeitet in Bordesholm, Schleswig-Holstein und der gesamten Region. Wenn Sie einen laengeren Umzug planen, koennen Sie trotzdem direkt anfragen.",
      };
    }

    if (matchesAny(text, ["termin", "kurzfristig", "express", "schnell"])) {
      return {
        html: 'Kurzfristige oder Express-Anfragen sind moeglich, je nach Verfuegbarkeit. Am schnellsten ist in solchen Faellen eine Nachricht ueber <a href="https://wa.me/' + WHATSAPP_PHONE + '" target="_blank" rel="noopener">WhatsApp</a> oder das <a href="kontakt.html">Kontaktformular</a>.',
      };
    }

    if (matchesAny(text, ["foto", "bild", "upload"])) {
      return {
        html: 'Fotos koennen Sie im <a href="kontakt.html">Kontaktformular</a> hochladen. Besonders praktisch ist zusaetzlich WhatsApp, wenn Sie mehrere Bilder senden moechten.',
      };
    }

    if (matchesAny(text, ["agb", "datenschutz", "impressum"])) {
      return {
        html: 'Die rechtlichen Informationen finden Sie hier: <a href="agb.html">AGB</a>, <a href="datenschutz.html">Datenschutz</a> und <a href="impressum.html">Impressum</a>.',
      };
    }

    if (matchesAny(text, ["danke", "super", "perfekt"])) {
      return {
        html: "Gern. Wenn Sie moechten, zeige ich Ihnen sofort den besten naechsten Schritt: Preis berechnen, Kontakt aufnehmen oder WhatsApp.",
      };
    }

    return {
      html: 'Dazu kann ich Ihnen direkt diese Wege empfehlen: <a href="umzugsrechner.html">Preis berechnen</a>, <a href="kontakt.html">Anfrage senden</a> oder <a href="https://wa.me/' + WHATSAPP_PHONE + '" target="_blank" rel="noopener">WhatsApp</a>.',
    };
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
    message.textContent = DODE_NAME + " schreibt...";
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

    throw lastError || new Error("Dode ist nicht erreichbar");
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
    const wrapper = document.createElement("div");
    wrapper.innerHTML = [
      '<button class="dode-fab" type="button" aria-label="Dode Chat oeffnen">',
      '  <i class="fa-solid fa-comments"></i>',
      "  <span>" + DODE_NAME + "</span>",
      "</button>",
      '<section class="dode-panel" aria-label="' + DODE_NAME + ' Chat">',
      '  <div class="dode-header">',
      '    <div class="dode-header-main">',
      '      <div class="dode-avatar">D</div>',
      "      <div>",
      '        <h2 class="dode-title">' + DODE_NAME + "</h2>",
      '        <p class="dode-subtitle">Ihr Klarumzug24 Assistent</p>',
      "      </div>",
      "    </div>",
      '    <button class="dode-close" type="button" aria-label="Chat schliessen"><i class="fa-solid fa-xmark"></i></button>',
      "  </div>",
      '  <div class="dode-body" aria-live="polite"></div>',
      '  <div class="dode-footer">',
      '    <div class="dode-input-row">',
      '      <input class="dode-input" type="text" placeholder="Fragen Sie ' + DODE_NAME + '..." aria-label="Nachricht an ' + DODE_NAME + '">',
      '      <button class="dode-send" type="button" aria-label="Nachricht senden"><i class="fa-solid fa-paper-plane"></i></button>',
      "    </div>",
      '    <div class="dode-note">' + DODE_NAME + " hilft bei Preis, Kontakt, WhatsApp und allgemeinen Umzugsfragen.</div>",
      "  </div>",
      "</section>",
    ].join("");

    document.body.appendChild(wrapper);

    const fab = wrapper.querySelector(".dode-fab");
    const panel = wrapper.querySelector(".dode-panel");
    const closeButton = wrapper.querySelector(".dode-close");
    const body = wrapper.querySelector(".dode-body");
    const input = wrapper.querySelector(".dode-input");
    const sendButton = wrapper.querySelector(".dode-send");

    function renderGreeting() {
      if (initialized) return;
      initialized = true;

      addMessage(
        body,
        "bot",
        "Hallo, ich bin <strong>" + DODE_NAME + "</strong>. Ich helfe Ihnen schnell bei Preis, Kontakt, WhatsApp und allgemeinen Fragen rund um Ihren Umzug."
      );
      conversation.push({
        role: "assistant",
        content: "Hallo, ich bin " + DODE_NAME + ". Ich helfe Ihnen schnell bei Preis, Kontakt, WhatsApp und allgemeinen Fragen rund um Ihren Umzug.",
      });

      const quickActions = document.createElement("div");
      quickActions.className = "dode-quick-actions";

      [
        "Preis berechnen",
        "Kontakt",
        "WhatsApp",
        "Leistungen",
        "Einsatzgebiet",
      ].forEach((label) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dode-chip";
        button.textContent = label;
        button.addEventListener("click", () => {
          void sendText(body, input, label);
        });
        quickActions.appendChild(button);
      });

      body.appendChild(quickActions);
    }

    function openPanel() {
      panel.classList.add("is-open");
      renderGreeting();
      input.focus();
    }

    function closePanel() {
      panel.classList.remove("is-open");
    }

    fab.addEventListener("click", () => {
      if (panel.classList.contains("is-open")) {
        closePanel();
      } else {
        openPanel();
      }
    });

    closeButton.addEventListener("click", closePanel);
    sendButton.addEventListener("click", () => {
      void sendText(body, input, input.value);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        void sendText(body, input, input.value);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildWidget);
  } else {
    buildWidget();
  }
})();
