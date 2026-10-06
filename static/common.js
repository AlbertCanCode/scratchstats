(() => {
    const modal = document.getElementById("aboutModal");
    const openBtn = document.getElementById("about-btn");
    const closeBtn = document.querySelector(".close-btn");

    openBtn.addEventListener("click", () => { modal.style.display = "block"; });
    closeBtn.addEventListener("click", () => { modal.style.display = "none"; });
    window.addEventListener("click", (event) => {
        if (event.target === modal) modal.style.display = "none";
    });
})();
