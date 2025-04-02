/**
 * portfolio-detail.js - JavaScript для страницы детального просмотра портфеля
 */

// Глобальные переменные
let performanceChart = null;
let compositionChart = null;
let activePeriod = '7d';

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log("portfolio-detail.js загружен");

    // Убедимся, что модальное окно скрыто при загрузке
    const modal = document.getElementById('confirmModal');
    if (modal) {
        modal.style.display = 'none';
    }

    // Инициализация обработчиков событий
    initEventHandlers();

    // Загружаем и отображаем графики
    loadPortfolioPerformance(activePeriod);
    loadPortfolioComposition();
});

/**
 * Инициализация обработчиков событий на странице
 */
function initEventHandlers() {
    // Кнопка обновления цен
    const updatePricesBtn = document.getElementById('update-prices-btn');
    if (updatePricesBtn) {
        updatePricesBtn.addEventListener('click', function() {
            updatePortfolioPrices();
        });
    }

    // Настраиваем кнопки выбора периода
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // Убираем активный класс у всех кнопок
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));

            // Устанавливаем активный класс для нажатой кнопки
            this.classList.add('active');

            // Загружаем данные за выбранный период
            activePeriod = this.getAttribute('data-period');
            loadPortfolioPerformance(activePeriod);
        });
    });

    // Кнопки удаления транзакций
    document.querySelectorAll('.delete-tx-btn').forEach(btn => {
        btn.addEventListener('click', function(event) {
            // Предотвращаем стандартное поведение и всплытие события
            event.preventDefault();
            event.stopPropagation();

            const txId = this.getAttribute('data-tx-id');
            if (txId) {
                showDeleteConfirmation(txId);
            }
        });
    });

    // Настраиваем модальное окно
    setupModalDialogs();
}

/**
 * Настройка модальных диалогов
 */
function setupModalDialogs() {
    const modal = document.getElementById('confirmModal');
    const closeBtn = document.querySelector('.modal-close');
    const cancelBtn = document.getElementById('cancelBtn');

    if (!modal || !closeBtn || !cancelBtn) {
        console.error("Элементы модального окна не найдены");
        return;
    }

    // Закрытие модального окна по крестику
    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });

    // Закрытие модального окна по кнопке "Отмена"
    cancelBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });

    // Закрытие модального окна при клике вне его области
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Нажатие клавиши ESC для закрытия окна
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
        }
    });
}

/**
 * Функция для загрузки данных о динамике стоимости портфеля
 * @param {string} period - Период для отображения (7d, 30d, 90d, all)
 */
function loadPortfolioPerformance(period) {
    console.log(`Загрузка данных о динамике портфеля за период: ${period}`);
    showSpinner();

    fetch(`/api/portfolio/${PORTFOLIO_ID}/performance?period=${period}`)
        .then(response => handleResponse(response))
        .then(data => {
            hideSpinner();
            console.log("Данные о динамике портфеля:", data);

            if (!data.performance || data.performance.length === 0) {
                console.warn("API вернул пустые данные о динамике");
                const chartContainer = document.getElementById('performanceChart').parentNode;
                chartContainer.innerHTML = '<div class="empty-message">Недостаточно данных для построения графика.</div>';
                return;
            }

            renderPerformanceChart(data.performance);
        })
        .catch(error => {
            console.error("Ошибка при загрузке данных о динамике:", error);
            hideSpinner();
            showNotification("Ошибка: " + error.message, 'error');
        });
}

/**
 * Функция для отрисовки графика динамики стоимости портфеля
 * @param {Array} performanceData - Массив данных о производительности портфеля
 */
function renderPerformanceChart(performanceData) {
    const chartElement = document.getElementById('performanceChart');
    if (!chartElement) {
        console.error("Не найден элемент performanceChart");
        return;
    }

    const ctx = chartElement.getContext('2d');

    // Подготовка данных для графика
    const labels = performanceData.map(item => item.date);
    const values = performanceData.map(item => item.value);
    const investedValues = performanceData.map(item => item.invested);

    // Если уже есть график, уничтожаем его
    if (performanceChart) {
        performanceChart.destroy();
    }

    // Создаем новый график
    performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Текущая стоимость',
                    data: values,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: true
                },
                {
                    label: 'Инвестировано',
                    data: investedValues,
                    backgroundColor: 'rgba(201, 203, 207, 0.2)',
                    borderColor: 'rgba(201, 203, 207, 1)',
                    borderWidth: 1,
                    tension: 0.1,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += '$' + context.parsed.y.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: false
                    },
                    ticks: {
                        callback: function(value, index, values) {
                            const date = moment(this.getLabelForValue(value));
                            return date.format('DD.MM.YYYY');
                        }
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Стоимость ($)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toFixed(2);
                        }
                    }
                }
            }
        }
    });
}

/**
 * Функция для загрузки данных о составе портфеля
 */
function loadPortfolioComposition() {
    console.log("Загрузка состава портфеля...");
    showSpinner();

    fetch(`/api/portfolio/${PORTFOLIO_ID}/composition`)
        .then(response => {
            console.log("Получен ответ API composition:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Получены данные о составе портфеля:", data);
            hideSpinner();

            if (data.error) {
                console.error("API вернул ошибку:", data.error);
                showNotification("Ошибка загрузки данных: " + data.error, 'error');
                return;
            }

            if (!data.composition || data.composition.length === 0) {
                console.warn("API вернул пустой состав портфеля");
                const container = document.querySelector('.composition-container');
                if (container) {
                    container.innerHTML = '<div class="empty-message">В портфеле нет активов или у монет нет текущих цен.</div>';
                }
                return;
            }

            renderCompositionChart(data.composition);
        })
        .catch(error => {
            console.error("Ошибка при получении данных о составе портфеля:", error);
            hideSpinner();
            showNotification("Ошибка: " + error.message, 'error');
            const container = document.querySelector('.composition-container');
            if (container) {
                container.innerHTML = '<div class="empty-message">Не удалось загрузить данные о составе портфеля.</div>';
            }
        });
}

/**
 * Функция для отрисовки круговой диаграммы состава портфеля
 * @param {Array} compositionData - Массив данных о составе портфеля
 */
function renderCompositionChart(compositionData) {
    const compositionContainer = document.querySelector('.composition-container');

    // Проверка на наличие данных
    if (!compositionData || compositionData.length === 0) {
        console.warn("Нет данных для отображения состава портфеля");
        if (compositionContainer) {
            compositionContainer.innerHTML = '<div class="empty-message">В портфеле нет активов или не удалось загрузить данные о составе портфеля.</div>';
        }
        return;
    }

    const chartElement = document.getElementById('compositionChart');
    if (!chartElement) {
        console.error("Не найден элемент compositionChart");
        if (compositionContainer) {
            compositionContainer.innerHTML = '<div class="empty-message">Ошибка отображения графика: элемент не найден.</div>';
        }
        return;
    }

    const ctx = chartElement.getContext('2d');

    // Подготавливаем данные для круговой диаграммы
    const labels = compositionData.map(item => item.name);
    const values = compositionData.map(item => item.value);
    const backgroundColor = generateColors(compositionData.length);

    // Если уже есть диаграмма, уничтожаем её
    if (compositionChart) {
        compositionChart.destroy();
    }

    // Создаем новую диаграмму
    compositionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: backgroundColor,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const dataIndex = context.dataIndex;
                            const asset = compositionData[dataIndex];
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(2);

                            return [
                                `${asset.name} (${asset.full_name})`,
                                `$${value.toFixed(2)} (${percentage}%)`
                            ];
                        }
                    }
                }
            }
        }
    });

    // Создаем легенду вручную
    createCustomLegend(compositionData, backgroundColor);
}

/**
 * Функция для создания кастомной легенды
 * @param {Array} data - Данные для легенды
 * @param {Array} colors - Массив цветов
 */
function createCustomLegend(data, colors) {
    const legendContainer = document.getElementById('compositionLegend');
    if (!legendContainer) {
        console.error("Не найден элемент compositionLegend");
        return;
    }

    legendContainer.innerHTML = '';

    // Рассчитываем общую сумму
    const total = data.reduce((sum, item) => sum + item.value, 0);

    // Создаем элементы легенды
    data.forEach((item, index) => {
        const percentage = ((item.value / total) * 100).toFixed(2);

        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item';

        const colorBox = document.createElement('div');
        colorBox.className = 'legend-color';
        colorBox.style.backgroundColor = colors[index];

        const label = document.createElement('div');
        label.className = 'legend-label';
        label.textContent = `${item.name} - $${item.value.toFixed(2)} (${percentage}%)`;

        legendItem.appendChild(colorBox);
        legendItem.appendChild(label);
        legendContainer.appendChild(legendItem);

        // Добавляем всплывающую подсказку
        legendItem.title = item.full_name;

        // Добавляем интерактивность (выделение сектора на диаграмме)
        legendItem.addEventListener('mouseover', () => {
            highlightChartSegment(index, true);
        });

        legendItem.addEventListener('mouseout', () => {
            highlightChartSegment(index, false);
        });
    });
}

/**
 * Функция для выделения сегмента на диаграмме
 * @param {number} index - Индекс сегмента
 * @param {boolean} highlight - Флаг выделения
 */
function highlightChartSegment(index, highlight) {
    if (compositionChart && compositionChart.data && compositionChart.data.datasets) {
        // Здесь можно добавить логику выделения сегмента
        // Например, изменение радиуса сегмента
        compositionChart.update();
    }
}

/**
 * Функция для генерации массива цветов
 * @param {number} count - Количество цветов для генерации
 * @returns {Array} - Массив цветов в формате rgba
 */
function generateColors(count) {
    const colors = [];
    const baseColors = [
        'rgba(255, 99, 132, 0.8)',
        'rgba(54, 162, 235, 0.8)',
        'rgba(255, 206, 86, 0.8)',
        'rgba(75, 192, 192, 0.8)',
        'rgba(153, 102, 255, 0.8)',
        'rgba(255, 159, 64, 0.8)',
        'rgba(199, 199, 199, 0.8)',
        'rgba(83, 102, 255, 0.8)',
        'rgba(40, 159, 64, 0.8)',
        'rgba(210, 199, 199, 0.8)',
    ];

    for (let i = 0; i < count; i++) {
        if (i < baseColors.length) {
            colors.push(baseColors[i]);
        } else {
            // Генерируем случайный цвет
            const r = Math.floor(Math.random() * 200 + 25);
            const g = Math.floor(Math.random() * 200 + 25);
            const b = Math.floor(Math.random() * 200 + 25);
            colors.push(`rgba(${r}, ${g}, ${b}, 0.8)`);
        }
    }

    return colors;
}

/**
 * Функция для обновления цен активов в портфеле
 */
function updatePortfolioPrices() {
    console.log("Обновление цен для портфеля", PORTFOLIO_ID);
    showSpinner();

    fetch(`/api/portfolio/${PORTFOLIO_ID}/update_prices`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log("Ответ на обновление цен:", response.status);
        return response.json();
    })
    .then(data => {
        hideSpinner();
        if (data.success) {
            showNotification(data.message);
            // Перезагружаем страницу для обновления данных
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showNotification('Не удалось обновить цены: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    })
    .catch(error => {
        console.error("Ошибка при обновлении цен:", error);
        hideSpinner();
        showNotification("Ошибка: " + error.message, 'error');
    });
}

/**
 * Показать диалог подтверждения удаления транзакции
 * @param {number} transactionId - ID транзакции для удаления
 */
function showDeleteConfirmation(transactionId) {
    console.log("Показ диалога подтверждения удаления транзакции:", transactionId);

    const modal = document.getElementById('confirmModal');
    const confirmMessage = document.getElementById('confirmMessage');
    const confirmBtn = document.getElementById('confirmBtn');

    if (!modal || !confirmMessage || !confirmBtn) {
        console.error("Не найдены элементы модального окна");
        return;
    }

    confirmMessage.textContent = 'Вы уверены, что хотите удалить эту транзакцию? Это действие нельзя отменить.';

    // Настраиваем кнопку подтверждения
    confirmBtn.onclick = function() {
        modal.style.display = 'none';
        deleteTransaction(transactionId);
    };

    // Показываем модальное окно
    modal.style.display = 'block';
}

/**
 * Удаление транзакции
 * @param {number} transactionId - ID транзакции для удаления
 */
function deleteTransaction(transactionId) {
    console.log("Удаление транзакции", transactionId);
    showSpinner();

    fetch(`/api/portfolio/${PORTFOLIO_ID}/delete_transaction`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            transaction_id: transactionId
        })
    })
    .then(handleResponse)
    .then(data => {
        hideSpinner();
        if (data.success) {
            showNotification(data.message);

            // Удаляем строку транзакции из таблицы
            const row = document.querySelector(`tr[data-tx-id="${transactionId}"]`);
            if (row) {
                row.style.backgroundColor = '#ffebee';
                row.style.opacity = '0.5';
                setTimeout(() => {
                    row.remove();

                    // Проверяем, остались ли транзакции
                    const remainingRows = document.querySelectorAll('.transactions-table tbody tr').length;
                    if (remainingRows === 0) {
                        const emptyRow = document.createElement('tr');
                        emptyRow.innerHTML = '<td colspan="6" class="empty-message">Нет транзакций в истории</td>';
                        document.querySelector('.transactions-table tbody').appendChild(emptyRow);
                    }
                }, 500);
            }

            // Перезагружаем страницу через 2 секунды для обновления всех данных
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showNotification('Не удалось удалить транзакцию', 'error');
        }
    })
    .catch(handleError);
}

/**
 * Обработка ответа от API
 * @param {Response} response - Объект ответа fetch
 * @returns {Promise} - Промис с данными
 */
function handleResponse(response) {
    if (!response.ok) {
        return response.json().then(data => {
            throw new Error(data.error || `Ошибка: ${response.status}`);
        });
    }
    return response.json();
}

/**
 * Обработка ошибок
 * @param {Error} error - Объект ошибки
 */
function handleError(error) {
    console.error('API Error:', error);
    hideSpinner();
    showNotification(error.message, 'error');
}

/**
 * Функция для отображения спиннера загрузки
 */
function showSpinner() {
    const spinnerOverlay = document.getElementById('spinnerOverlay');
    if (spinnerOverlay) {
        spinnerOverlay.style.display = 'flex';
    }
}

/**
 * Функция для скрытия спиннера загрузки
 */
function hideSpinner() {
    const spinnerOverlay = document.getElementById('spinnerOverlay');
    if (spinnerOverlay) {
        spinnerOverlay.style.display = 'none';
    }
}

/**
 * Функция для отображения уведомления
 * @param {string} message - Сообщение уведомления
 * @param {string} type - Тип уведомления (success, error, warning)
 */
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    if (!notification) {
        console.error("Элемент уведомления не найден");
        return;
    }

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