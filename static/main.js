// main.js
// Функция установки cookie
function setCookie(name, value, days) {
    const expires = days ? "; expires=" + new Date(Date.now() + days*864e5).toUTCString() : "";
    document.cookie = name + "=" + encodeURIComponent(value) + expires + "; path=/";
}

// Функция получения cookie по имени
function getCookie(name) {
    return document.cookie.split('; ').reduce((r, v) => {
        const parts = v.split('=');
        return parts[0] === name ? decodeURIComponent(parts[1]) : r
    }, '');
}

// Значения по умолчанию
const defaultFilters = {
    volMin: "10000",
    growth6h: "100",
    growth1h: "100",
    priceChangeMax: "10",
    priceChangeMin: "0",
    marketCapRank: ""  // Если пустая строка, значит фильтр не применяется
};

// Функция загрузки фильтров из cookie и заполнения формы
function loadFiltersFromCookie() {
    const volMin = getCookie("volMin") || defaultFilters.volMin;
    const growth6h = getCookie("growth6h") || defaultFilters.growth6h;
    const growth1h = getCookie("growth1h") || defaultFilters.growth1h;
    const priceChangeMax = getCookie("priceChangeMax") || defaultFilters.priceChangeMax;
    const priceChangeMin = getCookie("priceChangeMin") || defaultFilters.priceChangeMin;
    const marketCapRank = getCookie("marketCapRank") || defaultFilters.marketCapRank;

    document.getElementById("vol-min").value = volMin;
    document.getElementById("growth6h").value = growth6h;
    document.getElementById("growth1h").value = growth1h;
    document.getElementById("price-change-max").value = priceChangeMax;
    document.getElementById("price-change-min").value = priceChangeMin;
    document.getElementById("market-cap-rank").value = marketCapRank;
}

// Функция открытия модального окна для фильтров
function openFiltersModal() {
    const modal = document.getElementById('filter-modal');
    modal.style.display = 'block';
    loadFiltersFromCookie(); // Предзаполнить поля значениями из cookies
}

// Функция закрытия модального окна для фильтров
function closeFiltersModal() {
    document.getElementById('filter-modal').style.display = 'none';
}

// Функция сохранения фильтров: считываем значения из формы и сохраняем их в cookies
function saveFilters() {
    const volMin = document.getElementById("vol-min").value;
    const growth6h = document.getElementById("growth6h").value;
    const growth1h = document.getElementById("growth1h").value;
    const priceChangeMax = document.getElementById("price-change-max").value;
    const priceChangeMin = document.getElementById("price-change-min").value;
    const marketCapRank = document.getElementById("market-cap-rank").value;

    // Сохраняем каждое значение в cookie (на 30 дней)
    setCookie("volMin", volMin, 30);
    setCookie("growth6h", growth6h, 30);
    setCookie("growth1h", growth1h, 30);
    setCookie("priceChangeMax", priceChangeMax, 30);
    setCookie("priceChangeMin", priceChangeMin, 30);
    setCookie("marketCapRank", marketCapRank, 30);

    closeFiltersModal();

    // Вызываем функцию для обновления данных (например, через AJAX или перезагрузка страницы)
    refreshCryptoData();
}

// Пример функции для обновления данных (можно заменить на нужную реализацию)
function refreshCryptoData() {
    // Здесь можно собрать параметры из cookies и отправить AJAX запрос на сервер для получения новых данных.
    // Пример: просто перезагрузим страницу
    location.reload();
}

function formatAnalyticsContent(content) {
    if (!content) return '';

    return content
        .replace(/###\s*(.*?)\n/g, '<h3>$1</h3>') // Преобразуем ### в заголовки
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Преобразуем **text** в жирный текст
        .replace(/\n/g, '<br>'); // Преобразуем новые строки в <br>
}

function showAIAnalytics(name, symbol) {
    const modal = document.getElementById('modal');
    const modalLoading = document.getElementById('modal-loading');
    const modalContent = document.getElementById('modal-content-data');

    modal.style.display = 'block';
    modalLoading.style.display = 'block';
    modalContent.style.display = 'none';

    document.getElementById('modal-title').textContent = `AI Аналитика для ${name} (${symbol})`;

    fetch('/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `name=${encodeURIComponent(name)}&symbol=${encodeURIComponent(symbol)}`
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(err => {
                    console.error('Ошибка на сервере:', err);
                    throw new Error(`Ошибка сервера: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                alert(`Ошибка: ${data.error}`);
                modal.style.display = 'none';
            } else {
                modalLoading.style.display = 'none';
                modalContent.style.display = 'block';
                modalContent.innerHTML = formatAnalyticsContent(data.content); // Используем форматирование
            }
        })
        .catch(error => {
            console.error('Ошибка fetch:', error);
            alert(`Произошла ошибка: ${error.message}`);
            modal.style.display = 'none';
        });
}


// Function to close the modal
function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Function to sort table columns
function sortTable(columnIndex, type) {
    const table = document.getElementById('cryptoTable');
    const rows = Array.from(table.rows).slice(1);
    const direction = table.dataset.sortDirection === 'asc' ? 'desc' : 'asc';

    rows.sort((a, b) => {
        let x = a.cells[columnIndex].textContent.trim();
        let y = b.cells[columnIndex].textContent.trim();

        if (type === 'number') {
            x = parseFloat(x) || -Infinity;
            y = parseFloat(y) || -Infinity;
        } else if (type === 'percent') {
            x = parseFloat(x.replace('%', '')) || -Infinity;
            y = parseFloat(y.replace('%', '')) || -Infinity;
        } else {
            x = x.toLowerCase();
            y = y.toLowerCase();
        }

        return direction === 'asc' ? (x > y ? 1 : -1) : (x < y ? 1 : -1);
    });

    rows.forEach(row => table.tBodies[0].appendChild(row));
    table.dataset.sortDirection = direction;
}

// main.js

function toggleFavorite(coinId, currentVal) {
    // Определяем новое значение (true -> false, false -> true)
    const newVal = !currentVal;

    // Делаем запрос к Flask-приложению
    fetch('/toggle_favourite', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            id: coinId,
            isFavourites: newVal
        })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Ошибка сервера: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                alert(`Ошибка: ${data.error}`);
                return;
            }

            // Если успех, меняем текст кнопки
            const button = document.getElementById(`favorite-button-${coinId}`);
            if (newVal) {
                button.textContent = 'Удалить';
            } else {
                button.textContent = 'Добавить';
            }

            // Также нужно обновить сам onclick, чтобы при следующем нажатии правильно передавалось новое текущее значение
            button.setAttribute('onclick', `toggleFavorite('${coinId}', ${newVal})`);
        })
        .catch(error => {
            console.error('Ошибка при toggleFavorite:', error);
            alert(`Произошла ошибка: ${error.message}`);
        });
}

// Event listeners for modal buttons and sorting
window.onload = function () {
    document.getElementById('close-modal').addEventListener('click', closeModal);
    // Обработчики для модального окна фильтров
    document.getElementById('open-filters-btn').addEventListener('click', openFiltersModal);
    document.getElementById('close-filters-btn').addEventListener('click', closeFiltersModal);
    document.getElementById('save-filters-btn').addEventListener('click', saveFilters);

    document.querySelectorAll('#cryptoTable th[data-type]').forEach((header, index) => {
        header.addEventListener('click', () => {
            const type = header.getAttribute('data-type');
            sortTable(index, type);
        });
    });
};
