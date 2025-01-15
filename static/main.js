// Функция установки cookie (на случай, если потребуется fallback, можно оставить)
function setCookie(name, value, days) {
    const expires = days ? "; expires=" + new Date(Date.now() + days*864e5).toUTCString() : "";
    document.cookie = name + "=" + encodeURIComponent(value) + expires + "; path=/";
}

// Функция получения cookie по имени (если потребуется)
function getCookie(name) {
    return document.cookie.split('; ').reduce((r, v) => {
        const parts = v.split('=');
        return parts[0] === name ? decodeURIComponent(parts[1]) : r;
    }, '');
}

// Функция для открытия модального окна фильтров
function openFiltersModal() {
    const modal = document.getElementById('filter-modal');
    modal.style.display = 'block';
    // Загрузить значения из cookies (если применимо) или можно сделать AJAX-запрос к серверу для получения сохранённых настроек
    // Для примера будем использовать значения по умолчанию, если cookies не заданы:
    document.getElementById("vol-min").value = getCookie("volMin") || "10000";
    document.getElementById("growth6h").value = getCookie("growth6h") || "100";
    document.getElementById("growth1h").value = getCookie("growth1h") || "100";
    document.getElementById("price-change-max").value = getCookie("priceChangeMax") || "10";
    document.getElementById("price-change-min").value = getCookie("priceChangeMin") || "0";
    document.getElementById("market-cap-rank").value = getCookie("marketCapRank") || "";
}

// Функция для закрытия модального окна фильтров
function closeFiltersModal() {
    document.getElementById('filter-modal').style.display = 'none';
}

// Функция для сохранения настроек фильтров на сервере
function saveFilters() {
    // Читаем значения из полей формы
    const volMin = document.getElementById("vol-min").value;
    const growth6h = document.getElementById("growth6h").value;
    const growth1h = document.getElementById("growth1h").value;
    const priceChangeMax = document.getElementById("price-change-max").value;
    const priceChangeMin = document.getElementById("price-change-min").value;
    const marketCapRank = document.getElementById("market-cap-rank").value;

    // Формируем объект с настройками
    const filters = {
        volMin: volMin,
        growth6h: growth6h,
        growth1h: growth1h,
        priceChangeMax: priceChangeMax,
        priceChangeMin: priceChangeMin,
        marketCapRank: marketCapRank
    };

    // Отправляем AJAX-запрос на сервер для сохранения настроек
    fetch('/save_filters', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(filters)
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
        } else {
            alert("Настройки фильтров сохранены");
            // Сохраняем настройки в cookies для локального хранения (опционально)
            setCookie("volMin", volMin, 30);
            setCookie("growth6h", growth6h, 30);
            setCookie("growth1h", growth1h, 30);
            setCookie("priceChangeMax", priceChangeMax, 30);
            setCookie("priceChangeMin", priceChangeMin, 30);
            setCookie("marketCapRank", marketCapRank, 30);
            // Обновляем данные (например, перезагружаем страницу)
            location.reload();
        }
    })
    .catch(error => {
        console.error('Ошибка при сохранении фильтров:', error);
        alert(`Ошибка при сохранении настроек: ${error.message}`);
    });

    closeFiltersModal();
}

// Функция закрытия модального окна для AI аналитики
function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Функция для форматирования аналитического текста
function formatAnalyticsContent(content) {
    if (!content) return '';

    return content
        .replace(/###\s*(.*?)\n/g, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
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
            modalContent.innerHTML = formatAnalyticsContent(data.content);
        }
    })
    .catch(error => {
        console.error('Ошибка fetch:', error);
        alert(`Произошла ошибка: ${error.message}`);
        modal.style.display = 'none';
    });
}

function sortTable(columnIndex, type) {
    const table = document.getElementById('cryptoTable');
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.rows);

    // Получаем текущее направление сортировки из атрибута заголовка
    const header = table.querySelectorAll('th')[columnIndex];
    let currentDirection = header.getAttribute('data-direction') || 'asc';
    const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';

    // Устанавливаем атрибут data-direction на заголовке
    header.setAttribute('data-direction', newDirection);

    // Сортируем строки
    rows.sort((a, b) => {
        let x = a.cells[columnIndex].textContent.trim();
        let y = b.cells[columnIndex].textContent.trim();

        // Приведение типов
        if (type === 'number' || type === 'percent') {
            x = parseFloat(x.replace(/[^0-9.-]/g, '')) || 0;
            y = parseFloat(y.replace(/[^0-9.-]/g, '')) || 0;
        } else {
            x = x.toLowerCase();
            y = y.toLowerCase();
        }

        // Сравнение
        return newDirection === 'asc' ? (x > y ? 1 : -1) : (x < y ? 1 : -1);
    });

    // Перестраиваем таблицу
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// Функция для переключения избранного
function toggleFavorite(coinId, currentVal) {
    const newVal = !currentVal;
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
        const button = document.getElementById(`favorite-button-${coinId}`);
        if (newVal) {
            button.textContent = 'Удалить';
        } else {
            button.textContent = 'Добавить';
        }
        button.setAttribute('onclick', `toggleFavorite('${coinId}', ${newVal})`);
    })
    .catch(error => {
        console.error('Ошибка при toggleFavorite:', error);
        alert(`Произошла ошибка: ${error.message}`);
    });
}

window.onload = function() {
    console.log("main.js загружен");
    // Обработчик для закрытия модального окна AI аналитики
    document.getElementById('close-modal').addEventListener('click', closeModal);
    // Обработчики для модального окна фильтров
    document.getElementById('open-filters-btn').addEventListener('click', openFiltersModal);
    document.getElementById('close-filters-btn').addEventListener('click', closeFiltersModal);
    document.getElementById('save-filters-btn').addEventListener('click', saveFilters);

    // Обработчик клика по заголовкам таблицы
    document.querySelectorAll('#cryptoTable th[data-type]').forEach((header, index) => {
        header.addEventListener('click', () => {
            const type = header.getAttribute('data-type');
            sortTable(index, type);
        });
    });
};