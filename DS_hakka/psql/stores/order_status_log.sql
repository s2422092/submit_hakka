CREATE TABLE order_status_log (
    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        '注文受付中', '受付完了', '商品作成中', '作成直前', '受け取り待ち'
    )),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
