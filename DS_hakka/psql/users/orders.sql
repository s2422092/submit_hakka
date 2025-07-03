CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    status TEXT DEFAULT '注文受付中' CHECK (
        status IN (
            '注文受付中', '受付完了', '商品作成中', '作成直前', '受け取り待ち', 'completed', 'canceled'
        )
    ),
    datetime DATETIME NOT NULL,
    payment_method TEXT CHECK (payment_method IN ('PayPay')),
    total_amount INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (store_id) REFERENCES store(store_id)
);