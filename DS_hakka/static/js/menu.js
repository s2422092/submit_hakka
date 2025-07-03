document.addEventListener('DOMContentLoaded', function () {

    const addCartUrl = '/users_order/add_to_cart';

    const categoryButtons = document.querySelectorAll('.category-btn');
    const searchInput = document.getElementById('menu-search');
    const menuCards = document.querySelectorAll('.menu-card');

    // --- 数量操作・カート追加機能 ---
    menuCards.forEach(card => {
        const menuId = card.dataset.menuId;
        const qtyInput = card.querySelector('.qty-input');
        const addToCartBtn = card.querySelector('.add-to-cart-btn'); // ボタン要素を取得

        card.querySelector('.qty-up-btn').addEventListener('click', () => {
            qtyInput.value = parseInt(qtyInput.value) + 1;
        });

        card.querySelector('.qty-down-btn').addEventListener('click', () => {
            let currentQty = parseInt(qtyInput.value);
            if (currentQty > 1) {
                qtyInput.value = currentQty - 1;
            }
        });

        addToCartBtn.addEventListener('click', () => {
            const quantity = parseInt(qtyInput.value);
            
            // ★★★ UIフィードバック開始 ★★★
            // ボタンを無効化し、スタイルを変更
            addToCartBtn.disabled = true;
            addToCartBtn.classList.add('loading');
            addToCartBtn.textContent = '追加中...';

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
                addToCartBtn.classList.remove('loading'); // ローディングスタイルを削除

                if (data.error) {
                    displayFlashMessage(data.error, 'error');
                    // エラー時はボタンを元に戻す
                    addToCartBtn.textContent = 'カートに追加';
                    addToCartBtn.disabled = false;
                } else {
                    displayFlashMessage(data.message, 'success');
                    document.getElementById('cart-count').textContent = data.cart_count;

                    // ★★★ 成功時のUIフィードバック ★★★
                    addToCartBtn.classList.add('success');
                    addToCartBtn.textContent = '追加しました ✔';

                    // 2秒後にボタンを元の状態に戻す
                    setTimeout(() => {
                        addToCartBtn.classList.remove('success');
                        addToCartBtn.textContent = 'カートに追加';
                        addToCartBtn.disabled = false;
                    }, 2000);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                displayFlashMessage('通信エラーが発生しました。', 'error');
                // エラー時はボタンを元に戻す
                addToCartBtn.classList.remove('loading');
                addToCartBtn.textContent = 'カートに追加';
                addToCartBtn.disabled = false;
            });
        });
    });

    // --- カテゴリ・検索によるフィルタ ---
    function filterMenuItems() {
        const activeCategory = document.querySelector('.category-btn.active')?.dataset.category || "all";
        const keyword = searchInput.value.trim().toLowerCase();

        menuCards.forEach(card => {
            const category = card.querySelector('.item-category').textContent.trim();
            const name = card.querySelector('.item-name').textContent.trim().toLowerCase();

            const matchesCategory = activeCategory === "all" || category === activeCategory;
            const matchesSearch = name.includes(keyword);

            if (matchesCategory && matchesSearch) {
                card.style.display = "";
            } else {
                card.style.display = "none";
            }
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
