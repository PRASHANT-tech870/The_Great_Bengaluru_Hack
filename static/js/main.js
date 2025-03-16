// Global variables
let map;
let hexagonSource;
let driverSource;
let hexagonPopup;
let driverPopup;
let currentTimeSlot;

// Initialize the map when the page loads
$(document).ready(function() {
    // Initialize the map
    initMap();
    
    // Set up event handlers
    setupEventHandlers();
    
    // Note: loadData() is now called after the map is ready
});

// Initialize Azure Maps
function initMap() {
    // Initialize a map instance
    map = new atlas.Map('myMap', {
        center: [-74.0060, 40.7128],
        zoom: 11,
        view: 'Auto',
        authOptions: {
            authType: 'subscriptionKey',
            subscriptionKey: AZURE_MAPS_KEY
        }
    });
    
    // Wait until the map resources are ready
    map.events.add('ready', function() {
        // Create data sources
        hexagonSource = new atlas.source.DataSource();
        driverSource = new atlas.source.DataSource();
        map.sources.add([hexagonSource, driverSource]);
        
        // Create layers
        map.layers.add([
            // Hexagon fill layer
            new atlas.layer.PolygonLayer(hexagonSource, 'hexagon-fill', {
                fillColor: ['get', 'color'],
                fillOpacity: 0.5
            }),
            // Hexagon outline layer
            new atlas.layer.LineLayer(hexagonSource, 'hexagon-outline', {
                strokeColor: ['get', 'color'],
                strokeWidth: 1
            }),
            // Driver layer
            new atlas.layer.BubbleLayer(driverSource, 'driver-layer', {
                color: ['get', 'color'],
                radius: 5,
                strokeWidth: 0
            })
        ]);
        
        // Add route layer if needed
        if (driverSource.getShapes().some(shape => shape.getProperties().distance_km)) {
            // Add a background layer for routes
            map.layers.add(new atlas.layer.LineLayer(driverSource, 'route-background', {
                filter: ['has', 'distance_km'],
                strokeColor: 'white',
                strokeWidth: 5,
                strokeOpacity: 0.5,
                strokeDashArray: [1, 2]
            }));
            
            // Add the colored route layer
            map.layers.add(new atlas.layer.LineLayer(driverSource, 'route-layer', {
                filter: ['has', 'distance_km'],
                strokeColor: ['get', 'color'],
                strokeWidth: 3,
                strokeDashArray: [1, 2]
            }));
        }
        
        // Create popups
        hexagonPopup = new atlas.Popup({
            pixelOffset: [0, -10],
            closeButton: false
        });
        
        driverPopup = new atlas.Popup({
            pixelOffset: [0, -10],
            closeButton: false
        });
        
        // Add mouse events for hexagons - using proper event binding
        map.events.add('mouseover', 'hexagon-fill', showHexagonPopup);
        map.events.add('mouseover', 'hexagon-outline', showHexagonPopup);
        map.events.add('mouseout', 'hexagon-fill', hideHexagonPopup);
        map.events.add('mouseout', 'hexagon-outline', hideHexagonPopup);
        
        // Add mouse events for drivers - using proper event binding
        map.events.add('mouseover', 'driver-layer', showDriverPopup);
        map.events.add('mouseout', 'driver-layer', hideDriverPopup);
        
        // Load initial data after map is ready
        loadData();
    });
}

// Helper functions for popups
function showHexagonPopup(e) {
    if (e.shapes && e.shapes.length > 0) {
        const properties = e.shapes[0].getProperties();
        const content = `
            <div style="padding: 10px;">
                <b>Hex ID:</b> ${properties.hex_id}<br>
                <b>Demand:</b> ${properties.demand_level.charAt(0).toUpperCase() + properties.demand_level.slice(1)}<br>
                <b>Original Waiting Passengers:</b> ${properties.original_passenger_count}<br>
                <b>Current Waiting Passengers:</b> ${properties.current_passenger_count}
            </div>
        `;
        hexagonPopup.setOptions({
            content: content,
            position: e.position
        });
        hexagonPopup.open(map);
    }
}

function hideHexagonPopup() {
    hexagonPopup.close();
}

function showDriverPopup(e) {
    if (e.shapes && e.shapes.length > 0) {
        const properties = e.shapes[0].getProperties();
        const content = `
            <div style="padding: 10px;">
                <b>Driver ID:</b> ${properties.driver_id}<br>
                <b>Status:</b> ${properties.status.charAt(0).toUpperCase() + properties.status.slice(1)}
            </div>
        `;
        driverPopup.setOptions({
            content: content,
            position: e.position
        });
        driverPopup.open(map);
    }
}

function hideDriverPopup() {
    driverPopup.close();
}

// Set up event handlers
function setupEventHandlers() {
    // Time slot selection change
    $('#timeSlotSelect').change(function() {
        loadData();
    });
    
    // Send notifications button
    $('#sendNotificationsBtn').click(function() {
        sendNotifications();
    });
    
    // Simulate responses button
    $('#simulateResponsesBtn').click(function() {
        simulateResponses();
    });
}

// Load data based on selected time slot
function loadData() {
    currentTimeSlot = $('#timeSlotSelect').val();
    $('#mapTitle').text(`Demand Visualization for NYC at ${currentTimeSlot}`);
    
    // Reset buttons
    $('#simulateResponsesBtn').prop('disabled', true);
    
    // Get data from server
    $.ajax({
        url: '/get_data',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ time_slot: currentTimeSlot }),
        success: function(response) {
            // Update map with hexagon data
            hexagonSource.clear();
            hexagonSource.importDataFromUrl(
                'data:application/json;base64,' + 
                btoa(unescape(encodeURIComponent(JSON.stringify(response.hexagon_geojson))))
            );
            
            // Update map with driver data
            driverSource.clear();
            driverSource.importDataFromUrl(
                'data:application/json;base64,' + 
                btoa(unescape(encodeURIComponent(JSON.stringify(response.driver_geojson))))
            );
            
            // Update statistics
            updateStatistics(response.stats);
            
            // Enable/disable buttons based on state
            if (response.stats.notifications_sent) {
                $('#sendNotificationsBtn').prop('disabled', true);
                $('#simulateResponsesBtn').prop('disabled', false);
            } else {
                $('#sendNotificationsBtn').prop('disabled', false);
                $('#simulateResponsesBtn').prop('disabled', true);
            }
        },
        error: function(error) {
            console.error('Error loading data:', error);
        }
    });
}

// Send notifications to drivers
function sendNotifications() {
    $.ajax({
        url: '/send_notifications',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ time_slot: currentTimeSlot }),
        success: function(response) {
            // Show notification
            showNotification(response.message);
            
            // Reload data
            loadData();
        },
        error: function(error) {
            console.error('Error sending notifications:', error);
        }
    });
}

// Simulate driver responses
function simulateResponses() {
    $.ajax({
        url: '/simulate_responses',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ time_slot: currentTimeSlot }),
        success: function(response) {
            // Show notification
            showNotification(response.message);
            
            // Reload data
            loadData();
        },
        error: function(error) {
            console.error('Error simulating responses:', error);
        }
    });
}

// Update statistics display
function updateStatistics(stats) {
    let html = `
        <ul class="list-unstyled">
            <li>High demand areas: ${stats.high_demand_areas}</li>
            <li>Low demand areas: ${stats.low_demand_areas}</li>
            <li>Available drivers: ${stats.available_drivers}</li>
            <li>Total waiting passengers: ${stats.total_passengers}</li>
            <li>Average passengers per hexagon: ${stats.avg_passengers_per_hexagon}</li>
    `;
    
    if (stats.notifications_sent) {
        html += `<li>Notified drivers: ${stats.notified_drivers}</li>`;
        
        if (stats.accepted_count > 0) {
            html += `<li>Drivers who accepted rides: ${stats.accepted_count}</li>`;
        }
    }
    
    html += `</ul>`;
    
    $('#statistics').html(html);
}

// Show notification
function showNotification(message) {
    // Create notification element if it doesn't exist
    if ($('#notification').length === 0) {
        $('body').append('<div id="notification" class="notification"></div>');
    }
    
    // Set message and show
    $('#notification').text(message).fadeIn();
    
    // Hide after 3 seconds
    setTimeout(function() {
        $('#notification').fadeOut();
    }, 3000);
}