document.addEventListener('DOMContentLoaded', function () {
    const addCartUrl = '/users_order/add_to_cart';

    const categoryButtons = document.querySelectorAll('.category-btn');
    const searchInput = document.getElementById('menu-search');
    const menuCards = document.querySelectorAll('.menu-card');

    // --- 数量操作・カート追加機能 ---
    menuCards.forEach(card => {
        const menuId = card.dataset.menuId;
        const qtyInput = card.querySelector('.qty-input');
        const upBtn = card.querySelector('.qty-up-btn');
        const downBtn = card.querySelector('.qty-down-btn');
        const addBtn = card.querySelector('.add-to-cart-btn');

        if (qtyInput && upBtn && downBtn && addBtn) {
            upBtn.addEventListener('click', () => {
                qtyInput.value = parseInt(qtyInput.value) + 1;
            });

            downBtn.addEventListener('click', () => {
                let currentQty = parseInt(qtyInput.value);
                if (currentQty > 1) {
                    qtyInput.value = currentQty - 1;
                }
            });

            addBtn.addEventListener('click', () => {
                const quantity = parseInt(qtyInput.value);
                fetch(addCartUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        menu_id: menuId,
                        quantity: quantity
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        displayFlashMessage(data.error, 'error');
                    } else {
                        displayFlashMessage(data.message, 'success');
                        document.getElementById('cart-count').textContent = data.cart_count;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    displayFlashMessage('通信エラーが発生しました。', 'error');
                });
            });
        }
    });

    // --- カテゴリ・検索によるフィルタ ---
    function filterMenuItems() {
        const activeCategory = document.querySelector('.category-btn.active')?.dataset.category || "all";
        const keyword = searchInput.value.trim().toLowerCase();

        menuCards.forEach(card => {
            const categoryEl = card.querySelector('.item-category');
            const nameEl = card.querySelector('.item-name');

            const category = categoryEl ? categoryEl.textContent.trim() : "";
            const name = nameEl ? nameEl.textContent.trim().toLowerCase() : "";

            const matchesCategory = activeCategory === "all" || category === activeCategory;
            const matchesSearch = name.includes(keyword);

            card.style.display = (matchesCategory && matchesSearch) ? "" : "none";
        });
    }

    // カテゴリーボタンにクリックイベントを追加
    categoryButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            categoryButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterMenuItems();
        });
    });

    // 検索バーの入力でフィルタを実行
    if (searchInput) {
        searchInput.addEventListener('input', filterMenuItems);
    }

    // 初期化：最初に「すべて」ボタンを選択状態にしておく
    const allBtn = document.querySelector(".category-btn[data-category='all']");
    if (allBtn) {
        allBtn.classList.add("active");
    }
    filterMenuItems();

    // --- フラッシュメッセージ表示用関数 ---
    function displayFlashMessage(message, category) {
        const container = document.getElementById('flash-message-container');
        if (!container) return;
        const messageDiv = document.createElement('div');
        messageDiv.className = `flash ${category}`;
        messageDiv.textContent = message;
        container.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.style.opacity = '0';
            setTimeout(() => {
                messageDiv.remove();
            }, 500);
        }, 3000);
    }
});
