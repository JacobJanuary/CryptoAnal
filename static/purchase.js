/**
 * purchase.js - JavaScript для функциональности покупки криптовалют
 */

// Глобальные переменные для хранения данных
let selectedCoins = [];
let portfolios = [];

// Функция для обновления кнопок покупки
function togglePurchaseButton(button) {
    const parentCell = button.closest('.purchase-buttons');
    const coinId = parentCell.getAttribute('data-coin-id');
    const amount = button.getAttribute('data-amount');

    // Проверяем, активна ли кнопка
    const isActive = button.classList.contains('active');

    // Сначала деактивируем все кнопки для данной монеты
    const allButtons = parentCell.querySelectorAll('.purchase-button');
    allButtons.forEach(btn => {
        btn.classList.remove('active');
    });

    // Если кнопка не была активна, активируем её
    if (!isActive) {
        button.classList.add('active');
    }

    // Обновляем состояние кнопки оформления покупки
    updatePurchaseButtonVisibility();
}

// Функция для обновления видимости кнопки оформления покупки
function updatePurchaseButtonVisibility() {
    const purchaseButton = document.getElementById('complete-purchase-btn');
    const activeButtons = document.querySelectorAll('.purchase-button.active');

    if (activeButtons.length > 0) {
        purchaseButton.style.display = 'block';
    } else {
        purchaseButton.style.display = 'none';
    }
}

// Функция для сбора данных о выбранных монетах
function collectSelectedCoins() {
    selectedCoins = [];
    const activeButtons = document.querySelectorAll('.purchase-button.active');

    activeButtons.forEach(button => {
        const cell = button.closest('.purchase-buttons');
        const coinId = cell.getAttribute('data-coin-id');
        const dollarAmount = parseInt(button.getAttribute('data-amount')); // Сумма в долларах
        const row = button.closest('tr');
        const coinNameCell = row.cells[0];
        const priceCell = row.cells[10]; // Индекс ячейки с ценой

        const fullNameText = coinNameCell.textContent.trim();
        const matches = fullNameText.match(/(.*) \((.*)\)/);

        let coinName = fullNameText;
        let coinSymbol = '';

        if (matches && matches.length >= 3) {
            coinName = matches[1].trim();
            coinSymbol = matches[2].trim();
        }

        // Извлекаем цену из ячейки, убирая знак $
        let priceText = priceCell.textContent.trim();
        priceText = priceText.replace('$', '');
        const price = parseFloat(priceText);

        // Рассчитываем количество монет, которое можно купить на указанную сумму
        const coinQuantity = price > 0 ? dollarAmount / price : 0;

        selectedCoins.push({
            id: coinId,
            name: coinName,
            symbol: coinSymbol,
            dollarAmount: dollarAmount, // Сумма в долларах
            price: price,
            quantity: coinQuantity // Количество монет
        });
    });

    return selectedCoins;
}

// Функция для обновления цен через API CoinMarketCap
function updateCryptoPrices() {
    showSpinner();

    fetch('/update_prices', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка обновления цен');
            });
        }
        return response.json();
    })
    .then(data => {
        hideSpinner();
        if (data.success) {
            showNotification(`Цены успешно обновлены для ${data.updated_coins} монет`);
            openPurchaseModal();
        } else {
            showNotification('Не удалось обновить цены', 'error');
        }
    })
    .catch(error => {
        hideSpinner();
        console.error('Ошибка при обновлении цен:', error);
        showNotification(error.message, 'error');
    });
}

// Функция для открытия модального окна покупки
function openPurchaseModal() {
    // Загружаем данные о портфелях
    loadPortfolios();

    // Заполняем таблицу выбранных монет
    populatePurchaseTable();

    // Отображаем модальное окно
    document.getElementById('purchaseModal').style.display = 'block';
}

// Функция для закрытия модального окна покупки
function closePurchaseModal() {
    document.getElementById('purchaseModal').style.display = 'none';
}

// Функция для загрузки списка инвестиционных портфелей
function loadPortfolios() {
    showSpinner();

    fetch('/get_portfolios')
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка загрузки портфелей');
            });
        }
        return response.json();
    })
    .then(data => {
        hideSpinner();
        portfolios = data.portfolios;
        renderPortfolioOptions();
    })
    .catch(error => {
        hideSpinner();
        console.error('Ошибка при загрузке портфелей:', error);
        showNotification(error.message, 'error');
    });
}

// Функция для отображения списка портфелей
function renderPortfolioOptions() {
    const container = document.getElementById('portfolioOptions');
    container.innerHTML = '';

    if (portfolios.length === 0) {
        container.innerHTML = '<p>Нет доступных портфелей. Создайте новый.</p>';
        return;
    }

    portfolios.forEach((portfolio, index) => {
        const radioId = `portfolio_${portfolio.id}`;

        const radioInput = document.createElement('input');
        radioInput.type = 'radio';
        radioInput.name = 'portfolio';
        radioInput.id = radioId;
        radioInput.className = 'portfolio-radio';
        radioInput.value = portfolio.id;

        // Выбираем Основной портфель по умолчанию или первый в списке
        if (portfolio.name === 'Основной' || index === 0) {
            radioInput.checked = true;
        }

        const label = document.createElement('label');
        label.htmlFor = radioId;
        label.className = 'portfolio-label';
        label.textContent = portfolio.name;

        container.appendChild(radioInput);
        container.appendChild(label);
    });
}

// Функция для отображения формы добавления портфеля
function showAddPortfolioForm() {
    document.getElementById('addPortfolioForm').style.display = 'block';
}

// Функция для скрытия формы добавления портфеля
function hideAddPortfolioForm() {
    document.getElementById('addPortfolioForm').style.display = 'none';
    document.getElementById('portfolioName').value = '';
    document.getElementById('portfolioDescription').value = '';
}

// Функция для добавления нового портфеля
function addNewPortfolio() {
    const name = document.getElementById('portfolioName').value.trim();
    const description = document.getElementById('portfolioDescription').value.trim();

    if (!name) {
        showNotification('Необходимо указать название портфеля', 'warning');
        return;
    }

    showSpinner();

    fetch('/add_portfolio', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            name: name,
            description: description
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка добавления портфеля');
            });
        }
        return response.json();
    })
    .then(data => {
        hideSpinner();
        if (data.success) {
            showNotification(`Портфель "${data.name}" успешно добавлен`);
            hideAddPortfolioForm();
            loadPortfolios(); // Перезагружаем список портфелей
        } else {
            showNotification('Не удалось добавить портфель', 'error');
        }
    })
    .catch(error => {
        hideSpinner();
        console.error('Ошибка при добавлении портфеля:', error);
        showNotification(error.message, 'error');
    });
}

// Функция для заполнения таблицы выбранными монетами
function populatePurchaseTable() {
    const coins = collectSelectedCoins();
    const tableBody = document.getElementById('purchaseTableBody');
    tableBody.innerHTML = '';

    if (coins.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 5;
        cell.textContent = 'Не выбрано ни одной монеты';
        cell.style.textAlign = 'center';
        row.appendChild(cell);
        tableBody.appendChild(row);
        updateTotalAmount();
        return;
    }

    coins.forEach((coin, index) => {
        const row = document.createElement('tr');
        row.setAttribute('data-coin-id', coin.id);

        // Ячейка с названием монеты
        const nameCell = document.createElement('td');
        nameCell.textContent = `${coin.name} (${coin.symbol})`;

        // Ячейка с количеством - используем рассчитанное количество монет
        const quantityCell = document.createElement('td');
        const quantityInput = document.createElement('input');
        quantityInput.type = 'number';
        quantityInput.min = '0.00000001';
        quantityInput.step = '0.00000001';
        quantityInput.value = coin.quantity.toFixed(8); // Важно: используем рассчитанное количество, не сумму
        quantityInput.className = 'quantity-input';
        quantityInput.addEventListener('input', recalculateAmountOnChange);
        quantityCell.appendChild(quantityInput);

        // Ячейка с ценой
        const priceCell = document.createElement('td');
        const priceInput = document.createElement('input');
        priceInput.type = 'number';
        priceInput.min = '0.00000001';
        priceInput.step = '0.00000001';
        priceInput.value = coin.price;
        priceInput.className = 'price-input';
        priceInput.addEventListener('input', recalculateAmountOnChange);
        priceCell.appendChild(priceInput);

        // Ячейка с датой/временем
        const dateCell = document.createElement('td');
        const dateInput = document.createElement('input');
        dateInput.type = 'datetime-local';
        dateInput.value = getCurrentDateTimeForInput();
        dateInput.className = 'date-input';
        dateCell.appendChild(dateInput);

        // Ячейка с суммой (изначально сумма в долларах из кнопки)
        const amountCell = document.createElement('td');
        amountCell.className = 'row-amount';
        amountCell.textContent = `$${coin.dollarAmount.toFixed(2)}`;

        // Добавляем ячейки в строку
        row.appendChild(nameCell);
        row.appendChild(quantityCell);
        row.appendChild(priceCell);
        row.appendChild(dateCell);
        row.appendChild(amountCell);

        // Добавляем строку в таблицу
        tableBody.appendChild(row);
    });

    // Обновляем итоговую сумму
    updateTotalAmount();
}

// Функция для пересчета суммы при изменении количества или цены
function recalculateAmountOnChange(event) {
    const input = event.target;
    const row = input.closest('tr');
    const quantityInput = row.querySelector('.quantity-input');
    const priceInput = row.querySelector('.price-input');
    const amountCell = row.querySelector('.row-amount');

    const quantity = parseFloat(quantityInput.value) || 0;
    const price = parseFloat(priceInput.value) || 0;
    const amount = quantity * price;

    amountCell.textContent = `$${amount.toFixed(2)}`;

    // Обновляем итоговую сумму после изменения
    updateTotalAmount();
}

// Функция для обновления общей суммы
function updateTotalAmount() {
    const amounts = document.querySelectorAll('.row-amount');
    let total = 0;

    amounts.forEach(cell => {
        const amountText = cell.textContent.replace('$', '');
        total += parseFloat(amountText) || 0;
    });

    document.getElementById('purchaseTotal').textContent = `Итого: $${total.toFixed(2)}`;
}

// Функция для получения текущей даты и времени в формате для input
function getCurrentDateTimeForInput() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');

    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Функция для сохранения покупок
function savePurchases() {
    // Получаем выбранный портфель
    const selectedPortfolioElement = document.querySelector('input[name="portfolio"]:checked');
    if (!selectedPortfolioElement) {
        showNotification('Выберите инвестиционный портфель', 'warning');
        return;
    }

    const portfolioId = selectedPortfolioElement.value;

    // Собираем данные из таблицы
    const rows = document.querySelectorAll('#purchaseTableBody tr[data-coin-id]');
    if (rows.length === 0) {
        showNotification('Нет монет для покупки', 'warning');
        return;
    }

    const purchases = [];

    rows.forEach(row => {
        const coinId = row.getAttribute('data-coin-id');
        const coinNameElement = row.cells[0];
        const quantityInput = row.querySelector('.quantity-input');
        const priceInput = row.querySelector('.price-input');
        const dateInput = row.querySelector('.date-input');
        const amountCell = row.querySelector('.row-amount');

        if (!quantityInput || !priceInput || !dateInput || !amountCell) {
            return;
        }

        const quantity = parseFloat(quantityInput.value);
        const price_usd = parseFloat(priceInput.value);
        const purchase_date = dateInput.value;

        // Извлекаем сумму из ячейки
        const amountText = amountCell.textContent.replace('$', '');
        const amount = parseFloat(amountText);

        if (isNaN(quantity) || quantity <= 0 || isNaN(price_usd) || price_usd <= 0 || isNaN(amount) || amount <= 0) {
            return;
        }

        const fullNameText = coinNameElement.textContent.trim();
        const matches = fullNameText.match(/(.*) \((.*)\)/);

        let coinName = fullNameText;
        let coinSymbol = '';

        if (matches && matches.length >= 3) {
            coinName = matches[1].trim();
            coinSymbol = matches[2].trim();
        }

        purchases.push({
            coin_id: coinId,
            coin_name: coinName,
            coin_symbol: coinSymbol,
            quantity: quantity,
            price_usd: price_usd,
            total_amount: amount,
            purchase_date: purchase_date
        });
    });

    if (purchases.length === 0) {
        showNotification('Нет корректных данных для сохранения', 'warning');
        return;
    }

    // Отправляем данные на сервер
    showSpinner();

    fetch('/save_purchases', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            portfolio_id: portfolioId,
            purchases: purchases
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка сохранения покупок');
            });
        }
        return response.json();
    })
    .then(data => {
        hideSpinner();
        if (data.success) {
            showNotification(data.message);
            closePurchaseModal();

            // Сбрасываем выбор монет после успешного сохранения
            resetCoinSelection();
        } else {
            showNotification('Не удалось сохранить покупки', 'error');
        }
    })
    .catch(error => {
        hideSpinner();
        console.error('Ошибка при сохранении покупок:', error);
        showNotification(error.message, 'error');
    });
}

// Функция для сброса выбора монет
function resetCoinSelection() {
    const activeButtons = document.querySelectorAll('.purchase-button.active');
    activeButtons.forEach(button => {
        button.classList.remove('active');
    });
    updatePurchaseButtonVisibility();
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

// Функция для оформления покупки (которая вызывается по нажатию на кнопку "Оформить покупку")
function completePurchase() {
    // Сбор данных о выбранных монетах
    const selectedCoins = collectSelectedCoins();

    if (selectedCoins.length === 0) {
        showNotification('Не выбрано ни одной монеты', 'warning');
        return;
    }

    // Обновляем цены и открываем модальное окно покупки
    updateCryptoPrices();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    updatePurchaseButtonVisibility();

    // Добавляем обработчик для закрытия модального окна по нажатию ESC
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closePurchaseModal();
        }
    });

    // Добавляем обработчик для закрытия модального окна по клику вне его
    const modal = document.getElementById('purchaseModal');
    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === this) {
                closePurchaseModal();
            }
        });
    }
});