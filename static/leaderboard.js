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

    const requested = new URLSearchParams(location.search).get("metric");
    let metric = COLUMNS.some((c) => c.key === requested) ? requested : "followers";

    function renderTabs() {
        tabs.innerHTML = COLUMNS.map((c) =>
            `<button type="button" class="tab-btn${c.key === metric ? " active" : ""}" data-metric="${c.key}">${c.label}</button>`
        ).join("");
    }

    function renderTable(users) {
        if (!users.length) {
            box.innerHTML = '<p class="history-note">No one is on the leaderboard yet. Look up a Scratch user to add them!</p>';
            return;
        }

        const head = COLUMNS.map((c) => `<th class="${c.key === metric ? "sorted" : ""}">${c.label}</th>`).join("");
        const rows = users.map((u, i) => {
            const cells = COLUMNS.map((c) =>
                `<td class="${c.key === metric ? "sorted" : ""}">${Number(u[c.key]).toLocaleString()}</td>`).join("");
            return `
                <tr>
                    <td class="rank">${MEDALS[i] || i + 1}</td>
                    <td class="lb-user">
                        <img src="https://uploads.scratch.mit.edu/get_image/user/${Number(u.id)}_90x90.png" alt="" loading="lazy">
                        <a href="/u/${encodeURIComponent(u.username)}">${escapeHtml(u.username)}</a>
                    </td>
                    ${cells}
                </tr>`;
        }).join("");

        box.innerHTML = `
            <div class="table-scroll">
                <table class="leaderboard-table">
                    <thead><tr><th>#</th><th class="lb-user-head">Scratcher</th>${head}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            <p class="history-note">Stats are from each user's most recent lookup on this site.</p>
        `;
    }

    async function load() {
        renderTabs();
        box.innerHTML = '<div class="loading-spinner"></div> Loading...';
        try {
            const res = await fetch(`/api/leaderboard?metric=${encodeURIComponent(metric)}`);
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || "Request failed");
            renderTable(body.users);
        } catch (err) {
            console.error(err);
            box.textContent = "❌ Couldn't load the leaderboard. Please try again.";
        }
    }

    tabs.addEventListener("click", (e) => {
        const btn = e.target.closest(".tab-btn");
        if (!btn || btn.dataset.metric === metric) return;
        metric = btn.dataset.metric;
        history.replaceState(null, "", `?metric=${metric}`);
        load();
    });

    load();
})();
