/**
 * portfolios-list.js - JavaScript for the portfolios list page
 */

document.addEventListener('DOMContentLoaded', function() {
    // Добавляем анимацию появления карточек портфелей
    const portfolioCards = document.querySelectorAll('.portfolio-card');

    portfolioCards.forEach((card, index) => {
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
});