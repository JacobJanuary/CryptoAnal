/**
 * crypto-modal.js - JavaScript для работы с модальным окном деталей криптовалюты
 */

// Функция для отображения деталей криптовалюты
function showCoinDetails(coinId) {
    const modal = document.getElementById('cryptoModal');
    const modalContent = document.getElementById('cryptoModalContent');
    const modalLoading = document.getElementById('cryptoModalLoading');

    // Показываем индикатор загрузки
    modalLoading.style.display = 'flex';

    // Блокируем прокрутку страницы
    document.body.style.overflow = 'hidden';

    // Очищаем содержимое модального окна
    modalContent.innerHTML = "";

    // Показываем само модальное окно
    modal.style.display = 'block';

    // Запрашиваем данные о монете
    fetch(`/coin_details/${coinId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            // Форматируем значения
            let mcMln = data.market_cap ? (data.market_cap / 1e6).toFixed(2) : "N/A";
            let rank = data.market_cap_rank || "N/A";
            let volMln = data.total_volume_usd ? (data.total_volume_usd / 1e6).toFixed(2) : "N/A";
            let cPrice = data.current_price_usd ? parseFloat(data.current_price_usd).toFixed(data.current_price_usd < 1 ? 4 : 2) : "N/A";

            // Форматируем изменения цены
            let h1Change = data.percent_change_1h ? parseFloat(data.percent_change_1h).toFixed(2) : "N/A";
            let h24Change = data.price_change_percentage_24h ? parseFloat(data.price_change_percentage_24h).toFixed(2) : "N/A";
            let d7Change = data.percent_change_7d ? parseFloat(data.percent_change_7d).toFixed(2) : "N/A";
            let d30Change = data.percent_change_30d ? parseFloat(data.percent_change_30d).toFixed(2) : "N/A";
            let d60Change = data.percent_change_60d ? parseFloat(data.percent_change_60d).toFixed(2) : "N/A";
            let d90Change = data.percent_change_90d ? parseFloat(data.percent_change_90d).toFixed(2) : "N/A";

            // Форматируем дату запуска
            let launchDate = data.date_added ? new Date(data.date_added).toLocaleDateString() : "N/A";

            // Информация о поставках
            let circulatingSupply = data.circulating_supply ? formatNumber(data.circulating_supply) : "N/A";
            let totalSupply = data.total_supply ? formatNumber(data.total_supply) : "N/A";

            // Исторические данные
            let max365 = data.max_365d_price ? parseFloat(data.max_365d_price).toFixed(4) : "N/A";
            let max365Date = data.max_365d_date ? new Date(data.max_365d_date).toLocaleDateString() : "N/A";
            let min365 = data.min_365d_price ? parseFloat(data.min_365d_price).toFixed(4) : "N/A";
            let min365Date = data.min_365d_date ? new Date(data.min_365d_date).toLocaleDateString() : "N/A";

            // Создаем HTML структуру
            let html = `
                <div id="cryptoModalHeader">
                    <h3>${data.name} <span class="coin-symbol">${data.symbol.toUpperCase()}</span></h3>
                    <button id="cryptoModalClose">×</button>
                </div>
                <div id="cryptoModalBody">
                    <!-- Сетка статистики (без 24h Change) -->
                    <div class="coin-stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">Price</div>
                            <div class="stat-value">$${cPrice}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Market Cap</div>
                            <div class="stat-value">$${mcMln}M</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Rank</div>
                            <div class="stat-value">#${rank}</div>
                        </div>
                    </div>
                    
                    <!-- Общая информация (без дублирования Market Cap) -->
                    <div class="coin-section">
                        <div class="section-header">
                            <span style="margin-right: 10px;">ℹ️</span>
                            <h3>Coin Information</h3>
                        </div>
                        <div class="section-content">
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; width: 30%; font-weight: 600;">Дата запуска:</td>
                                    <td style="padding: 8px 0;">${launchDate}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: 600;">Supply:</td>
                                    <td style="padding: 8px 0;">${circulatingSupply} (${totalSupply})</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: 600;">Volume 24h:</td>
                                    <td style="padding: 8px 0;">$${volMln}M</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                    
                    <!-- История цен с 6 периодами изменений -->
                    <div class="coin-section">
                        <div class="section-header">
                            <span style="margin-right: 10px;">📈</span>
                            <h3>365-Day Range</h3>
                        </div>
                        <div class="section-content">
                            <div class="price-range">
                                <div>
                                    <div>$${min365}</div>
                                    <div class="range-date">${min365Date}</div>
                                </div>
                                <div>
                                    <div>$${max365}</div>
                                    <div class="range-date">${max365Date}</div>
                                </div>
                            </div>
                            
                            <div class="price-slider">
                                ${calculatePriceRange(data.min_365d_price, data.max_365d_price, data.current_price_usd)}
                            </div>
                            
                            <div class="data-grid" style="margin-top: 25px;">
                                <div class="data-item">
                                    <div class="data-label">1h Change</div>
                                    <div class="data-value ${parseFloat(h1Change) > 0 ? 'positive-change' : parseFloat(h1Change) < 0 ? 'negative-change' : ''}">${h1Change}%</div>
                                </div>
                                <div class="data-item">
                                    <div class="data-label">24h Change</div>
                                    <div class="data-value ${parseFloat(h24Change) > 0 ? 'positive-change' : parseFloat(h24Change) < 0 ? 'negative-change' : ''}">${h24Change}%</div>
                                </div>
                                <div class="data-item">
                                    <div class="data-label">7d Change</div>
                                    <div class="data-value ${parseFloat(d7Change) > 0 ? 'positive-change' : parseFloat(d7Change) < 0 ? 'negative-change' : ''}">${d7Change}%</div>
                                </div>
                                <div class="data-item">
                                    <div class="data-label">30d Change</div>
                                    <div class="data-value ${parseFloat(d30Change) > 0 ? 'positive-change' : parseFloat(d30Change) < 0 ? 'negative-change' : ''}">${d30Change}%</div>
                                </div>
                                <div class="data-item">
                                    <div class="data-label">60d Change</div>
                                    <div class="data-value ${parseFloat(d60Change) > 0 ? 'positive-change' : parseFloat(d60Change) < 0 ? 'negative-change' : ''}">${d60Change}%</div>
                                </div>
                                <div class="data-item">
                                    <div class="data-label">90d Change</div>
                                    <div class="data-value ${parseFloat(d90Change) > 0 ? 'positive-change' : parseFloat(d90Change) < 0 ? 'negative-change' : ''}">${d90Change}%</div>
                                </div>
                            </div>
                        </div>
                    </div>`;

            // Добавляем раздел аналитики, если он доступен
            if (data.AI_text && !data.gemini_invest) {
                html += `
                    <!-- Раздел аналитики -->
                    <div class="coin-section">
                        <div class="section-header">
                            <span style="margin-right: 10px;">🧠</span>
                            <h3>AI Analytics</h3>
                        </div>
                        <div class="section-content analytics-content">
                            ${formatAnalyticsContent(data.AI_text)}
                        </div>
                    </div>`;
            }

            // Добавляем инвестиционный анализ, если он доступен
            if (data.AI_invest && !data.gemini_invest) {
                html += `
                    <!-- Инвестиционный анализ -->
                    <div class="coin-section">
                        <div class="section-header">
                            <span style="margin-right: 10px;">💰</span>
                            <h3>Investment Analysis</h3>
                        </div>
                        <div class="section-content analytics-content">
                            ${formatAnalyticsContent(data.AI_invest)}
                        </div>
                    </div>`;
            }

            // Добавляем дополнительный анализ, если он доступен
            if (data.gemini_invest) {
                html += `
                    <!-- Дополнительный анализ -->
                    <div class="coin-section">
                        <div class="section-header">
                            <span style="margin-right: 10px;">📊</span>
                            <h3>Additional Investment Analysis</h3>
                        </div>
                        <div class="section-content analytics-content">
                            ${formatAnalyticsContent(data.gemini_invest)}
                        </div>
                    </div>`;
            }

            html += `</div>`; // Закрываем modal-body

            // Обновляем содержимое модального окна
            modalContent.innerHTML = html;

            // Скрываем индикатор загрузки
            modalLoading.style.display = 'none';

            // Настраиваем кнопку закрытия
            document.getElementById('cryptoModalClose').addEventListener('click', closeCryptoModal);
        })
        .catch(err => {
            console.error("Error loading coin details:", err);

            // Показываем сообщение об ошибке
            modalContent.innerHTML = `
                <div id="cryptoModalHeader">
                    <h3>Error</h3>
                    <button id="cryptoModalClose">×</button>
                </div>
                <div id="cryptoModalBody" style="text-align: center; padding: 40px 20px;">
                    <div style="font-size: 50px; margin-bottom: 20px;">⚠️</div>
                    <p style="font-size: 18px; color: #e74c3c;">${err.message}</p>
                    <button style="padding: 10px 20px; background-color: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 20px;" onclick="closeCryptoModal()">Close</button>
                </div>
            `;

            // Скрываем индикатор загрузки
            modalLoading.style.display = 'none';

            // Настраиваем кнопку закрытия
            document.getElementById('cryptoModalClose').addEventListener('click', closeCryptoModal);
        });
}

// Вспомогательные функции остаются без изменений
function calculatePriceRange(minPrice, maxPrice, currentPrice) {
    if (!minPrice || !maxPrice || !currentPrice) {
        return `
            <div class="price-slider-fill" style="width: 0%"></div>
            <div class="price-slider-handle" style="left: 0%"></div>
        `;
    }

    const min = parseFloat(minPrice);
    const max = parseFloat(maxPrice);
    const current = parseFloat(currentPrice);

    // Рассчитываем процентное положение
    let position = 0;
    if (max > min) {
        position = ((current - min) / (max - min)) * 100;
        // Ограничиваем значения от 0 до 100
        position = Math.max(0, Math.min(100, position));
    }

    return `
        <div class="price-slider-fill" style="width: ${position}%"></div>
        <div class="price-slider-handle" style="left: ${position}%"></div>
    `;
}

function formatAnalyticsContent(content) {
    if (!content) return '<p>No data available</p>';

    // Расширенное форматирование
    let formatted = content
        .replace(/###\s*(.*?)\n/g, '<h4>$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    // Оборачиваем в теги параграфа, если они еще не добавлены
    if (!formatted.startsWith('<p>')) {
        formatted = '<p>' + formatted;
    }
    if (!formatted.endsWith('</p>')) {
        formatted = formatted + '</p>';
    }

    // Очищаем возможные проблемы с параграфами
    formatted = formatted.replace(/<p><\/p>/g, '');

    return formatted;
}

function formatNumber(num) {
    if (num === null || num === undefined) return "N/A";

    // Обработка научной нотации
    if (num > 1e9) {
        return (num / 1e9).toFixed(2) + "B";
    } else if (num > 1e6) {
        return (num / 1e6).toFixed(2) + "M";
    } else if (num > 1e3) {
        return (num / 1e3).toFixed(2) + "K";
    }

    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Функция закрытия модального окна
function closeCryptoModal() {
    const modal = document.getElementById('cryptoModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = ''; // Восстанавливаем прокрутку страницы
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded, setting up crypto modal"); // Отладочный вывод

    // Проверяем, существует ли модальное окно
    const modal = document.getElementById('cryptoModal');
    if (!modal) {
        console.error("Modal element #cryptoModal not found in DOM");
        return;
    }

    // Настраиваем закрытие по клавише ESC
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeCryptoModal();
        }
    });

    // Настраиваем закрытие по клику вне модального окна
    modal.addEventListener('click', function(event) {
        if (event.target === this) {
            closeCryptoModal();
        }
    });

    console.log("Crypto modal setup completed");
});