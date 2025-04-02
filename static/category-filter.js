/**
 * Скрипт фильтрации категорий с корректной поддержкой категории "Другое"
 */
document.addEventListener('DOMContentLoaded', function() {
    initCategoryFilter();
});

/**
 * Инициализация фильтра категорий
 */
function initCategoryFilter() {
    const categoryChips = document.querySelectorAll('.category-chip');
    const selectAllBtn = document.getElementById('select-all-btn');
    const deselectAllBtn = document.getElementById('deselect-all-btn');
    const emptyMessage = document.getElementById('empty-filter-message');
    const visibleCoinsCount = document.getElementById('visible-coins-count');
    const totalCoinsCount = document.getElementById('total-coins-count');
    const otherCategoryCount = document.getElementById('other-category-count');

    // Набор активных категорий
    let activeCategories = new Set();
    let isOtherCategoryActive = true;

    // Собираем все ID топовых категорий
    const topCategoryIds = new Set();
    categoryChips.forEach(chip => {
        const id = chip.getAttribute('data-category-id');
        if (id && id !== 'other') {
            topCategoryIds.add(id);
        }
    });

    // Подсчет токенов в категории "Другое"
    let otherCategoryTokensCount = countCoinsInOtherCategory(topCategoryIds);

    if (otherCategoryCount) {
        otherCategoryCount.textContent = otherCategoryTokensCount;
    }

    // Инициализация начального состояния
    categoryChips.forEach(chip => {
        const categoryId = chip.getAttribute('data-category-id');
        if (!categoryId) return;

        // По умолчанию все категории активны
        chip.classList.add('active');

        if (categoryId === 'other') {
            isOtherCategoryActive = true;
        } else {
            activeCategories.add(categoryId);
        }

        // Обработчик клика
        chip.addEventListener('click', function() {
            this.classList.toggle('active');

            if (categoryId === 'other') {
                isOtherCategoryActive = this.classList.contains('active');
            } else {
                if (this.classList.contains('active')) {
                    activeCategories.add(categoryId);
                } else {
                    activeCategories.delete(categoryId);
                }
            }

            applyFilter();
        });
    });

    // Обработчики кнопок
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function() {
            categoryChips.forEach(chip => {
                chip.classList.add('active');
                const id = chip.getAttribute('data-category-id');
                if (id === 'other') {
                    isOtherCategoryActive = true;
                } else if (id) {
                    activeCategories.add(id);
                }
            });
            applyFilter();
        });
    }

    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', function() {
            categoryChips.forEach(chip => {
                chip.classList.remove('active');
                const id = chip.getAttribute('data-category-id');
                if (id === 'other') {
                    isOtherCategoryActive = false;
                } else if (id) {
                    activeCategories.delete(id);
                }
            });
            applyFilter();
        });
    }

    /**
     * Подсчет монет в категории "Другое"
     * @param {Set} topCategoryIds - ID топовых категорий
     * @returns {number} Количество монет без топовых категорий
     */
    function countCoinsInOtherCategory(topCategoryIds) {
        const rows = document.querySelectorAll('.coin-row');
        let count = 0;

        rows.forEach(row => {
            const categoryIds = row.getAttribute('data-category-ids');
            if (!categoryIds || categoryIds.trim() === '') {
                count++;
                return;
            }

            // Проверяем, есть ли хотя бы одна топовая категория
            const rowCategoryIds = categoryIds.split(',').map(id => id.trim());
            const hasTopCategory = rowCategoryIds.some(id => topCategoryIds.has(id));

            if (!hasTopCategory) {
                count++;
            }
        });

        return count;
    }

    /**
     * Применение фильтра по категориям
     */
    function applyFilter() {
        const rows = document.querySelectorAll('.coin-row');
        let visibleCount = 0;

        rows.forEach(row => {
            const categoryIds = row.getAttribute('data-category-ids');

            // Проверка, входит ли монета в категорию "Другое"
            const isInOtherCategory = !categoryIds || !categoryIdsHaveTopCategory(categoryIds, topCategoryIds);

            // Если монета в категории "Другое" и она активна
            if (isInOtherCategory) {
                row.style.display = isOtherCategoryActive ? '' : 'none';
                if (isOtherCategoryActive) {
                    visibleCount++;
                }
                return;
            }

            // Для обычных монет, проверяем, есть ли у них активная категория
            const rowCategoryIds = categoryIds.split(',').map(id => id.trim());
            const shouldShow = rowCategoryIds.some(catId => activeCategories.has(catId));

            if (shouldShow) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Обновление счетчиков
        if (visibleCoinsCount) {
            visibleCoinsCount.textContent = visibleCount;
        }

        if (totalCoinsCount) {
            totalCoinsCount.textContent = visibleCount;
        }

        // Отображение сообщения при отсутствии результатов
        if (emptyMessage) {
            emptyMessage.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    }

    /**
     * Проверка, содержит ли строка ID категорий хотя бы одну топовую категорию
     * @param {string} categoryIdsString - Строка с ID категорий через запятую
     * @param {Set} topCategoryIds - Набор ID топовых категорий
     * @returns {boolean} - true, если содержит топовую категорию
     */
    function categoryIdsHaveTopCategory(categoryIdsString, topCategoryIds) {
        if (!categoryIdsString || categoryIdsString.trim() === '') {
            return false;
        }

        const categoryIds = categoryIdsString.split(',').map(id => id.trim());
        return categoryIds.some(id => topCategoryIds.has(id));
    }

    // Применяем фильтр при инициализации
    applyFilter();
}