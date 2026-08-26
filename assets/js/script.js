(() => {
    "use strict";

    const navToggle = document.querySelector(".nav-toggle");
    const navMenu = document.querySelector(".nav-menu");
    const navLinks = [...document.querySelectorAll(".nav-link")];
    const sections = [...document.querySelectorAll("main section[id]")];
    const currentYear = document.getElementById("current-year");

    const setMenuState = (isOpen) => {
        if (!navToggle || !navMenu) return;

        navToggle.setAttribute("aria-expanded", String(isOpen));
        navToggle.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
        navMenu.classList.toggle("is-open", isOpen);
        document.body.classList.toggle("nav-open", isOpen);
    };

    if (navToggle && navMenu) {
        navToggle.addEventListener("click", () => {
            const isOpen = navToggle.getAttribute("aria-expanded") !== "true";
            setMenuState(isOpen);
        });

        navMenu.addEventListener("click", (event) => {
            if (event.target.closest("a")) setMenuState(false);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && navToggle.getAttribute("aria-expanded") === "true") {
                setMenuState(false);
                navToggle.focus();
            }
        });

        window.addEventListener("resize", () => {
            if (window.innerWidth > 820) setMenuState(false);
        });
    }

    if ("IntersectionObserver" in window && sections.length > 0) {
        const sectionObserver = new IntersectionObserver((entries) => {
            const visibleSection = entries
                .filter((entry) => entry.isIntersecting)
                .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

            if (!visibleSection) return;

            navLinks.forEach((link) => {
                const isCurrent = link.getAttribute("href") === `#${visibleSection.target.id}`;
                if (isCurrent) {
                    link.setAttribute("aria-current", "location");
                } else {
                    link.removeAttribute("aria-current");
                }
            });
        }, {
            rootMargin: "-20% 0px -65% 0px",
            threshold: [0, 0.15, 0.4]
        });

        sections.forEach((section) => sectionObserver.observe(section));
    }

    if (currentYear) {
        currentYear.textContent = new Intl.DateTimeFormat("en", { year: "numeric" }).format(new Date());
    }
})();
