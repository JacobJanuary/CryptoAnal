// Настраиваем сопоставление категорий и цветов
const categoryColors = {
    "Фонды": { code: 1, color: "#F0FFF0" },
    "Мемы": { code: 2, color: "#FFF0F5" },
    "Маск": { code: 3, color: "#FFFACD" },
    "Ai": { code: 4, color: "#E6E6FA" },
    "Infrastructure": { code: 5, color: "#F0FFFF" },
    "dePin": { code: 6, color: "#F5F5DC" },
    "GameFi": { code: 7, color: "#FAF0E6" },
    "RWA": { code: 8, color: "#FFE4E1" },
    "Other trended": { range: [9, 18], color: "#F8F8FF" }
};

// Функция для раскраски строк по категории
function colorByCategory(btnLabel) {
    const table = document.getElementById('cryptoTable');
    const rows = table.tBodies[0].rows;

    // Сбрасываем предыдущие стили
    for (let row of rows) {
        row.style.backgroundColor = "";
    }

    console.log("colorByCategory вызывается для кнопки:", btnLabel);

    for (let row of rows) {
        const coinId = row.getAttribute('data-coin-id');
        const aboutStr = row.getAttribute("data-coin-about");
        const aboutValue = parseInt(aboutStr);
        console.log(`Строка coin_id=${coinId}, about_what=${aboutStr}`);
        if (isNaN(aboutValue)) {
            console.log(`Невозможно распарсить about_what для coin_id=${coinId}`);
            continue;
        }

        let applyColor = null;
        // Получаем конфигурацию для данной кнопки
        const config = categoryColors[btnLabel];
        if (!config) {
            console.log(`Нет конфигурации для категории: ${btnLabel}`);
        } else {
            if (config.code !== undefined) {
                if (aboutValue === config.code) {
                    applyColor = config.color;
                }
            } else if (config.range) {
                if (aboutValue >= config.range[0] && aboutValue <= config.range[1]) {
                    applyColor = config.color;
                }
            }
        }

        if (applyColor) {
            console.log(`Применяю цвет ${applyColor} для coin_id ${coinId}`);
            row.style.backgroundColor = applyColor;
        } else {
            console.log(`Для coin_id ${coinId} категория about_what=${aboutValue} не соответствует ${btnLabel}`);
        }
    }
}

// Функция для настройки кнопок категорий
function setupCategoryButtons() {
    const buttons = [
        { id: "btn-all-trended", label: "Все трендовые" },
        { id: "btn-fonds", label: "Фонды" },
        { id: "btn-memes", label: "Мемы" },
        { id: "btn-musk", label: "Маск" },
        { id: "btn-ai", label: "Ai" },
        { id: "btn-infra", label: "Infrastructure" },
        { id: "btn-depin", label: "dePin" },
        { id: "btn-gamefi", label: "GameFi" },
        { id: "btn-rwa", label: "RWA" },
        { id: "btn-other", label: "Other trended" }
    ];
    buttons.forEach(item => {
        const btn = document.getElementById(item.id);
        if (btn) {
            btn.addEventListener('click', () => {
                console.log(`Нажата кнопка ${item.label}`);
                // Если нажата кнопка "Все трендовые", вызываем colorTrendCoins()
                if (item.label === "Все трендовые") {
                    colorTrendCoins();
                } else {
                    colorByCategory(item.label);
                }
            });
        }
    });
}


// Функция для получения списка coin_id из таблицы
function getTableCoinIds() {
    const table = document.getElementById('cryptoTable');
    const rows = table.tBodies[0].rows;
    const coinIds = [];
    for (let row of rows) {
        const coinId = row.getAttribute('data-coin-id');
        if (coinId) {
            coinIds.push(coinId);
        }
    }
    return coinIds;
}

// Функция для раскраски трендовых монет отправляя список coin_id на сервер
function colorTrendCoins() {
    const coinIds = getTableCoinIds();
    console.log("Отправляем следующие coin_id для тренда:", coinIds);
    fetch('/trend_coins', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ coin_ids: coinIds })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            alert("Ошибка: " + data.error);
            return;
        }
        const trends = data.trends; // Ожидаем массив объектов с { coin_id, about_what }
        console.log("Получены тренды:", trends);

        // Проходим по строкам таблицы и раскрашиваем
        const table = document.getElementById('cryptoTable');
        const rows = table.tBodies[0].rows;
        for (let row of rows) {
            const coinId = row.getAttribute('data-coin-id');
            // Найти объект тренда для этого coinId
            const trendObj = trends.find(obj => obj.coin_id === coinId);
            if (trendObj) {
                let applyColor = null;
                const aboutValue = trendObj.about_what;
                // Для кнопки "Все трендовые" применим цвет исходя из о том, какая категория является приоритетной
                // Здесь перебираем всё сопоставление
                for (const key in categoryColors) {
                    const config = categoryColors[key];
                    if (config.code && aboutValue === config.code) {
                        applyColor = config.color;
                        break;
                    } else if (config.range) {
                        if (aboutValue >= config.range[0] && aboutValue <= config.range[1]) {
                            applyColor = config.color;
                            break;
                        }
                    }
                }
                if (applyColor) {
                    row.style.backgroundColor = applyColor;
                }
            }
        }
    })
    .catch(error => {
        console.error("Ошибка при получении трендовых монет:", error);
        alert("Ошибка при получении трендовых монет: " + error.message);
    });
}

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

    // Если атрибуты не установлены, устанавливаем начальные значения.
    if (!table.dataset.sortDirection) {
        table.dataset.sortDirection = 'asc';
    }
    if (!table.dataset.sortColumn) {
        table.dataset.sortColumn = '-1';
    }

    let currentColumn = table.dataset.sortColumn;
    let currentDirection = table.dataset.sortDirection;

    if (currentColumn === columnIndex.toString()) {
        // Если сортировка по тому же столбцу, переключаем направление.
        currentDirection = (currentDirection === 'asc' ? 'desc' : 'asc');
    } else {
        // Если другой столбец, устанавливаем направление по возрастанию.
        currentDirection = 'asc';
    }

    // Сортируем строки
    rows.sort((a, b) => {
        let x = a.cells[columnIndex].textContent.trim();
        let y = b.cells[columnIndex].textContent.trim();

        // Приведение к нужному типу
        if (type === 'number') {
            x = parseFloat(x.replace(/[^0-9.-]/g, '')) || 0;
            y = parseFloat(y.replace(/[^0-9.-]/g, '')) || 0;
        } else if (type === 'percent') {
            x = parseFloat(x.replace('%', '')) || 0;
            y = parseFloat(y.replace('%', '')) || 0;
        } else {
            x = x.toLowerCase();
            y = y.toLowerCase();
        }

        if (x === y) return 0;
        return (currentDirection === 'asc' ? (x > y ? 1 : -1) : (x < y ? 1 : -1));
    });

    // Перестраиваем таблицу
    tbody.innerHTML = "";
    rows.forEach(row => tbody.appendChild(row));

    // Сохраняем новое направление и индекс столбца
    table.dataset.sortDirection = currentDirection;
    table.dataset.sortColumn = columnIndex.toString();

    console.log("Direction: " + table.dataset.sortDirection + ", Column: " + table.dataset.sortColumn);
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
    // Обработка кнопок категорий
    setupCategoryButtons();
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