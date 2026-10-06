(() => {
    const tabs = document.getElementById("leaderboardTabs");
    const box = document.getElementById("leaderboard");

    const COLUMNS = [
        { key: "followers", label: "👥 Followers" },
        { key: "loves", label: "❤️ Loves" },
        { key: "favorites", label: "✨ Faves" },
        { key: "views", label: "👁️ Views" },
        { key: "projects", label: "📁 Projects" },
    ];
    const MEDALS = ["🥇", "🥈", "🥉"];

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));

    let metric = "followers";
    let page = 1;

    function readUrl() {
        const params = new URLSearchParams(location.search);
        const requested = params.get("metric");
        metric = COLUMNS.some((c) => c.key === requested) ? requested : "followers";
        page = Math.max(1, parseInt(params.get("page"), 10) || 1);
    }

    function writeUrl(push) {
        const url = `?metric=${metric}${page > 1 ? `&page=${page}` : ""}`;
        history[push ? "pushState" : "replaceState"](null, "", url);
    }

    function renderTabs() {
        tabs.innerHTML = COLUMNS.map((c) =>
            `<button type="button" class="tab-btn${c.key === metric ? " active" : ""}" data-metric="${c.key}">${c.label}</button>`
        ).join("");
    }

    // 1 … 4 5 [6] 7 8 … 20
    function pageNumbers(current, total) {
        const wanted = new Set([1, total, current - 1, current, current + 1]);
        const nums = [...wanted].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
        const out = [];
        nums.forEach((n, i) => {
            if (i > 0 && n - nums[i - 1] > 1) out.push("gap");
            out.push(n);
        });
        return out;
    }

    function renderPager(current, total) {
        if (total <= 1) return "";
        const numbers = pageNumbers(current, total).map((n) => n === "gap"
            ? '<span class="pager-gap">…</span>'
            : `<button type="button" class="tab-btn${n === current ? " active" : ""}" data-page="${n}" aria-label="Page ${n}"${n === current ? ' aria-current="page"' : ""}>${n}</button>`
        ).join("");
        return `
            <div class="pager" role="navigation" aria-label="Leaderboard pages">
                <button type="button" class="tab-btn" data-page="${current - 1}"${current === 1 ? " disabled" : ""}>← Prev</button>
                ${numbers}
                <button type="button" class="tab-btn" data-page="${current + 1}"${current === total ? " disabled" : ""}>Next →</button>
            </div>
        `;
    }

    function renderTable(body) {
        const { users, total } = body;
        if (!users.length) {
            box.innerHTML = '<p class="history-note">No one is on the leaderboard yet. Look up a Scratch user to add them!</p>';
            return;
        }

        const head = COLUMNS.map((c) => `<th class="${c.key === metric ? "sorted" : ""}">${c.label}</th>`).join("");
        const rows = users.map((u) => {
            const cells = COLUMNS.map((c) =>
                `<td class="${c.key === metric ? "sorted" : ""}">${Number(u[c.key]).toLocaleString()}</td>`).join("");
            return `
                <tr>
                    <td class="rank">${MEDALS[u.rank - 1] || Number(u.rank)}</td>
                    <td class="lb-user">
                        <img src="https://uploads.scratch.mit.edu/get_image/user/${Number(u.id)}_90x90.png" alt="" loading="lazy">
                        <a href="/u/${encodeURIComponent(u.username)}">${escapeHtml(u.username)}</a>
                    </td>
                    ${cells}
                </tr>`;
        }).join("");

        const first = Number(users[0].rank);
        const last = Number(users[users.length - 1].rank);

        box.innerHTML = `
            <div class="table-scroll">
                <table class="leaderboard-table">
                    <thead><tr><th>#</th><th class="lb-user-head">Scratcher</th>${head}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            ${renderPager(body.page, body.pages)}
            <p class="history-note">Showing ${first}–${last} of ${Number(total).toLocaleString()}. Stats are from each user's most recent lookup on this site.</p>
        `;
    }

    async function load() {
        renderTabs();
        box.innerHTML = '<div class="loading-spinner"></div> Loading...';
        try {
            const res = await fetch(`/api/leaderboard?metric=${encodeURIComponent(metric)}&page=${page}`);
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || "Request failed");
            if (body.page !== page) {   // asked for a page past the end
                page = body.page;
                writeUrl(false);
            }
            renderTable(body);
        } catch (err) {
            console.error(err);
            box.textContent = "❌ Couldn't load the leaderboard. Please try again.";
        }
    }

    tabs.addEventListener("click", (e) => {
        const btn = e.target.closest(".tab-btn");
        if (!btn || btn.dataset.metric === metric) return;
        metric = btn.dataset.metric;
        page = 1;
        writeUrl(false);
        load();
    });

    box.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-page]");
        if (!btn || btn.disabled) return;
        page = Number(btn.dataset.page);
        writeUrl(true);
        load().then(() => tabs.scrollIntoView({ behavior: "smooth", block: "start" }));
    });

    window.addEventListener("popstate", () => {
        readUrl();
        load();
    });

    readUrl();
    load();
})();
