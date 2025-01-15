// main.js


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

    document.querySelectorAll('#cryptoTable th[data-type]').forEach((header, index) => {
        header.addEventListener('click', () => {
            const type = header.getAttribute('data-type');
            sortTable(index, type);
        });
    });
};
