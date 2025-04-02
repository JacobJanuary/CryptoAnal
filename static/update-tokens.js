/**
 * Функционал обновления данных о токенах
 */
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем кнопку обновления данных
    const updateBtn = document.getElementById('update-data-btn');

    if (updateBtn) {
        updateBtn.addEventListener('click', updateTokensData);
    }
});

/**
 * Обновление данных о токенах через API
 */
function updateTokensData() {
    const updateBtn = document.getElementById('update-data-btn');

    // Предотвращаем повторные клики во время загрузки
    if (updateBtn.classList.contains('loading')) {
        return;
    }

    // Показываем индикатор загрузки
    updateBtn.classList.add('loading');
    updateBtn.textContent = "Обновление...";

    // Показываем спиннер, если он есть
    const spinnerOverlay = document.getElementById('spinnerOverlay');
    if (spinnerOverlay) {
        spinnerOverlay.style.display = 'flex';
    }

    // Отправляем запрос к API
    fetch('/api/update_favourite_tokens', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка обновления данных');
            });
        }
        return response.json();
    })
    .then(data => {
        // Скрываем индикатор загрузки
        updateBtn.classList.remove('loading');
        updateBtn.textContent = "Обновить данные";

        if (spinnerOverlay) {
            spinnerOverlay.style.display = 'none';
        }

        // Показываем уведомление об успешном обновлении
        if (data.success) {
            // Используем функцию showNotification
            showNotification(`Данные успешно обновлены для ${data.updated_count} монет`);

            // Обновляем данные на странице без перезагрузки
            updatePageData();
        } else {
            showNotification('Не удалось обновить данные', 'error');
        }
    })
    .catch(error => {
        // Скрываем индикатор загрузки
        updateBtn.classList.remove('loading');
        updateBtn.textContent = "Обновить данные";

        if (spinnerOverlay) {
            spinnerOverlay.style.display = 'none';
        }

        console.error('Ошибка при обновлении данных:', error);
        showNotification(error.message, 'error');
    });
}

/**
 * Функция для обновления данных на странице без перезагрузки
 */
function updatePageData() {
    // Получаем обновленные данные для монет
    fetch('/cmc_favourites')
        .then(response => response.text())
        .then(html => {
            // Создаем временный элемент для парсинга HTML
            const parser = new DOMParser();
            const newDocument = parser.parseFromString(html, 'text/html');

            // Получаем таблицу с обновленными данными
            const newTable = newDocument.querySelector('#favorites-table tbody');
            const currentTable = document.querySelector('#favorites-table tbody');

            if (newTable && currentTable) {
                // Обновляем только ячейки с данными, сохраняя состояние фильтрации
                const currentRows = currentTable.querySelectorAll('tr');
                const newRows = newTable.querySelectorAll('tr');

                currentRows.forEach((row, index) => {
                    // Пропускаем строки, которых нет в новой таблице
                    if (index >= newRows.length) return;

                    const newRow = newRows[index];
                    const coinId = row.getAttribute('data-coin-id');

                    // Если ID монеты совпадает, обновляем данные
                    if (coinId && coinId === newRow.getAttribute('data-coin-id')) {
                        // Сохраняем стиль отображения для фильтров
                        const displayStyle = row.style.display;

                        // Обновляем содержимое ячеек (кроме последней с кнопками)
                        const cells = row.querySelectorAll('td:not(:last-child)');
                        const newCells = newRow.querySelectorAll('td:not(:last-child)');

                        cells.forEach((cell, cellIndex) => {
                            if (cellIndex < newCells.length) {
                                // Обновляем HTML-содержимое ячейки
                                cell.innerHTML = newCells[cellIndex].innerHTML;

                                // Копируем классы для отображения положительных/отрицательных значений
                                cell.className = newCells[cellIndex].className;
                            }
                        });

                        // Восстанавливаем состояние отображения для фильтров
                        row.style.display = displayStyle;
                    }
                });

                // Добавляем визуальный эффект обновления
                currentRows.forEach(row => {
                    // Не применяем эффект к скрытым строкам
                    if (row.style.display !== 'none') {
                        row.classList.add('updated-row');

                        // Убираем класс через некоторое время
                        setTimeout(() => {
                            row.classList.remove('updated-row');
                        }, 2000);
                    }
                });
            }
        })
        .catch(error => {
            console.error('Ошибка при обновлении данных на странице:', error);
            // Перезагружаем страницу в случае ошибки
            window.location.reload();
        });
}

/**
 * Отображение уведомления
 * @param {string} message - Текст уведомления
 * @param {string} type - Тип уведомления (success, error, warning)
 */
function showNotification(message, type = 'success') {
    let notification = document.getElementById('notification');

    // Если элемент уведомления не существует, создаем его
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        notification.className = 'notification';
        document.body.appendChild(notification);
    }

    // Очищаем предыдущие классы
    notification.className = 'notification';

    // Добавляем соответствующий класс в зависимости от типа
    if (type === 'error') {
        notification.classList.add('error');
    } else if (type === 'warning') {
        notification.classList.add('warning');
    } else {
        notification.classList.add('success');
    }

    // Устанавливаем текст сообщения
    notification.textContent = message;

    // Добавляем класс для отображения уведомления
    notification.classList.add('show');

    // Скрываем уведомление через 5 секунд
    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}