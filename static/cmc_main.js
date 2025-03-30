// Tooltip functionality
let tooltipDiv = null;

function showCategoryTooltip(event) {
    // Get element via event.currentTarget
    const targetElem = event.currentTarget;
    if (!targetElem) return;

    // Read category list from data attribute
    const categories = targetElem.getAttribute('data-categories');
    if (!categories || categories.trim() === '') {
        return;
    }

    // Display tooltip
    tooltipDiv.style.display = 'block';
    tooltipDiv.textContent = categories;

    // Position near cursor
    tooltipDiv.style.left = (event.pageX + 10) + 'px';
    tooltipDiv.style.top = (event.pageY + 10) + 'px';
}

function moveCategoryTooltip(event) {
    // Move tooltip with cursor
    tooltipDiv.style.left = (event.pageX + 10) + 'px';
    tooltipDiv.style.top = (event.pageY + 10) + 'px';
}

function hideCategoryTooltip() {
    tooltipDiv.style.display = 'none';
}

// Set up tooltip handlers
function setupCategoryTooltips() {
    tooltipDiv = document.getElementById('category-tooltip');
    if (!tooltipDiv) return;

    const table = document.querySelector('table');
    if (!table) return;

    const rows = table.tBodies[0].rows;
    for (let row of rows) {
        row.addEventListener('mouseover', showCategoryTooltip);
        row.addEventListener('mousemove', moveCategoryTooltip);
        row.addEventListener('mouseout', hideCategoryTooltip);
    }
}

// Format analytics content
function formatAnalyticsContent(content) {
    if (!content) return 'No data available';

    return content
        .replace(/###\s*(.*?)\n/g, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

// Coin filtering functionality
function toggleCoinFilter() {
    // Get current state from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const isFiltered = urlParams.get('filtered') === 'true';
    const category = urlParams.get('category') || '678ded1251eda549b5afd3fe';
    const sort_by = urlParams.get('sort_by') || 'market_cap_rank';
    const order = urlParams.get('order') || 'asc';

    // Toggle filter state and redirect
    if (isFiltered) {
        // Remove filter
        window.location.href = `/?category=${category}&sort_by=${sort_by}&order=${order}`;
    } else {
        // Apply filter
        window.location.href = `/?category=${category}&sort_by=${sort_by}&order=${order}&filtered=true`;
    }
}

// Toggle favorite status
function toggleFavorite(coinId, currentVal) {
    console.log(`toggleFavorite called for coin ${coinId} with currentVal=${currentVal} (${typeof currentVal})`);

    // Convert to boolean if needed
    if (currentVal === 1) currentVal = true;
    if (currentVal === 0) currentVal = false;

    const newVal = !currentVal;
    console.log(`Setting favorite status to ${newVal}`);

    // Change UI immediately for better feedback
    const button = document.querySelector(`button[onclick*="toggleFavorite('${coinId}"]`);
    if (button) {
        console.log("Button found, updating UI");
        if (newVal) {
            button.innerHTML = '★';
            button.classList.add('favorite-active');
        } else {
            button.innerHTML = '☆';
            button.classList.remove('favorite-active');
        }
    } else {
        console.log("Button not found in DOM");
    }

    // Send request to server
    const requestData = {
        id: coinId,
        isFavourites: newVal
    };

    console.log("Sending request:", requestData);

    fetch('/toggle_favourite', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        console.log("Response status:", response.status);
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("Server response:", data);
        if (data.error) {
            alert(`Error: ${data.error}`);
            // Revert UI on error
            if (button) {
                if (currentVal) {
                    button.innerHTML = '★';
                    button.classList.add('favorite-active');
                } else {
                    button.innerHTML = '☆';
                    button.classList.remove('favorite-active');
                }
            }
            return;
        }

        console.log(`Successfully ${data.action} to favorites`);
        // Don't reload the page
    })
    .catch(error => {
        console.error('Error toggling favorite:', error);
        alert(`An error occurred: ${error.message}`);
        // Revert UI on error
        if (button) {
            if (currentVal) {
                button.innerHTML = '★';
                button.classList.add('favorite-active');
            } else {
                button.innerHTML = '☆';
                button.classList.remove('favorite-active');
            }
        }
    });
}

// Show coin details in modal
function showCoinDetails(coinId) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalContent = document.getElementById('modal-content-data');
    const modalLoading = document.getElementById('modal-loading');

    // Show loading state
    modalTitle.textContent = "Loading...";
    modalContent.innerHTML = "";
    modalLoading.style.display = 'block';
    modalContent.style.display = 'none';
    modal.style.display = 'block';

    // Fetch coin details
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

            // Set modal title
            modalTitle.textContent = `${data.name} (${data.symbol})`;

            // Create HTML content
            let html = "";

            // Coin information section
            let mcMln = data.market_cap ? (data.market_cap / 1e6).toFixed(2) : "N/A";
            let rank = data.market_cap_rank || "N/A";
            let volMln = data.total_volume_usd ? (data.total_volume_usd / 1e6).toFixed(2) : "N/A";
            let cPrice = data.current_price_usd ? parseFloat(data.current_price_usd).toFixed(4) : "N/A";
            let athVal = data.ath_usd ? parseFloat(data.ath_usd).toFixed(4) : "N/A";
            let atlVal = data.atl_usd ? parseFloat(data.atl_usd).toFixed(4) : "N/A";

            // Price changes
            let h1Change = data.percent_change_1h ? parseFloat(data.percent_change_1h).toFixed(2) : "N/A";
            let h24Change = data.price_change_percentage_24h ? parseFloat(data.price_change_percentage_24h).toFixed(2) : "N/A";
            let d7Change = data.percent_change_7d ? parseFloat(data.percent_change_7d).toFixed(2) : "N/A";
            let d30Change = data.percent_change_30d ? parseFloat(data.percent_change_30d).toFixed(2) : "N/A";

            // Historical data
            let max365 = data.max_365d_price ? parseFloat(data.max_365d_price).toFixed(4) : "N/A";
            let max365Date = data.max_365d_date ? new Date(data.max_365d_date).toLocaleDateString() : "N/A";
            let percMaxToCurrent = data.perc_change_max_to_current ? parseFloat(data.perc_change_max_to_current).toFixed(2) : "N/A";
            let min365 = data.min_365d_price ? parseFloat(data.min_365d_price).toFixed(4) : "N/A";
            let min365Date = data.min_365d_date ? new Date(data.min_365d_date).toLocaleDateString() : "N/A";
            let percMinToCurrent = data.perc_change_min_to_current ? parseFloat(data.perc_change_min_to_current).toFixed(2) : "N/A";

            // Other stats
            let highVolDays = data.high_volume_days || "N/A";
            let totalDays = data.total_days || "N/A";

            // Build sections
            html += `<h3>Coin Information</h3>`;
            html += `<p><strong>Market Cap:</strong> $${mcMln}M (Rank: ${rank})</p>`;
            html += `<p><strong>Volume 24h:</strong> $${volMln}M | <strong>Price:</strong> $${cPrice}</p>`;

            html += `<h3>Price Changes</h3>`;
            html += `<p><strong>1h:</strong> ${h1Change}% | <strong>24h:</strong> ${h24Change}% | <strong>7d:</strong> ${d7Change}% | <strong>30d:</strong> ${d30Change}%</p>`;
            html += `<p><strong>ATH:</strong> $${athVal} | <strong>ATL:</strong> $${atlVal}</p>`;

            html += `<h3>365-Day Range</h3>`;
            html += `<p><strong>High:</strong> $${max365} (${max365Date}) ${percMaxToCurrent}% from current</p>`;
            html += `<p><strong>Low:</strong> $${min365} (${min365Date}) ${percMinToCurrent}% from current</p>`;

            if (highVolDays !== "N/A" && totalDays !== "N/A") {
                html += `<p><strong>High Volume Days:</strong> ${highVolDays} out of ${totalDays} total days</p>`;
            }

            // AI Analytics section
            html += `<hr><h3>AI Analytics</h3>`;
            html += formatAnalyticsContent(data.AI_text);

            // AI Investment data
            html += `<h3>Investment Analysis</h3>`;
            html += formatAnalyticsContent(data.AI_invest);

            // Additional analysis if available
            if (data.gemini_invest) {
                html += `<h3>Additional Investment Analysis</h3>`;
                html += formatAnalyticsContent(data.gemini_invest);
            }

            // Update modal with content
            modalContent.innerHTML = html;
            modalLoading.style.display = 'none';
            modalContent.style.display = 'block';
        })
        .catch(err => {
            console.error("Error loading coin details:", err);
            alert("Error: " + err.message);
            modal.style.display = 'none';
        });
}

// Close modal
function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Initialize on page load
window.onload = function() {
    // Initialize tooltips
    setupCategoryTooltips();

    // Set up close button for modal
    const closeButton = document.getElementById('close-modal');
    if (closeButton) {
        closeButton.addEventListener('click', closeModal);
    }
};