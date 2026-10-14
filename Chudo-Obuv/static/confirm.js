function showConfirm(form) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
        <div class="modal warning" role="dialog" aria-modal="true">
            <h2 class="modal-title">⚠ Подтверждение</h2>
            <p class="modal-text"></p>
            <div class="modal-actions">
                <button class="modal-cancel" type="button">Нет</button>
                <button class="accent-btn" type="button">Да</button>
            </div>
        </div>`;
    overlay.querySelector(".modal-text").textContent = form.dataset.confirm;
    overlay.querySelector(".modal-cancel").addEventListener("click", () => overlay.remove());
    overlay.querySelector(".accent-btn").addEventListener("click", () => form.submit());
    document.body.appendChild(overlay);
}

// Перед необратимым действием форма не отправляется, пока пользователь не нажмёт «Да»
for (const form of document.querySelectorAll("form[data-confirm]")) {
    form.addEventListener("submit", event => {
        event.preventDefault();
        showConfirm(form);
    });
}
