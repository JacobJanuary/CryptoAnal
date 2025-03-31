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

        // Update onclick attribute with the new state
        button.setAttribute('onclick', `toggleFavorite('${coinId}', ${newVal})`);
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
                // Reset onclick attribute to original state
                button.setAttribute('onclick', `toggleFavorite('${coinId}', ${currentVal})`);
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
            // Reset onclick attribute to original state
            button.setAttribute('onclick', `toggleFavorite('${coinId}', ${currentVal})`);
        }
    });
}

// Initialize on page load
window.onload = function() {
    // Initialize tooltips
    setupCategoryTooltips();
};