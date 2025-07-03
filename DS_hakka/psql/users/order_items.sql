CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    menu_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price_at_order INTEGER NOT NULL, 
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (menu_id) REFERENCES menus(menu_id)
);