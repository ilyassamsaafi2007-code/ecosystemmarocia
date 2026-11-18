/*
 * guide.js
 * Guided onboarding tour for the platform.
 * - Runs automatically only on the first visit.
 * - Uses localStorage, so it stays dismissed on this browser.
 * - Works without external libraries.
 * - Can be reopened with window.PlatformGuide.start().
 */

(function () {
    "use strict";

    var STORAGE_KEY = "platform_onboarding_completed_v1";

    var steps = [
        {
            selector: '[data-guide="logo"]',
            title: "Bienvenue 👋",
            text: "Bienvenue sur la plateforme. Le logo vous permet de revenir rapidement à la page principale.",
            position: "right"
        },
        {
            selector: '[data-guide="navigation"]',
            title: "Votre navigation",
            text: "Ici vous trouverez les principales fonctionnalités : offres, entreprises, dashboard, CV, évaluation, formations et profil.",
            position: "right"
        },
        {
            selector: '[data-guide="content"]',
            title: "Votre espace",
            text: "C'est ici que le contenu de chaque page s'affiche. Commencez par les offres ou utilisez les autres rubriques du menu.",
            position: "bottom"
        },
        {
            selector: '[data-guide="topbar"]',
            title: "Langue et sécurité",
            text: "La barre supérieure contient le changement de langue et les informations liées à votre espace sécurisé.",
            position: "bottom"
        },
        {
            selector: '[data-guide="profile"]',
            title: "Votre profil",
            text: "Depuis ici, vous pouvez accéder à votre profil et vérifier l'état de votre compte.",
            position: "right"
        },
        {
            selector: '[data-guide="chat"]',
            title: "Assistant",
            text: "Vous avez besoin d'aide ? Utilisez ce bouton pour ouvrir l'assistant et poser vos questions.",
            position: "left"
        }
    ];

    var state = {
        index: 0,
        overlay: null,
        card: null,
        target: null
    };

    function isCompleted() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "1";
        } catch (e) {
            return false;
        }
    }

    function markCompleted() {
        try {
            localStorage.setItem(STORAGE_KEY, "1");
        } catch (e) {}
    }

    function visible(el) {
        if (!el) return false;
        var rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    function findNextAvailableStep(start) {
        for (var i = start; i < steps.length; i++) {
            var el = document.querySelector(steps[i].selector);
            if (visible(el)) return i;
        }
        return -1;
    }

    function createUI() {
        state.overlay = document.createElement("div");
        state.overlay.className = "guide-overlay";

        state.card = document.createElement("div");
        state.card.className = "guide-card";
        state.card.setAttribute("role", "dialog");
        state.card.setAttribute("aria-modal", "true");

        state.card.innerHTML = `
            <div class="guide-step">
                <span class="guide-step-number"></span>
                <span class="guide-step-total"></span>
            </div>
            <button class="guide-close" type="button" aria-label="Fermer">×</button>
            <div class="guide-icon">✨</div>
            <h3 class="guide-title"></h3>
            <p class="guide-text"></p>
            <div class="guide-progress">
                <span></span>
            </div>
            <div class="guide-actions">
                <button type="button" class="guide-skip">Passer</button>
                <div>
                    <button type="button" class="guide-back">Retour</button>
                    <button type="button" class="guide-next">Suivant</button>
                </div>
            </div>
        `;

        document.body.appendChild(state.overlay);
        document.body.appendChild(state.card);

        state.card.querySelector(".guide-close").addEventListener("click", finish);
        state.card.querySelector(".guide-skip").addEventListener("click", finish);
        state.card.querySelector(".guide-back").addEventListener("click", function () {
            showStep(state.index - 1);
        });
        state.card.querySelector(".guide-next").addEventListener("click", function () {
            if (state.index >= steps.length - 1) {
                finish();
            } else {
                showStep(state.index + 1);
            }
        });

        state.overlay.addEventListener("click", function (event) {
            if (event.target === state.overlay) finish();
        });
    }

    function clearHighlight() {
        if (state.target) {
            state.target.classList.remove("guide-highlight");
            state.target.removeAttribute("data-guide-active");
        }
    }

    function showStep(index) {
        var actual = findNextAvailableStep(index);

        if (actual === -1) {
            finish();
            return;
        }

        clearHighlight();

        state.index = actual;
        state.target = document.querySelector(steps[actual].selector);

        if (!state.target) {
            finish();
            return;
        }

        state.target.classList.add("guide-highlight");
        state.target.setAttribute("data-guide-active", "true");

        var step = steps[actual];

        state.card.querySelector(".guide-step-number").textContent = String(actual + 1);
        state.card.querySelector(".guide-step-total").textContent = "/ " + String(steps.length);
        state.card.querySelector(".guide-title").textContent = step.title;
        state.card.querySelector(".guide-text").textContent = step.text;
        state.card.querySelector(".guide-progress span").style.width =
            (((actual + 1) / steps.length) * 100) + "%";

        var back = state.card.querySelector(".guide-back");
        var next = state.card.querySelector(".guide-next");

        back.style.visibility = actual === 0 ? "hidden" : "visible";
        next.textContent = actual === steps.length - 1 ? "Terminer" : "Suivant";

        positionCard(step.position);

        requestAnimationFrame(function () {
            positionCard(step.position);
        });
    }

    function positionCard(position) {
        if (!state.target || !state.card) return;

        var rect = state.target.getBoundingClientRect();
        var cardRect = state.card.getBoundingClientRect();
        var gap = 18;
        var top;
        var left;

        if (position === "right") {
            left = rect.right + gap;
            top = rect.top + (rect.height / 2) - (cardRect.height / 2);
        } else if (position === "left") {
            left = rect.left - cardRect.width - gap;
            top = rect.top + (rect.height / 2) - (cardRect.height / 2);
        } else {
            left = rect.left + (rect.width / 2) - (cardRect.width / 2);
            top = rect.bottom + gap;
        }

        var margin = 12;

        if (left + cardRect.width > window.innerWidth - margin) {
            left = window.innerWidth - cardRect.width - margin;
        }

        if (left < margin) {
            left = margin;
        }

        if (top + cardRect.height > window.innerHeight - margin) {
            top = window.innerHeight - cardRect.height - margin;
        }

        if (top < margin) {
            top = margin;
        }

        state.card.style.left = left + "px";
        state.card.style.top = top + "px";
    }

    function finish() {
        clearHighlight();

        if (state.overlay) state.overlay.remove();
        if (state.card) state.card.remove();

        state.overlay = null;
        state.card = null;
        state.target = null;

        markCompleted();
        document.body.classList.remove("guide-running");
    }

    function start(force) {
        if (!force && isCompleted()) return;

        if (state.overlay) return;

        createUI();
        document.body.classList.add("guide-running");
        showStep(0);
    }

    window.PlatformGuide = {
        start: function () {
            start(true);
        },
        reset: function () {
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch (e) {}
        },
        isCompleted: isCompleted
    };

    document.addEventListener("keydown", function (event) {
        if (!state.card) return;

        if (event.key === "Escape") {
            finish();
        }

        if (event.key === "ArrowRight") {
            if (state.index < steps.length - 1) showStep(state.index + 1);
        }

        if (event.key === "ArrowLeft") {
            if (state.index > 0) showStep(state.index - 1);
        }
    });

    window.addEventListener("resize", function () {
        if (state.card) positionCard(steps[state.index].position);
    });

    window.addEventListener("load", function () {
        setTimeout(function () {
            start(false);
        }, 700);
    });
})();
