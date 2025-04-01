/**
 * add-tokens.js - JavaScript для добавления токенов в избранное
 */

// Глобальное хранилище для выбранных токенов
let selectedTokens = [];

// Открыть модальное окно добавления токенов
function openAddTokensModal() {
    document.getElementById('addTokensModal').style.display = 'block';
    document.getElementById('tokenSearchInput').focus();

    // Сбросить список выбранных токенов
    selectedTokens = [];
    renderSelectedTokens();

    // Скрыть результаты поиска
    document.getElementById('tokenSearchResults').classList.remove('show');
}

// Закрыть модальное окно добавления токенов
function closeAddTokensModal() {
    document.getElementById('addTokensModal').style.display = 'none';
    document.getElementById('tokenSearchInput').value = '';
}

// Поиск токенов
function searchTokens() {
    const searchInput = document.getElementById('tokenSearchInput');
    const searchTerm = searchInput.value.trim();

    // Если поисковый запрос слишком короткий, скрываем результаты
    if (searchTerm.length < 2) {
        document.getElementById('tokenSearchResults').classList.remove('show');
        return;
    }

    // Показываем индикатор загрузки
    showSpinner();

    // Выполняем запрос к API
    fetch(`/get_all_tokens?search=${encodeURIComponent(searchTerm)}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Ошибка поиска токенов');
                });
            }
            return response.json();
        })
        .then(data => {
            hideSpinner();
            // Отображаем результаты
            renderSearchResults(data.tokens);
        })
        .catch(error => {
            hideSpinner();
            console.error('Ошибка при поиске токенов:', error);
            showNotification(error.message, 'error');
        });
}

// Отображение результатов поиска
function renderSearchResults(tokens) {
    const resultsContainer = document.getElementById('tokenSearchResults');
    resultsContainer.innerHTML = '';

    if (tokens.length === 0) {
        resultsContainer.innerHTML = '<div class="empty-list-message">Ничего не найдено</div>';
        resultsContainer.classList.add('show');
        return;
    }

    tokens.forEach(token => {
        // Проверяем, не добавлен ли уже токен
        const isAlreadySelected = selectedTokens.some(selectedToken => selectedToken.id === token.id);

        const item = document.createElement('div');
        item.className = 'token-search-item';

        const nameElement = document.createElement('span');
        nameElement.className = 'token-search-item-name';
        nameElement.textContent = token.name;

        const symbolElement = document.createElement('span');
        symbolElement.className = 'token-search-item-symbol';
        symbolElement.textContent = token.symbol.toUpperCase();

        const addButton = document.createElement('button');
        addButton.className = 'token-search-item-add';
        addButton.textContent = 'Добавить';
        addButton.disabled = isAlreadySelected;

        if (isAlreadySelected) {
            addButton.textContent = 'Добавлен';
            addButton.style.backgroundColor = '#cccccc';
        }

        addButton.addEventListener('click', function() {
            addTokenToSelection(token);
        });

        item.appendChild(nameElement);
        item.appendChild(symbolElement);
        item.appendChild(addButton);

        resultsContainer.appendChild(item);
    });

    resultsContainer.classList.add('show');
}

// Добавление токена в выбранные
function addTokenToSelection(token) {
    // Проверяем, не добавлен ли уже токен
    const isAlreadySelected = selectedTokens.some(selectedToken => selectedToken.id === token.id);

    if (isAlreadySelected) {
        showNotification('Этот токен уже добавлен в список', 'warning');
        return;
    }

    // Добавляем токен в список выбранных
    selectedTokens.push(token);

    // Обновляем отображение выбранных токенов
    renderSelectedTokens();

    // Обновляем интерфейс: скрываем результаты поиска и очищаем поле ввода
    document.getElementById('tokenSearchResults').classList.remove('show');
    document.getElementById('tokenSearchInput').value = '';

    showNotification(`Токен ${token.name} (${token.symbol}) добавлен в список`);
}

// Отображение выбранных токенов
function renderSelectedTokens() {
    const tableBody = document.getElementById('selectedTokensBody');
    const emptyMessage = document.getElementById('noSelectedTokensMessage');
    const addButton = document.getElementById('addToFavouritesBtn');

    tableBody.innerHTML = '';

    if (selectedTokens.length === 0) {
        emptyMessage.style.display = 'block';
        addButton.disabled = true;
        return;
    }

    emptyMessage.style.display = 'none';
    addButton.disabled = false;

    selectedTokens.forEach((token, index) => {
        const row = document.createElement('tr');

        // Имя и символ
        const nameCell = document.createElement('td');
        nameCell.textContent = `${token.name} (${token.symbol})`;

        // Ранг
        const rankCell = document.createElement('td');
        rankCell.textContent = token.cmc_rank || 'N/A';

        // Цена
        const priceCell = document.createElement('td');
        priceCell.textContent = token.price_usd ? `$${parseFloat(token.price_usd).toFixed(4)}` : 'N/A';

        // Объем
        const volumeCell = document.createElement('td');
        if (token.volume_24h) {
            const volumeMln = (token.volume_24h / 1000000).toFixed(2);
            volumeCell.textContent = `$${volumeMln}M`;
        } else {
            volumeCell.textContent = 'N/A';
        }

        // Кнопка удаления
        const actionCell = document.createElement('td');
        const removeButton = document.createElement('button');
        removeButton.className = 'remove-token-btn';
        removeButton.textContent = '-';
        removeButton.title = 'Удалить из списка';
        removeButton.addEventListener('click', function() {
            removeTokenFromSelection(index);
        });
        actionCell.appendChild(removeButton);

        // Добавляем ячейки в строку
        row.appendChild(nameCell);
        row.appendChild(rankCell);
        row.appendChild(priceCell);
        row.appendChild(volumeCell);
        row.appendChild(actionCell);

        // Добавляем строку в таблицу
        tableBody.appendChild(row);
    });
}

// Удаление токена из выбранных
function removeTokenFromSelection(index) {
    const token = selectedTokens[index];
    selectedTokens.splice(index, 1);
    renderSelectedTokens();
    showNotification(`Токен ${token.name} удален из списка`);
}

// Добавление выбранных токенов в избранное
function addTokensToFavourites() {
    if (selectedTokens.length === 0) {
        showNotification('Нет выбранных токенов для добавления', 'warning');
        return;
    }

    // Собираем ID выбранных токенов
    const tokenIds = selectedTokens.map(token => token.id);

    // Показываем индикатор загрузки
    showSpinner();

    // Отправляем запрос на добавление в избранное
    fetch('/add_to_favourites', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            token_ids: tokenIds
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка добавления в избранное');
            });
        }
        return response.json();
    })
    .then(data => {
        hideSpinner();
        if (data.success) {
            showNotification(data.message);
            closeAddTokensModal();
            // Перезагружаем страницу, чтобы отобразить новые избранные токены
            location.reload();
        } else {
            showNotification('Не удалось добавить токены в избранное', 'error');
        }
    })
    .catch(error => {
        hideSpinner();
        console.error('Ошибка при добавлении в избранное:', error);
        showNotification(error.message, 'error');
    });
}

// Функция для отображения спиннера загрузки
function showSpinner() {
    document.getElementById('spinnerOverlay').style.display = 'block';
}

// Функция для скрытия спиннера загрузки
function hideSpinner() {
    document.getElementById('spinnerOverlay').style.display = 'none';
}

// Функция для отображения уведомления
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = 'notification';

    if (type === 'error') {
        notification.classList.add('error');
    } else if (type === 'warning') {
        notification.classList.add('warning');
    }

    notification.classList.add('show');

    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Добавляем обработчик для закрытия модального окна по нажатию ESC
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAddTokensModal();
        }
    });

    // Добавляем обработчик для закрытия модального окна по клику вне его
    const modal = document.getElementById('addTokensModal');
    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeAddTokensModal();
            }
        });
    }

    // Добавляем обработчик для поиска при вводе текста
    const searchInput = document.getElementById('tokenSearchInput');
    if (searchInput) {
        let debounceTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(searchTokens, 300); // Задержка поиска для предотвращения слишком частых запросов
        });
    }
});