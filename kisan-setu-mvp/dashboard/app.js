// Kisan-Setu Dashboard - Real-Time Updates
// API Gateway endpoint
const API_GATEWAY = 'https://061d3ls8qh.execute-api.ap-south-1.amazonaws.com/prod';

// State
let messages = [];
let farmers = new Set();
let creditScores = {};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initSatelliteMap();
    initCreditChart();
    startLiveFeed();
    loadInitialData();
});

// Initialize satellite map with NDVI data
function initSatelliteMap() {
    const map = L.map('satellite-map').setView([19.7515, 75.7139], 10);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Mock farmer locations with NDVI data
    const mockFarmers = [
        { name: 'राज पाटील', lat: 19.7515, lon: 75.7139, ndvi: 0.75, crop: 'Onion' },
        { name: 'सुरेश देशमुख', lat: 19.8200, lon: 75.6500, ndvi: 0.82, crop: 'Wheat' },
        { name: 'विजय जाधव', lat: 19.6800, lon: 75.8000, ndvi: 0.68, crop: 'Cotton' },
        { name: 'अनिल कदम', lat: 19.7900, lon: 75.7800, ndvi: 0.55, crop: 'Soybean' },
        { name: 'मनोज शिंदे', lat: 19.7100, lon: 75.6800, ndvi: 0.71, crop: 'Onion' }
    ];

    mockFarmers.forEach(farmer => {
        const color = getNDVIColor(farmer.ndvi);
        const circle = L.circle([farmer.lat, farmer.lon], {
            color: color,
            fillColor: color,
            fillOpacity: 0.5,
            radius: 2000
        }).addTo(map);

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

// Initialize credit score chart
let creditChart;
function initCreditChart() {
    const ctx = document.getElementById('credit-chart').getContext('2d');

    // Mock credit score data
    const dates = ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'];
    const scores = [620, 635, 645, 660, 675, 685];

    creditChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Average Credit Score',
                data: scores,
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
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 550,
                    max: 850,
                    ticks: {
                        callback: function(value) {
                            return value;
                        }
                    },
                    title: {
                        display: true,
                        text: 'Credit Score (550-850)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time Period'
                    }
                }
            }
        }
    });
}

// Start live message feed
function startLiveFeed() {
    // Update every 5 seconds
    setInterval(fetchMessages, 5000);
    fetchMessages(); // Initial load
}

// Fetch messages from DynamoDB via API Gateway
async function fetchMessages() {
    try {
        // In production, this would query DynamoDB
        // For demo, show mock messages
        const feed = document.getElementById('message-feed');

        if (messages.length === 0) {
            // Show demo messages
            addDemoMessages();
        }

        // Update stats
        updateStats();
    } catch (error) {
        console.error('Error fetching messages:', error);
        showError('Failed to load messages');
    }
}

// Add demo messages
function addDemoMessages() {
    const demoMessages = [
        {
            sender: '+919876543210',
            name: 'राज पाटील',
            type: 'text',
            content: 'मेरा क्रेडिट स्कोर क्या है?',
            language: 'hi',
            time: new Date(Date.now() - 300000).toLocaleTimeString()
        },
        {
            sender: '+919876543211',
            name: 'सुरेश देशमुख',
            type: 'image',
            content: '📷 Uploaded ledger image for processing',
            language: 'hi',
            time: new Date(Date.now() - 600000).toLocaleTimeString()
        },
        {
            sender: '+919876543212',
            name: 'विजय जाधव',
            type: 'voice',
            content: '🎤 Voice message: मंडी मूल्य कितना है?',
            language: 'mr',
            time: new Date(Date.now() - 900000).toLocaleTimeString()
        },
        {
            sender: '+919876543213',
            name: 'System',
            type: 'text',
            content: 'Credit score calculated: 685/850 - Good standing',
            language: 'en',
            time: new Date(Date.now() - 120000).toLocaleTimeString()
        }
    ];

    const feed = document.getElementById('message-feed');
    feed.innerHTML = '';

    demoMessages.forEach(msg => {
        messages.push(msg);
        farmers.add(msg.sender);
        renderMessage(msg);
    });
}

// Render single message
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

// Update statistics
function updateStats() {
    document.getElementById('stat-messages').textContent = messages.length;
    document.getElementById('stat-farmers').textContent = farmers.size;
    document.getElementById('stat-ledgers').textContent = messages.filter(m => m.type === 'image').length;
    document.getElementById('message-count').textContent = `${messages.length} messages`;
}

// Load initial data from DynamoDB
async function loadInitialData() {
    try {
        // In production, would fetch from DynamoDB via API Gateway
        console.log('Dashboard initialized with demo data');
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

// Show error message
function showError(message) {
    const feed = document.getElementById('message-feed');
    feed.innerHTML = `
        <div class="no-data">
            <p style="color: #ef4444;">⚠️ ${message}</p>
            <p style="margin-top: 10px; color: #999;">Retrying in 5 seconds...</p>
        </div>
    `;
}

// Simulate new message arrival (for demo purposes)
setInterval(() => {
    if (Math.random() > 0.7) {
        const newMessage = {
            sender: '+919876543' + Math.floor(Math.random() * 1000),
            name: ['राज पाटील', 'सुरेश देशमुख', 'विजय जाधव'][Math.floor(Math.random() * 3)],
            type: ['text', 'image', 'voice'][Math.floor(Math.random() * 3)],
            content: 'New incoming message...',
            language: ['hi', 'mr', 'en'][Math.floor(Math.random() * 3)],
            time: new Date().toLocaleTimeString()
        };

        messages.push(newMessage);
        farmers.add(newMessage.sender);
        renderMessage(newMessage);
        updateStats();
    }
}, 10000); // New message every 10 seconds (demo)
