document.addEventListener('DOMContentLoaded', function () {
    const mapElement = document.getElementById('map');
    const locationData = mapElement.getAttribute('data-locations');
    let locations = JSON.parse(locationData);
    const menuUrlTemplate = mapElement.getAttribute('data-menu-url-template');

    // 地図中心を店舗の平均緯度経度に設定（あれば）
    let centerLat = 35.6769; // デフォルト東京
    let centerLng = 139.7661;

    const map = L.map('map').setView([centerLat, centerLng], 10);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    let markers = [];

    function addMarkers(locs) {
        // 既存マーカー削除
        markers.forEach(m => map.removeLayer(m));
        markers = [];

        locs.forEach(loc => {
            const menuUrl = menuUrlTemplate.replace('/0', '/' + loc.id);

            const popupContent = `
                <div style="font-size: 1em; line-height: 1.5; max-width: 220px;">
                    <div style="font-size: 1.5em;">📍</div>
                    <a href="${menuUrl}" style="font-weight:bold; color:#007bff; text-decoration: none;">
                        ${loc.store_name || '店舗名未登録'}
                    </a><br>
                    <span style="color:#444;">メール: ${loc.email || '未登録'}</span><br>
                    <span style="color:#444;">担当者: ${loc.representative || '不明'}</span><br>
                    <span style="color:#444;">説明: ${loc.description || 'なし'}</span><br>
                    <span style="font-size: 0.8em; color: gray;">※クリックでメニュー画面へ</span>
                </div>
            `;

            const marker = L.marker([loc.lat, loc.lng])
                .addTo(map)
                .bindPopup(popupContent);

            marker.on('mouseover', function () { this.openPopup(); });
            marker.on('mouseout', function () { this.closePopup(); });
            marker.on('click', function () { window.location.href = menuUrl; });

            markers.push(marker);
        });
    }

    // 初期表示
    addMarkers(locations);

    // 検索機能
    const searchInput = document.getElementById('store-search');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const keyword = this.value.trim().toLowerCase();
            const filtered = locations.filter(loc => loc.store_name.toLowerCase().includes(keyword));
            addMarkers(filtered);

            // サイドバー店舗リストの表示切替（DOM操作）
            const storeListItems = document.querySelectorAll('.store-list li');
            storeListItems.forEach(li => {
                const text = li.textContent.toLowerCase();
                if (text.includes(keyword)) {
                    li.style.display = '';
                } else {
                    li.style.display = 'none';
                }
            });
        });
    }
});
