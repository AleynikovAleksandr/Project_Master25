const search = document.getElementById("search");
const category = document.getElementById("category");
const sort = document.getElementById("sort");
const list = document.getElementById("products");
const empty = document.getElementById("empty");

function updateList() {
    const text = search.value.trim().toLowerCase();
    const cards = Array.from(list.children);
    let visible = 0;

    for (const card of cards) {
        const textOk = card.dataset.text.includes(text);
        const categoryOk = category.value === "" || card.dataset.category === category.value;
        card.hidden = !(textOk && categoryOk);
        if (!card.hidden) {
            visible++;
        }
    }

    if (sort.value === "asc") {
        cards.sort((a, b) => a.dataset.price - b.dataset.price);
    } else if (sort.value === "desc") {
        cards.sort((a, b) => b.dataset.price - a.dataset.price);
    } else {
        // Возвращаем исходный порядок карточек
        cards.sort((a, b) => a.dataset.index - b.dataset.index);
    }
    cards.forEach(card => list.appendChild(card));

    empty.hidden = visible > 0;
}

search.addEventListener("input", updateList);
category.addEventListener("change", updateList);
sort.addEventListener("change", updateList);
