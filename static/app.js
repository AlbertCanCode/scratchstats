(() => {
    const form = document.getElementById("statsForm");
    const statsDiv = document.getElementById("stats");
    const submitBtn = document.getElementById("submitBtn");
    const username1Input = document.getElementById("username1");
    const username2Input = document.getElementById("username2");
    const actionsDiv = document.getElementById("result-actions");
    const copyBtn = document.getElementById("copyLinkBtn");
    const downloadBtn = document.getElementById("downloadBtn");
    const header = document.getElementById("main-header");
    const subheader = document.getElementById("main-subheader");
    const viewMode = form.dataset.mode;

    const VALID_NAME = /^[A-Za-z0-9_-]{1,30}$/;
    let currentSharePath = null;

    // --- Escaping (every Scratch-controlled string goes through this) ---
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
    const fmtNum = (value) => (typeof value === "number" ? value.toLocaleString() : escapeHtml(value));
    const fmtDays = (value) => (typeof value === "number" ? `${value} days` : "N/A");

    // --- Setup View Mode ---
    if (viewMode === "compare") {
        header.textContent = "Compare Two Scratch Users";
        subheader.textContent = "Enter the usernames you want to compare.";
        username2Input.style.display = "block";
        username2Input.required = true;
    } else {
        header.textContent = "Scratch Stats";
        subheader.textContent = "Enter a Scratch username below 👇";
        username2Input.style.display = "none";
        username2Input.required = false;
    }

    // --- Shareable links ---
    function sharePathFor(u1, u2) {
        if (!VALID_NAME.test(u1)) return null;
        if (viewMode === "compare") {
            return VALID_NAME.test(u2) ? `/compare/${encodeURIComponent(u1)}/${encodeURIComponent(u2)}` : null;
        }
        return `/u/${encodeURIComponent(u1)}`;
    }

    // --- Search ---
    async function search(updateUrl) {
        const username1 = username1Input.value.trim();
        const username2 = username2Input.value.trim();

        actionsDiv.hidden = true;
        currentSharePath = null;

        if (!username1) {
            statsDiv.textContent = "❌ Please enter a username.";
            return;
        }
        if (viewMode === "compare" && !username2) {
            statsDiv.textContent = "❌ Please enter both usernames for comparison.";
            return;
        }

        statsDiv.innerHTML = '<div class="loading-spinner"></div> Fetching data...';
        submitBtn.disabled = true;
        submitBtn.textContent = "Fetching...";

        const params = new URLSearchParams();
        params.append("username1", username1);
        if (viewMode === "compare" && username2) params.append("username2", username2);

        try {
            const res = await fetch("/api/stats", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: params.toString(),
            });

            const response = await res.json();

            if (!res.ok) {
                statsDiv.textContent = `❌ Error: ${response.error || "Could not connect to server/API."}`;
                return;
            }

            const data = response.data;
            const errors = response.errors || {};

            if (viewMode === "compare" && data.user1 && data.user2) {
                statsDiv.innerHTML = renderComparison(data.user1, data.user2, errors);
            } else if (data.user1 && viewMode === "compare") {
                statsDiv.innerHTML = renderSingle(data.user1, errors.user1, "⚠️ Only one user loaded. Comparison requires both users to be found.");
            } else if (data.user1) {
                statsDiv.innerHTML = renderSingle(data.user1, errors.user1);
            } else {
                statsDiv.textContent = `❌ Could not retrieve any statistics. ${errors.user1 || errors.user2 || ""}`;
                return;
            }

            const historyBox = statsDiv.querySelector(".history-section");
            if (historyBox) loadHistory(historyBox);

            currentSharePath = sharePathFor(username1, username2);
            copyBtn.hidden = !currentSharePath;
            actionsDiv.hidden = false;
            if (updateUrl && currentSharePath && location.pathname !== currentSharePath) {
                history.pushState(null, "", currentSharePath);
            }
        } catch (err) {
            console.error(err);
            statsDiv.textContent = "❌ Network error. Please check your connection or try again.";
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = "Get Stats";
        }
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        search(true);
    });

    window.addEventListener("popstate", () => location.reload());

    // Open straight to results when arriving via a shared link
    username1Input.value = form.dataset.user1 || "";
    username2Input.value = form.dataset.user2 || "";
    if (username1Input.value && (viewMode !== "compare" || username2Input.value)) {
        search(false);
    }

    // --- Copy link ---
    copyBtn.addEventListener("click", async () => {
        if (!currentSharePath) return;
        const url = location.origin + currentSharePath;
        const original = copyBtn.textContent;
        try {
            await navigator.clipboard.writeText(url);
            copyBtn.textContent = "✅ Link copied!";
            setTimeout(() => { copyBtn.textContent = original; }, 2000);
        } catch (err) {
            window.prompt("Copy this link:", url);
        }
    });

    // --- Download as image ---
    function loadHtml2Canvas() {
        if (window.html2canvas) return Promise.resolve(window.html2canvas);
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
            script.onload = () => resolve(window.html2canvas);
            script.onerror = () => reject(new Error("Could not load the image exporter."));
            document.head.appendChild(script);
        });
    }

    downloadBtn.addEventListener("click", async () => {
        const original = downloadBtn.textContent;
        downloadBtn.disabled = true;
        downloadBtn.textContent = "Rendering...";

        // Swap Scratch CDN images for same-origin copies so the canvas isn't tainted by CORS.
        const images = [...statsDiv.querySelectorAll("img[data-proxy]")];
        const originalSrcs = images.map((img) => img.src);

        try {
            const html2canvas = await loadHtml2Canvas();
            await Promise.all(images.map((img) => new Promise((resolve) => {
                img.onload = img.onerror = resolve;
                img.src = img.dataset.proxy;
            })));

            const canvas = await html2canvas(statsDiv, { backgroundColor: "#101010", scale: 2, useCORS: true });
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
            if (!blob) throw new Error("Image export failed.");

            const names = [username1Input.value.trim(), viewMode === "compare" ? username2Input.value.trim() : ""]
                .filter(Boolean)
                .map((n) => n.replace(/[^A-Za-z0-9_-]/g, ""));
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `scratchstats-${names.join("-vs-")}.png`;
            link.click();
            setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        } catch (err) {
            console.error(err);
            alert("Sorry, the image couldn't be created. Please try again.");
        } finally {
            images.forEach((img, i) => { img.onload = img.onerror = null; img.src = originalSrcs[i]; });
            downloadBtn.disabled = false;
            downloadBtn.textContent = original;
        }
    });

    // --- Highlighting Helpers ---
    // mode: "higher" (bigger wins), "lower" (smaller wins), "neutral" (no winner)
    function getComparisonClass(val1, val2, mode = "higher") {
        if (mode === "neutral") return "";
        if (typeof val1 !== "number" || typeof val2 !== "number") return "";
        if (val1 === val2) return val1 !== 0 ? "highlight-tie" : "";
        const firstWins = mode === "lower" ? val1 < val2 : val1 > val2;
        return firstWins ? "highlight-winner" : "highlight-loser";
    }

    function compareAndRenderStat(key, label, data1, data2, mode = "higher") {
        const val1 = data1[key];
        const val2 = data2[key];

        const formatValue = (value) => {
            if (key.includes("avg")) return typeof value === "number" ? value.toFixed(2) : escapeHtml(value);
            if (key === "days_since_last_project") return fmtDays(value);
            return fmtNum(value);
        };

        return {
            html1: `<p class="${getComparisonClass(val1, val2, mode)}"><strong>${label}:</strong> ${formatValue(val1)}</p>`,
            html2: `<p class="${getComparisonClass(val2, val1, mode)}"><strong>${label}:</strong> ${formatValue(val2)}</p>`,
        };
    }

    // --- Rendering ---
    function renderSingle(data, errorMsg, notice = "") {
        if (errorMsg) {
            return `<div class="error-message">❌ ${escapeHtml(errorMsg)}</div>`;
        }

        return `
            <div class="stats-container single-user">
                ${notice ? `<div class="notice-message">${escapeHtml(notice)}</div>` : ""}
                ${renderProfileHeader(data)}
                <div class="user-info">
                    <p><strong>🆔 ID:</strong> ${fmtNum(data.id)}</p>
                    <p><strong>📅 Joined:</strong> ${escapeHtml(data.joined)}</p>
                    <p><strong>🌍 Country:</strong> ${escapeHtml(data.country)}</p>
                    <p><strong>🕒 Latest Project:</strong> ${escapeHtml(data.most_recent_activity)}</p>
                    <p><strong>⏳ Days Since Project:</strong> ${fmtDays(data.days_since_last_project)}</p>
                </div>

                ${renderActivity(data)}

                <div class="stats-grid">
                    ${renderCoreStats(data)}
                    ${renderAverageStats(data)}
                </div>

                ${renderProjectHighlights(data)}

                <div class="history-section" data-username="${escapeHtml(data.username)}"></div>
            </div>
        `;
    }

    function renderComparison(data1, data2, errors) {
        // Higher is better
        const followerStats = compareAndRenderStat("followers", "👥 Followers", data1, data2);
        const totalProjectsStats = compareAndRenderStat("project_count", "📁 Total Projects", data1, data2);
        const favedProjectsStats = compareAndRenderStat("favorited_projects_count", "⭐ Projects Faved", data1, data2);
        const totalFavesStats = compareAndRenderStat("total_favorites_received", "✨ TOTAL FAVES REC", data1, data2);
        const totalLovesStats = compareAndRenderStat("total_loves", "❤️ TOTAL LOVES REC", data1, data2);
        const totalViewsStats = compareAndRenderStat("total_views", "👁️ Total Views", data1, data2);
        const avgLovesStats = compareAndRenderStat("avg_loves", "❤️ Avg. Loves/Project", data1, data2);
        const avgFavesStats = compareAndRenderStat("avg_favorites", "✨ Avg. Faves/Project", data1, data2);
        const avgViewsStats = compareAndRenderStat("avg_views", "👁️ Avg. Views/Project", data1, data2);

        // Following more people isn't "better" or "worse"
        const followingStats = compareAndRenderStat("following", "➕ Following", data1, data2, "neutral");

        // Lower is better
        const daysSinceStats = compareAndRenderStat("days_since_last_project", "⏳ Days Since Project", data1, data2, "lower");

        const lovedClass1 = getComparisonClass(data1.most_loved?.loves ?? 0, data2.most_loved?.loves ?? 0);
        const lovedClass2 = getComparisonClass(data2.most_loved?.loves ?? 0, data1.most_loved?.loves ?? 0);
        const viewedClass1 = getComparisonClass(data1.most_viewed?.views ?? 0, data2.most_viewed?.views ?? 0);
        const viewedClass2 = getComparisonClass(data2.most_viewed?.views ?? 0, data1.most_viewed?.views ?? 0);

        const renderColumn = (data, isUser1) => {
            const error = isUser1 ? errors.user1 : errors.user2;
            if (error) {
                return `<div class="user-col error-message">❌ ${escapeHtml(error)}</div>`;
            }

            const pick = (stats) => (isUser1 ? stats.html1 : stats.html2);

            return `
                <div class="user-col">
                    <h3 class="col-header">${escapeHtml(data.username)}</h3>
                    ${renderProfileHeader(data)}
                    <div class="user-info">
                        <p><strong>🆔 ID:</strong> ${fmtNum(data.id)}</p>
                        <p><strong>📅 Joined:</strong> ${escapeHtml(data.joined)}</p>
                        <p><strong>🌍 Country:</strong> ${escapeHtml(data.country)}</p>
                        <p><strong>🕒 Latest Project:</strong> ${escapeHtml(data.most_recent_activity)}</p>
                        ${pick(daysSinceStats)}
                    </div>
                    <div class="stats-grid comparison-grid">
                        ${pick(followerStats)}
                        ${pick(followingStats)}
                        ${pick(totalProjectsStats)}
                        ${pick(favedProjectsStats)}
                        ${pick(totalFavesStats)}
                        ${pick(totalLovesStats)}
                        ${pick(totalViewsStats)}
                        ${pick(avgLovesStats)}
                        ${pick(avgFavesStats)}
                        ${pick(avgViewsStats)}
                    </div>
                    ${renderTopProjectComparison(data, isUser1 ? lovedClass1 : lovedClass2, isUser1 ? viewedClass1 : viewedClass2)}
                </div>
            `;
        };

        return `
            <div class="comparison-container">
                ${renderColumn(data1, true)}
                ${renderColumn(data2, false)}
            </div>
            <div class="highlight-key">
                <span class="highlight-winner">Winner</span>
                <span class="highlight-loser">Loser</span>
                <span class="highlight-tie">Tie</span>
            </div>
        `;
    }

    function renderProfileHeader(data) {
        return `
            <div class="profile">
                <img src="${escapeHtml(data.profile_pic)}" data-proxy="/img/user/${Number(data.id)}" alt="Profile Picture">
                <div>
                    <h2>${escapeHtml(data.username)}
                        ${data.scratchteam ? '<span class="scratch-team-badge">⭐️ Scratch Team</span>' : ""}
                    </h2>
                    <a href="https://scratch.mit.edu/users/${encodeURIComponent(data.username)}" target="_blank" rel="noopener" class="profile-btn">View Profile ↗️</a>
                </div>
            </div>
        `;
    }

    function renderActivity(data) {
        return `
            <div class="activity-section">
                <h4>💬 About Me</h4>
                <p class="activity-content">${escapeHtml(data.about_me) || "Nothing here yet!"}</p>
                <h4>💻 What I'm Working On</h4>
                <p class="activity-content">${escapeHtml(data.wiwo) || "Nothing here yet!"}</p>
            </div>
        `;
    }

    function renderCoreStats(data) {
        return `
            <p><strong>👥 Followers:</strong> ${fmtNum(data.followers)}</p>
            <p><strong>➕ Following:</strong> ${fmtNum(data.following)}</p>
            <p><strong>📁 Total Projects:</strong> ${fmtNum(data.project_count)}</p>
            <p><strong>⭐ Projects Faved:</strong> ${fmtNum(data.favorited_projects_count)}</p>
            <p><strong>✨ TOTAL FAVES REC:</strong> ${fmtNum(data.total_favorites_received)}</p>
            <p><strong>❤️ TOTAL LOVES REC:</strong> ${fmtNum(data.total_loves)}</p>
            <p><strong>👁️ Total Views:</strong> ${fmtNum(data.total_views)}</p>
        `;
    }

    function renderAverageStats(data) {
        return `
            <p><strong>❤️ Avg. Loves/Project:</strong> ${Number(data.avg_loves).toFixed(2)}</p>
            <p><strong>✨ Avg. Faves/Project:</strong> ${Number(data.avg_favorites).toFixed(2)}</p>
            <p><strong>👁️ Avg. Views/Project:</strong> ${Number(data.avg_views).toFixed(2)}</p>
        `;
    }

    function renderProjectHighlights(data) {
        if (!(data.most_loved || data.most_viewed || data.most_recent)) return "<p>No projects found.</p>";

        return `
            <div class="project-highlights-container">
                ${renderProjectBox(data.most_recent, "🕒 Newest Project", "🕒 Created", "id", "loves", "views", "favorites")}
                ${renderProjectBox(data.most_loved, "🏆 Most Loved Project", "❤️ Loves", "loves", "views", "favorites")}
                ${renderProjectBox(data.most_viewed, "👁️ Most Viewed Project", "👁️ Views", "views", "loves", "favorites")}
            </div>
        `;
    }

    function renderTopProjectComparison(data, lovedClass, viewedClass) {
        const { most_loved: loved, most_viewed: viewed, most_recent: recent } = data;
        if (!loved && !viewed && !recent) return "";

        const link = (project, cls = "") =>
            `<a href="https://scratch.mit.edu/projects/${Number(project.id)}" target="_blank" rel="noopener" class="${cls}">${escapeHtml(project.title)}</a>`;

        return `
            <div class="comparison-project-summary">
                <h4>Top Projects</h4>
                ${recent ? `<p><strong>🕒 Recent:</strong> ${link(recent)}</p>` : ""}
                ${loved ? `<p><strong>🏆 Loved:</strong> ${link(loved, lovedClass)} (${fmtNum(loved.loves)})</p>` : ""}
                ${viewed ? `<p><strong>👁️ Viewed:</strong> ${link(viewed, viewedClass)} (${fmtNum(viewed.views)})</p>` : ""}
            </div>
        `;
    }

    function renderProjectBox(project, title, metricLabel, metricKey, ...otherKeys) {
        if (!project) return "";

        let statsHtml = metricKey === "id"
            ? `<span>${metricLabel} (ID ${Number(project.id)})</span>`
            : `<span>${metricLabel} ${fmtNum(project[metricKey])}</span>`;

        otherKeys.forEach((key) => {
            const label = key === "loves" ? "❤️" : key === "views" ? "👁️" : key === "favorites" ? "⭐" : "";
            if (label) statsHtml += `<span>${label} ${fmtNum(project[key] || 0)}</span>`;
        });

        const id = Number(project.id);
        return `
            <div class="project-box">
                <h3>${title}</h3>
                <img src="https://cdn2.scratch.mit.edu/get_image/project/${id}_144x108.png" data-proxy="/img/project/${id}"
                     alt="${escapeHtml(project.title)} thumbnail" class="project-thumbnail">
                <p class="project-title">${escapeHtml(project.title)}</p>
                <div class="project-stats">
                    ${statsHtml}
                </div>
                <a href="https://scratch.mit.edu/projects/${id}" target="_blank" rel="noopener" class="project-btn">View Project ↗️</a>
            </div>
        `;
    }

    // --- Growth history chart ---
    const HISTORY_METRICS = [
        { key: "followers", label: "👥 Followers" },
        { key: "loves", label: "❤️ Loves" },
        { key: "favorites", label: "✨ Faves" },
        { key: "views", label: "👁️ Views" },
        { key: "projects", label: "📁 Projects" },
    ];
    const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

    async function loadHistory(container) {
        container.innerHTML = '<h4>📈 Growth History</h4><p class="history-note">Loading history...</p>';
        try {
            const res = await fetch(`/api/history/${encodeURIComponent(container.dataset.username)}`);
            const { points } = await res.json();
            renderHistory(container, points);
        } catch (err) {
            console.error(err);
            container.innerHTML = "";
        }
    }

    function renderHistory(container, points) {
        if (points.length < 2) {
            const since = points.length ? escapeHtml(points[0].day) : "today";
            container.innerHTML = `
                <h4>📈 Growth History</h4>
                <p class="history-note">Tracking started ${since}. Look this user up again on another day to see how their stats grow.</p>
            `;
            return;
        }

        container.innerHTML = `
            <h4>📈 Growth History</h4>
            <div class="tab-row history-tabs">
                ${HISTORY_METRICS.map((m, i) => `<button type="button" class="tab-btn${i === 0 ? " active" : ""}" data-metric="${m.key}">${m.label}</button>`).join("")}
            </div>
            <div class="history-chart"></div>
        `;
        const chart = container.querySelector(".history-chart");
        const draw = (metric) => { chart.innerHTML = lineChartSvg(points, metric); };

        container.querySelector(".history-tabs").addEventListener("click", (e) => {
            const btn = e.target.closest(".tab-btn");
            if (!btn) return;
            container.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
            draw(btn.dataset.metric);
        });
        draw(HISTORY_METRICS[0].key);
    }

    function lineChartSvg(points, metric) {
        const W = 640, H = 240, L = 56, R = 16, T = 16, B = 34;
        const times = points.map((p) => Date.parse(`${p.day}T00:00:00Z`));
        const values = points.map((p) => p[metric]);
        const tMin = times[0], tMax = times[times.length - 1];
        let vMin = Math.min(...values), vMax = Math.max(...values);
        if (vMin === vMax) { vMin -= 1; vMax += 1; }

        const x = (t) => L + ((t - tMin) / (tMax - tMin || 1)) * (W - L - R);
        const y = (v) => T + (1 - (v - vMin) / (vMax - vMin)) * (H - T - B);

        const grid = [0, 1, 2, 3].map((i) => {
            const v = vMin + ((vMax - vMin) * i) / 3;
            return `<line class="chart-grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"></line>
                    <text class="chart-label" x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${compact.format(Math.round(v))}</text>`;
        }).join("");

        const line = points.map((p, i) => `${x(times[i]).toFixed(1)},${y(values[i]).toFixed(1)}`).join(" ");
        const dots = points.map((p, i) =>
            `<circle class="chart-dot" cx="${x(times[i]).toFixed(1)}" cy="${y(values[i]).toFixed(1)}" r="4">
                <title>${escapeHtml(p.day)}: ${values[i].toLocaleString()}</title>
            </circle>`).join("");

        const change = values[values.length - 1] - values[0];
        const changeText = `${change >= 0 ? "+" : ""}${change.toLocaleString()} since ${escapeHtml(points[0].day)}`;

        return `
            <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Growth chart" class="history-svg">
                ${grid}
                <polyline class="chart-line" points="${line}"></polyline>
                ${dots}
                <text class="chart-label" x="${L}" y="${H - 8}" text-anchor="start">${escapeHtml(points[0].day)}</text>
                <text class="chart-label" x="${W - R}" y="${H - 8}" text-anchor="end">${escapeHtml(points[points.length - 1].day)}</text>
            </svg>
            <p class="history-note">${changeText}</p>
        `;
    }
})();
