// Настраиваем соответствие about_what -> цвет
const categoryColors = {
    "Фонды": {code: 1, color: "#F0FFF0"},
    "Мемы": {code: 2, color: "#FFF0F5"},
    "Маск": {code: 3, color: "#FFFACD"},
    "Ai": {code: 4, color: "#E6E6FA"},
    "Infrastructure": {code: 5, color: "#F0FFFF"},
    "dePin": {code: 6, color: "#F5F5DC"},
    "GameFi": {code: 7, color: "#FAF0E6"},
    "RWA": {code: 8, color: "#FFE4E1"},
    "USA": {code: 20, color: "#39E75F"},
    "Other trended": {range: [9, 18], color: "#F8F8FF"}
};

function hideNonTrended() {
    const table = document.getElementById('cryptoTable');
    if (!table) return;
    const rows = table.tBodies[0].rows;

    for (let row of rows) {
        const aboutVal = parseInt(row.getAttribute('data-about-min')) || 0;
        if (aboutVal === 0) {
            // Монета не в тренде — скрываем строку
            row.style.display = 'none';
        }
    }
}

function showAllCoins() {
    const table = document.getElementById('cryptoTable');
    if (!table) return;
    const rows = table.tBodies[0].rows;
    for (let row of rows) {
        row.style.display = '';
    }
}


let tooltipDiv = null;

function showCategoryTooltip(event) {
    // Получаем <tr> или <td> через event.currentTarget (зависит от того, куда именно навешиваем обработчики)
    const targetElem = event.currentTarget;
    if (!targetElem) return;

    // Считываем список категорий из data-атрибута
    const categories = targetElem.getAttribute('data-categories');
    if (!categories || categories.trim() === '') {
        return;
    }
    // Отображаем tooltip
    tooltipDiv.style.display = 'block';
    tooltipDiv.textContent = categories; // Выводим список категорий

    // Первое позиционирование (примерно рядом с курсором)
    tooltipDiv.style.left = (event.pageX + 10) + 'px';
    tooltipDiv.style.top = (event.pageY + 10) + 'px';
}

function moveCategoryTooltip(event) {
    // Двигаем tooltip вслед за курсором
    tooltipDiv.style.left = (event.pageX + 10) + 'px';
    tooltipDiv.style.top = (event.pageY + 10) + 'px';
}

function hideCategoryTooltip() {
    tooltipDiv.style.display = 'none';
}

// Функция для автоматической раскраски при загрузке
function colorTrendedOnLoad() {
    const table = document.getElementById('cryptoTable');
    if (!table) return;
    const rows = table.tBodies[0].rows;

    for (let row of rows) {
        const aboutVal = parseInt(row.getAttribute('data-about-min')) || 0;
        if (aboutVal !== 0) {
            // Ищем соответствующий цвет
            let colorToApply = null;
            for (const key in categoryColors) {
                const cfg = categoryColors[key];
                if (cfg.code && cfg.code === aboutVal) {
                    colorToApply = cfg.color;
                    break;
                } else if (cfg.range) {
                    if (aboutVal >= cfg.range[0] && aboutVal <= cfg.range[1]) {
                        colorToApply = cfg.color;
                        break;
                    }
                }
            }
            if (colorToApply) {
                row.style.backgroundColor = colorToApply;
            }
        }
    }
}

// Навешиваем обработчики на каждую строку таблицы
function setupCategoryTooltips() {
    tooltipDiv = document.getElementById('category-tooltip');
    if (!tooltipDiv) {
        console.warn("Элемент #category-tooltip не найден!");
        return;
    }
    const table = document.getElementById('cryptoTable');
    if (!table) {
        console.warn("Таблица #cryptoTable не найдена!");
        return;
    }

    const rows = table.tBodies[0].rows;
    for (let row of rows) {
        // навешиваем события на <tr>
        row.addEventListener('mouseover', showCategoryTooltip);
        row.addEventListener('mousemove', moveCategoryTooltip);
        row.addEventListener('mouseout', hideCategoryTooltip);
    }
}

// Функция установки cookie (на случай, если потребуется fallback, можно оставить)
function setCookie(name, value, days) {
    const expires = days ? "; expires=" + new Date(Date.now() + days * 864e5).toUTCString() : "";
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

function showCoinDetails(coinId) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalContent = document.getElementById('modal-content-data');
    const modalLoading = document.getElementById('modal-loading');

    modalTitle.textContent = "Загрузка...";
    modalContent.innerHTML = "";
    modalLoading.style.display = 'block';
    modalContent.style.display = 'none';
    modal.style.display = 'block';

    fetch(`/coin_details/${coinId}`)
    .then(response => {
        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        modalTitle.textContent = `${data.name} (${data.symbol})`;

        let html = "";

        // Информация по монете
        let mcMln = data.market_cap_usd ? (data.market_cap_usd / 1e6).toFixed(2) : "N/A";
        let rank = data.market_cap_rank || "N/A";
        let volMln = data.total_volume_usd ? (data.total_volume_usd / 1e6).toFixed(2) : "N/A";
        let cPrice = data.current_price_usd ? data.current_price_usd.toFixed(2) : "N/A";
        let high24 = data.high_24h_usd ? data.high_24h_usd.toFixed(2) : "N/A";
        let low24 = data.low_24h_usd ? data.low_24h_usd.toFixed(2) : "N/A";
        let athVal = data.ath_usd ? data.ath_usd.toFixed(2) : "N/A";
        let athPct = data.ath_change_percentage_usd ? data.ath_change_percentage_usd.toFixed(2) : "N/A";
        let athDate = data.ath_date_usd || "N/A";
        let atlVal = data.atl_usd ? data.atl_usd.toFixed(2) : "N/A";
        let atlPct = data.atl_change_percentage_usd ? data.atl_change_percentage_usd.toFixed(2) : "N/A";
        let atlDate = data.atl_date_usd || "N/A";
        let max2325 = data.max_price_oct23_mar25 ? data.max_price_oct23_mar25.toFixed(2) : "N/A";
        let max2325Date = data.max_date_oct23_mar25 || "N/A";
        let percMaxToCurrent = data.perc_change_max_to_current ? data.perc_change_max_to_current.toFixed(2) : "N/A";
        let min2325 = data.min_price_oct23_mar25 ? data.min_price_oct23_mar25.toFixed(2) : "N/A";
        let min2325Date = data.min_date_oct23_mar25 || "N/A";
        let percMinToCurrent = data.perc_change_min_to_current ? data.perc_change_min_to_current.toFixed(2) : "N/A";

        html += `<h3>Информация по монете</h3>`;
        html += `<p><strong>Market Cap:</strong> ${mcMln} млн. (Rank: ${rank})</p>`;
        html += `<p><strong>Volume:</strong> ${volMln} млн. | <strong>Price:</strong> $${cPrice}</p>`;
        html += `<p>24h Low: $${low24}, 24h High: $${high24}</p>`;
        html += `<p><strong>ATH:</strong> $${athVal}, ${athPct}%, ${athDate}</p>`;
        html += `<p><strong>ATL:</strong> $${atlVal}, ${atlPct}%, ${atlDate}</p>`;
        html += `<p><strong>High23-25:</strong> $${max2325} (${max2325Date}) ${percMaxToCurrent}%</p>`;
        html += `<p><strong>Low23-25:</strong> $${min2325} (${min2325Date}) ${percMinToCurrent}%</p>`;

        // Аномальные объемы
        let volumeSpikes = [];
        try {
            volumeSpikes = JSON.parse(data.volume_spikes || '[]');
        } catch (e) {
            console.error("Error parsing volume_spikes:", e);
        }
        if (volumeSpikes.length > 0) {
            html += `<h3>Аномальные объемы</h3>`;
            html += `<table style="border-collapse: collapse; width: 100%;"><tr><th style="border: 1px solid #ddd; padding: 8px;">Date</th><th style="border: 1px solid #ddd; padding: 8px;">Volume</th></tr>`;
            volumeSpikes.forEach(spike => {
                html += `<tr><td style="border: 1px solid #ddd; padding: 8px;">${spike.date}</td><td style="border: 1px solid #ddd; padding: 8px;">${spike.volume.toLocaleString()}</td></tr>`;
            });
            html += `</table>`;
        } else {
            html += `<p><strong>Аномальные объемы:</strong> Нет данных</p>`;
        }

        // Аномальная волатильность
        let buybacks = [];
        try {
            buybacks = JSON.parse(data.anomalous_buybacks || '[]');
        } catch (e) {
            console.error("Error parsing anomalous_buybacks:", e);
        }
        if (buybacks.length > 0) {
            html += `<h3>Аномальная волатильность</h3>`;
            html += `<table style="border-collapse: collapse; width: 100%;"><tr><th style="border: 1px solid #ddd; padding: 8px;">Date</th><th style="border: 1px solid #ddd; padding: 8px;">Price Change (%)</th><th style="border: 1px solid #ddd; padding: 8px;">Volume</th></tr>`;
            buybacks.forEach(bb => {
                html += `<tr><td style="border: 1px solid #ddd; padding: 8px;">${bb.date}</td><td style="border: 1px solid #ddd; padding: 8px;">${bb.price_change.toFixed(2)}</td><td style="border: 1px solid #ddd; padding: 8px;">${bb.volume.toLocaleString()}</td></tr>`;
            });
            html += `</table>`;
        } else {
            html += `<p><strong>Аномальная волатильность:</strong> Нет данных</p>`;
        }

        // AI Аналитика
        html += `<h3>AI Аналитика</h3>`;
        html += formatAnalyticsContent(data.AI_text || "Нет данных");

        // AI Фонды
        html += `<h3>AI Фонды</h3>`;
        html += formatAnalyticsContent(data.AI_invest || "Нет данных");

        modalContent.innerHTML = html;
        modalLoading.style.display = 'none';
        modalContent.style.display = 'block';
    })
    .catch(err => {
        console.error("Ошибка при загрузке деталей монеты:", err);
        alert("Ошибка: " + err.message);
        modal.style.display = 'none';
    });
}

// Модифицированная функция formatAiBlock
function formatAiBlock(title, text, lineCount) {
    if (!text) {
        return `<p><strong>${title}:</strong> N/A</p>`;
    }

    // Применяем нашу логику форматирования (например, formatAnalyticsContent)
    // к полной версии текста, чтобы поддержать **...** и ### ...
    const formattedFull = formatAnalyticsContent(text);

    // Разбиваем текст на строки (по \n)
    const lines = text.split("\n");
    if (lines.length <= lineCount) {
        // если меньше нужного количества строк, выводим всё целиком в форматированном виде
        return `
          <p><strong>${title}:</strong></p>
          <div>${formatAnalyticsContent(text)}</div>
        `;
    } else {
        // показываем только первые lineCount строк
        const firstLines = lines.slice(0, lineCount).join("\n");
        const formattedCollapsed = formatAnalyticsContent(firstLines);

        return `
          <p><strong>${title}:</strong></p>
          <div class="ai-block">
            <div class="collapsed-text">${formattedCollapsed}</div>
            <button onclick="toggleAiExpand(this)" data-full='${escapeHtml(formattedFull)}'>
              >> Развернуть
            </button>
          </div>
        `;
    }
}

// При нажатии на >> Развернуть
function toggleAiExpand(btn) {
    const full = unescapeHtml(btn.getAttribute("data-full"));
    const block = btn.closest(".ai-block");
    block.innerHTML = full;
}

// Пример экранирования HTML
function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
}
function unescapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">");
}

// main.js

// Пример функции, которая открывает модальное окно и показывает детальные данные монеты
function showCoinDetails(coinId) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalContent = document.getElementById('modal-content-data');
    const modalLoading = document.getElementById('modal-loading');

    // Очищаем / показываем модалку
    modalTitle.textContent = "Загрузка...";
    modalContent.innerHTML = "";
    modalLoading.style.display = 'block';
    modalContent.style.display = 'none';
    modal.style.display = 'block';

    // Запрашиваем данные
    fetch(`/coin_details/${coinId}`)
    .then(response => {
        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }

        // Устанавливаем заголовок модалки = "Name (Symbol)"
        modalTitle.textContent = `${data.name} (${data.symbol})`;

        // Начинаем формировать HTML
        let html = "";


        // -----------------------------
        // 2) Информация о монете
        // -----------------------------
        let mcMln = data.market_cap_usd ? (data.market_cap_usd / 1e6).toFixed(2) : "N/A";
        let rank = data.market_cap_rank || "N/A";
        let volMln = data.total_volume_usd ? (data.total_volume_usd / 1e6).toFixed(2) : "N/A";
        let cPrice = data.current_price_usd || "N/A";
        let high24 = data.high_24h_usd || "N/A";
        let low24 = data.low_24h_usd || "N/A";

        html += `<hr><h3>Информация по монете</h3>`;
        html += `<p><strong>Market Cap:</strong> ${mcMln} млн. (Rank: ${rank})</p>`;
        html += `<p><strong>Volume:</strong> ${volMln} млн. | <strong>Price:</strong> $${cPrice}</p>`;
        html += `<p>24h Low: $${low24}, 24h High: $${high24}</p>`;

        // ATH / ATL
        let athVal = data.ath_usd || "N/A";
        let athPct = data.ath_change_percentage_usd || "N/A";
        let athDate = data.ath_date_usd || "N/A";
        let atlVal = data.atl_usd || "N/A";
        let atlPct = data.atl_change_percentage_usd || "N/A";
        let atlDate = data.atl_date_usd || "N/A";
        html += `<p><strong>ATH:</strong> $${athVal}, ${athPct}%, ${athDate}</p>`;
        html += `<p><strong>ATL:</strong> $${atlVal}, ${atlPct}%, ${atlDate}</p>`;

        // High365 / Low365
        let percMaxToCurrent = data.perc_change_max_to_current ? data.perc_change_max_to_current.toFixed(2) : "N/A";
        let percMinToMax = data.perc_change_min_to_max ? data.perc_change_min_to_max.toFixed(2) : "N/A";

        html += `<p><strong>High23-25:</strong> $${max2325} (${max2325Date}) ${percMaxToCurrent}%</p>`;
        html += `<p><strong>Low23-25:</strong> $${min2325} (${min2325Date}) ${percMinToMax}%</p>`;

        // watchlist_portfolio_users
        if (data.watchlist_portfolio_users !== undefined && data.watchlist_portfolio_users !== null) {
            html += `<p><strong>Watchlist:</strong> ${data.watchlist_portfolio_users}</p>`;
        }

        // -----------------------------
        // 3) Исторические даты
        // -----------------------------
        html += `<hr><h3>Исторические даты</h3>`;
        html += generateDatePriceBlock(data);

        // -----------------------------
        // 4) AI Аналитика (полностью, с форматированием)
        // -----------------------------
        html += `<hr><h3>AI Аналитика</h3>`;
        html += formatAnalyticsContent(data.AI_text || "Нет данных");

        // -----------------------------
        // 1) AI Фонды (полностью, с форматированием)
        // -----------------------------
        html += `<h3>AI Фонды</h3>`;
        html += formatAnalyticsContent(data.AI_invest || "Нет данных");

        // Помещаем всё в окно
        modalContent.innerHTML = html;
        modalLoading.style.display = 'none';
        modalContent.style.display = 'block';
    })
    .catch(err => {
        console.error("Ошибка при загрузке деталей монеты:", err);
        alert("Ошибка: " + err.message);
        modal.style.display = 'none';
    });
}

// Пример функции форматирования AI-текста (убираем свернуть/развернуть):
function formatAnalyticsContent(content) {
    if (!content) return 'N/A';
    return content
      // Пример простой замены ### и **...** + переносы
      .replace(/###\s*(.*?)\n/g, '<h3>$1</h3>\n')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
}

// Пример функции для расчёта и генерации HTML по датам
function generateDatePriceBlock(data) {
    let html = "<hr><h4>Prices by dates:</h4>";

    // Для примера сделаем пару вычислений:
    //  - 05.08 $`05_08_2024`
    //  - Сравнение с 04.08, 06.08 ...
    // (Можно сделать более универсально, если нужно)

    // Пример чтения data["d_05_08_24"]:
    const d_04_08_24 = data.d_04_08_24 || null;
    const d_05_08_24 = data.d_05_08_24 || null;
    const d_06_08_24 = data.d_06_08_24 || null;

    // Пример вывода
    html += `<p><strong>05.08.24:</strong> $${d_05_08_24 || "N/A"}</p>`;
    if (d_05_08_24 && d_04_08_24) {
        let pct = ((d_05_08_24 - d_04_08_24) / d_04_08_24) * 100;
        html += `<p>Изменение (04.08 -> 05.08): ${pct.toFixed(2)}%</p>`;
    }
    if (d_06_08_24 && d_05_08_24) {
        let pct = ((d_06_08_24 - d_05_08_24) / d_05_08_24) * 100;
        html += `<p>Изменение (05.08 -> 06.08): ${pct.toFixed(2)}%</p>`;
    }

    // Аналогично для 02.02, 03.02, 04.02 ...
    const d_02_02_25 = data.d_02_02_25 || null;
    const d_03_02_25 = data.d_03_02_25 || null;
    const d_04_02_25 = data.d_04_02_25 || null;

    html += `<p><strong>03.02.25:</strong> $${d_03_02_25 || "N/A"}</p>`;
    if (d_03_02_25 && d_02_02_25) {
        let pct = ((d_03_02_25 - d_02_02_25) / d_02_02_25) * 100;
        html += `<p>Изменение (02.02 -> 03.02): ${pct.toFixed(2)}%</p>`;
    }
    if (d_04_02_25 && d_03_02_25) {
        let pct = ((d_04_02_25 - d_03_02_25) / d_03_02_25) * 100;
        html += `<p>Изменение (03.02 -> 04.02): ${pct.toFixed(2)}%</p>`;
    }

    // Пример для 07.12.24
    const d_07_12_24 = data.d_07_12_24 || null;
    if (d_07_12_24) {
        html += `<p><strong>07.12.24:</strong> $${d_07_12_24}</p>`;
    }

    return html;
}
function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

window.onload = function () {
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
    // Сначала раскрашиваем
    colorTrendedOnLoad();
    // Инициализируем tooltip
    setupCategoryTooltips();

    // Кнопка для скрытия не-трендовых
    const hideBtn = document.getElementById('hide-non-trended-btn');
    if (hideBtn) {
        hideBtn.addEventListener('click', hideNonTrended);
    }
};