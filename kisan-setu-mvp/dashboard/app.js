// Kisan-Setu Dashboard - Real-Time Updates

// API Gateway endpoint
const API_GATEWAY = 'https://061d3ls8qh.execute-api.ap-south-1.amazonaws.com/prod';

// API Key — set this after deployment (API Gateway > API Keys in AWS Console)
const API_KEY = '';

// State
let messages = [];
let farmers = new Set();
let creditScores = {};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

/**
 * Fetch JSON from the API Gateway with the x-api-key header.
 * Throws on non-2xx responses so callers can handle errors uniformly.
 */
async function apiFetch(path) {
    const response = await fetch(`${API_GATEWAY}${path}`, {
        headers: { 'x-api-key': API_KEY }
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return response.json();
}

/**
 * Wrapper around apiFetch that catches errors, shows an error banner via
 * showError(), and retries after `retryDelay` ms (default 5 000).
 * Returns the parsed JSON on success, or null on failure.
 */
async function fetchWithRetry(path, retryDelay = 5000) {
    try {
        return await apiFetch(path);
    } catch (error) {
        console.error(`Fetch failed for ${path}:`, error);
        showError(`Failed to load data from ${path}`);
        setTimeout(() => fetchWithRetry(path, retryDelay), retryDelay);
        return null;
    }
}

// ---------------------------------------------------------------------------
// Initialise dashboard
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    initSatelliteMap();
    initCreditChart();
    startLiveFeed();
});

// ---------------------------------------------------------------------------
// Satellite map — farmer locations + NDVI
// ---------------------------------------------------------------------------

let satelliteMap;

function initSatelliteMap() {
    satelliteMap = L.map('satellite-map').setView([19.7515, 75.7139], 10);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(satelliteMap);

    // Kick off the first data fetch
    fetchFarmers();
}

/**
 * Fetch farmer/NDVI data from the API and render map markers.
 * Falls back to a "no data" message when the API is unreachable or empty.
 */
async function fetchFarmers() {
    const data = await fetchWithRetry('/credit');

    if (!data || !Array.isArray(data.farmers) || data.farmers.length === 0) {
        console.warn('No farmer data available from API');
        showError('No live farmer data available — configure API endpoints');
        return;
    }

    data.farmers.forEach(farmer => {
        const color = getNDVIColor(farmer.ndvi);
        const circle = L.circle([farmer.lat, farmer.lon], {
            color: color,
            fillColor: color,
            fillOpacity: 0.5,
            radius: 2000
        }).addTo(satelliteMap);

        circle.bindPopup(`
            <strong>${farmer.name}</strong><br>
            Crop: ${farmer.crop}<br>
            NDVI: ${farmer.ndvi.toFixed(3)}<br>
            Health: ${getHealthStatus(farmer.ndvi)}
        `);
    });
}

// Get NDVI color (green = healthy, red = stressed)
function getNDVIColor(ndvi) {
    if (ndvi > 0.7) return '#10b981'; // Healthy - green
    if (ndvi > 0.5) return '#f59e0b'; // Moderate - orange
    return '#ef4444'; // Stressed - red
}

// Get health status
function getHealthStatus(ndvi) {
    if (ndvi > 0.7) return 'Healthy 🟢';
    if (ndvi > 0.5) return 'Moderate 🟡';
    return 'Stressed 🔴';
}

// ---------------------------------------------------------------------------
// Credit score chart
// ---------------------------------------------------------------------------

let creditChart;

function initCreditChart() {
    const ctx = document.getElementById('credit-chart').getContext('2d');

    // Create chart with empty data — filled once the API responds
    creditChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Average Credit Score',
                data: [],
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointRadius: 5,
                pointBackgroundColor: '#667eea'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top' },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    min: 0,
                    max: 100,
                    ticks: { callback: value => value },
                    title: { display: true, text: 'Credit Score (0-100)' }
                },
                x: {
                    title: { display: true, text: 'Time Period' }
                }
            }
        }
    });

    // Kick off the first data fetch
    fetchCreditScores();
}

/**
 * Fetch credit score history from the API and update the chart.
 * Falls back to a "no data" message when the API is unreachable or empty.
 */
async function fetchCreditScores() {
    const data = await fetchWithRetry('/credit');

    if (!data || !Array.isArray(data.scores) || data.scores.length === 0) {
        console.warn('No credit score data available from API');
        return;
    }

    const dates = data.scores.map(s => s.date);
    const scores = data.scores.map(s => s.score);

    creditChart.data.labels = dates;
    creditChart.data.datasets[0].data = scores;
    creditChart.update();
}

// ---------------------------------------------------------------------------
// Live message feed
// ---------------------------------------------------------------------------

// Start live message feed — polls every 5 seconds
function startLiveFeed() {
    fetchMessages(); // Initial load
    setInterval(fetchMessages, 5000);
}

/**
 * Fetch recent messages from the API and render them in the feed.
 * If the API is unreachable or returns no data, shows an informational message.
 */
async function fetchMessages() {
    try {
        const data = await apiFetch('/messages');

        if (!data || !Array.isArray(data.messages) || data.messages.length === 0) {
            if (messages.length === 0) {
                showError('No live message data available — configure API endpoints');
            }
            updateStats();
            return;
        }

        const feed = document.getElementById('message-feed');

        data.messages.forEach(msg => {
            // Avoid duplicates based on sender + time
            const isDuplicate = messages.some(
                m => m.sender === msg.sender && m.time === msg.time && m.content === msg.content
            );
            if (!isDuplicate) {
                messages.push(msg);
                farmers.add(msg.sender);
                renderMessage(msg);
            }
        });

        updateStats();
    } catch (error) {
        console.error('Error fetching messages:', error);
        if (messages.length === 0) {
            showError('No live message data available — configure API endpoints');
        }
        updateStats();
    }
}

// Render a single message into the feed
function renderMessage(msg) {
    const feed = document.getElementById('message-feed');

    const messageEl = document.createElement('div');
    messageEl.className = 'message-item';

    const typeIcon = {
        'text': '💬',
        'image': '📷',
        'voice': '🎤',
        'document': '📄'
    }[msg.type] || '📨';

    messageEl.innerHTML = `
        <div class="message-header">
            <div>
                <span class="message-sender">${msg.name || msg.sender}</span>
                <span class="message-type">${typeIcon} ${msg.type}</span>
                <span class="language-badge">${msg.language.toUpperCase()}</span>
            </div>
            <span class="message-time">${msg.time}</span>
        </div>
        <div class="message-content">${msg.content}</div>
    `;

    feed.insertBefore(messageEl, feed.firstChild);

    // Cap visible messages at 50 to prevent DOM bloat
    const MAX_MESSAGES = 50;
    while (feed.children.length > MAX_MESSAGES) {
        feed.removeChild(feed.lastChild);
    }
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

function updateStats() {
    document.getElementById('stat-messages').textContent = messages.length;
    document.getElementById('stat-farmers').textContent = farmers.size;
    document.getElementById('stat-ledgers').textContent = messages.filter(m => m.type === 'image').length;
    document.getElementById('message-count').textContent = `${messages.length} messages`;
}

// ---------------------------------------------------------------------------
// Error / info UI
// ---------------------------------------------------------------------------

/**
 * Display an error or informational banner inside the message feed area.
 * Used when API requests fail or return empty data.
 */
function showError(message) {
    const feed = document.getElementById('message-feed');
    feed.innerHTML = `
        <div class="no-data">
            <p style="color: #ef4444;">⚠️ ${message}</p>
            <p style="margin-top: 10px; color: #999;">Retrying in 5 seconds...</p>
        </div>
    `;
}
