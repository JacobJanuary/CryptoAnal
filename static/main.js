// main.js
// Отображение модального окна с фильтрами
function openFiltersModal() {
    const modal = document.getElementById('filter-modal');
    modal.style.display = 'block';
}

// Закрытие модального окна с фильтрами
function closeFiltersModal() {
    const modal = document.getElementById('filter-modal');
    modal.style.display = 'none';
}

// Функция сохранения фильтров и обновления таблицы
function saveFilters() {
    // Чтение значений из полей
    const volMin = document.getElementById('vol-min').value;
    const growth6h = document.getElementById('growth6h').value;
    const growth1h = document.getElementById('growth1h').value;
    const priceChangeMax = document.getElementById('price-change-max').value;
    const priceChangeMin = document.getElementById('price-change-min').value;
    const marketCapRank = document.getElementById('market-cap-rank').value;

    // Сохраняем параметры в localStorage (можно хранить как JSON-строку)
    const filters = {
        volMin: volMin || null,
        growth6h: growth6h || null,
        growth1h: growth1h || null,
        priceChangeMax: priceChangeMax || null,
        priceChangeMin: priceChangeMin || null,
        marketCapRank: marketCapRank || null
    };
    localStorage.setItem('cryptoFilters', JSON.stringify(filters));

    // Закрываем окно фильтров
    closeFiltersModal();

    // Вызываем функцию обновления таблицы с новыми фильтрами
    refreshCryptoData();
}

// Функция обновления данных таблицы по фильтрам (пример запроса через AJAX)
function refreshCryptoData() {
    // Считываем сохраненные фильтры
    const filters = JSON.parse(localStorage.getItem('cryptoFilters')) || {};

    // Формируем параметры запроса (передаем их на сервер, если сервер принимает динамические фильтры)
    // Пример для POST запроса:
    fetch('/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(filters)
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
        // Предполагается, что сервер возвращает отфильтрованные данные
        // Обновляем таблицу. Здесь можно перезагрузить страницу или обновить DOM
        location.reload();
    })
    .catch(error => {
        console.error('Ошибка при обновлении данных:', error);
        alert(`Произошла ошибка: ${error.message}`);
    });
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
window.onload = function() {
    document.getElementById('close-modal').addEventListener('click', closeModal);

    document.querySelectorAll('#cryptoTable th[data-type]').forEach((header, index) => {
        header.addEventListener('click', () => {
            const type = header.getAttribute('data-type');
            sortTable(index, type);
        });
    });
};
