// Renders the Claude Code version and model published in status.json.
// Any element with data-claude="<field>" on the page is filled in. The file is
// written by sync-status.sh, so nothing here needs editing when the model changes.
(() => {
    "use strict";

    const script = document.currentScript;
    const STATUS_URL = new URL("status.json", script ? script.src : window.location.href);
    const NPM_LATEST_URL = "https://registry.npmjs.org/@anthropic-ai/claude-code/latest";
    const FAMILIES = { opus: "Opus", sonnet: "Sonnet", haiku: "Haiku", fable: "Fable" };

    const nodes = (field) => document.querySelectorAll(`[data-claude="${field}"]`);

    const setField = (field, value) => {
        nodes(field).forEach((node) => {
            node.textContent = value;
        });
    };

    const setBadge = (field, text, tone) => {
        nodes(field).forEach((node) => {
            node.textContent = text;
            node.classList.remove("ok", "warn", "info", "danger");
            if (tone) node.classList.add(tone);
        });
    };

    // "claude-opus-5-5[1m]" -> "Opus 5.5", "claude-sonnet-4-20250514" -> "Sonnet 4".
    // Claude Code's display name can be just "Opus", so the ID wins unless the
    // display name carries its own version number.
    const modelName = (id, displayName) => {
        const display = (displayName || "").replace(/\s*\([^)]*context[^)]*\)\s*$/i, "").trim();
        if (display && /\d/.test(display)) return display;
        const match = /claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?!\d)/i.exec(id || "");
        if (match) {
            const family = FAMILIES[match[1].toLowerCase()] || match[1];
            return match[3] ? `${family} ${match[2]}.${match[3]}` : `${family} ${match[2]}`;
        }
        return display || id || "Unknown";
    };

    const contextSize = (status) => {
        const size = Number(status.context_window_size);
        if (size > 0) return size;
        const id = (status.model && status.model.id) || "";
        const display = (status.model && status.model.display_name) || "";
        if (/\[1m\]/i.test(id) || /\b1M\b/.test(display)) return 1000000;
        return null;
    };

    const formatTokens = (size) => {
        if (!size) return null;
        if (size >= 1000000) return `${+(size / 1000000).toFixed(1)}M`;
        return `${Math.round(size / 1000)}K`;
    };

    const compareVersions = (a, b) => {
        const pa = String(a).split(/[.-]/).map((part) => parseInt(part, 10) || 0);
        const pb = String(b).split(/[.-]/).map((part) => parseInt(part, 10) || 0);
        for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
            const diff = (pa[i] || 0) - (pb[i] || 0);
            if (diff !== 0) return diff > 0 ? 1 : -1;
        }
        return 0;
    };

    const relativeTime = (date) => {
        const seconds = Math.round((date.getTime() - Date.now()) / 1000);
        const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
        const format = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
        for (const [unit, span] of units) {
            if (Math.abs(seconds) >= span) {
                const text = format.format(Math.round(seconds / span), unit);
                return text.charAt(0).toUpperCase() + text.slice(1);
            }
        }
        return "Just now";
    };

    const getJson = (url) => fetch(url, { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    });

    let installedVersion = null;
    let latestVersion = null;

    const renderUpdateState = () => {
        if (!latestVersion) return;
        setField("latest", latestVersion);
        if (!installedVersion) {
            setBadge("update-state", latestVersion, "info");
        } else if (compareVersions(installedVersion, latestVersion) < 0) {
            setBadge("update-state", `Update to ${latestVersion}`, "warn");
        } else {
            setBadge("update-state", "Up to date", "ok");
        }
    };

    const renderStatus = (status) => {
        const id = (status.model && status.model.id) || "";
        const name = modelName(id, status.model && status.model.display_name);
        const tokens = formatTokens(contextSize(status));

        installedVersion = status.claude_code_version || null;
        setField("version", installedVersion || "Unknown");
        setField("model", name);
        setField("model-full", tokens ? `${name} (${tokens} context)` : name);
        setField("model-id", id || "Not reported");
        setField("context", tokens ? `${tokens} tokens` : "Default");
        setField("context-short", tokens ? `${tokens} context` : "Default context");
        setField("context-note", tokens === "1M"
            ? "Extended context for long sessions and large codebases."
            : "Standard context window for this model.");

        const updated = status.updated_at ? new Date(status.updated_at) : null;
        if (updated && !Number.isNaN(updated.getTime())) {
            const relative = relativeTime(updated);
            const full = updated.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
            const ageDays = (Date.now() - updated.getTime()) / 86400000;
            setField("synced", updated.toISOString().slice(0, 10));
            setField("synced-relative", relative);
            setField("synced-full", status.source ? `${full} · via ${status.source}` : full);
            setBadge("synced-badge", relative, ageDays > 14 ? "warn" : "ok");
        } else {
            setBadge("synced-badge", "Unknown", "warn");
        }

        renderUpdateState();
    };

    const statusUrl = new URL(STATUS_URL);
    statusUrl.searchParams.set("t", Date.now());
    getJson(statusUrl)
        .then(renderStatus)
        .catch(() => {
            setBadge("synced-badge", "Unavailable", "danger");
            setField("synced-relative", "Unavailable");
            setField("synced-full", "status.json could not be loaded. Showing the last values built into the page.");
        });

    if (nodes("latest").length || nodes("update-state").length) {
        getJson(NPM_LATEST_URL)
            .then((pkg) => {
                latestVersion = pkg.version || null;
                renderUpdateState();
            })
            .catch(() => {
                setField("latest", "unavailable");
                setBadge("update-state", "Unavailable", null);
            });
    }
})();
