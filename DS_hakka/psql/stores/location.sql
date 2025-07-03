CREATE TABLE locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 各ロケーションの一意なID（自動採番）
    location_title TEXT NOT NULL,                   -- 地点の名称（travel_data.t_location をコピー）
    travel_data_id INTEGER NOT NULL,                -- 紐づく旅行データのID（外部キー）
    latitude REAL NOT NULL,                         -- 緯度情報
    longitude REAL NOT NULL,                        -- 経度情報
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 作成日時
    FOREIGN KEY(travel_data_id) REFERENCES store(id)  -- 外部キー制約
);


CREATE TABLE locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,     -- 各ロケーションの一意なID（自動採番）
    location_title TEXT NOT NULL,                      -- 地点の名称（store.location をコピー）
    store_id INTEGER NOT NULL,                         -- 紐づく店舗ID（外部キー）
    latitude REAL NOT NULL,                            -- 緯度情報
    longitude REAL NOT NULL,                           -- 経度情報
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,     -- 作成日時
    FOREIGN KEY (store_id) REFERENCES store(store_id)  -- storeテーブルとの外部キー制約
);
