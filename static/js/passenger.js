// Global variables
let map;
let datasource;
let popup;

// This function will be called after data is loaded
function initializePassengerMap() {
    console.log("Initializing passenger map with data:", {
        passengerId,
        mapKey: AZURE_MAPS_KEY ? "Available" : "Missing",
        hexagonFeatures: hexagonGeoJson?.features?.length || 0,
        driverFeatures: driverGeoJson?.features?.length || 0,
        passengerFeatures: passengerGeoJson?.features?.length || 0,
        pickupFeatures: pickupGeoJson?.features?.length || 0,
        walkingRouteFeatures: walkingRouteGeoJson?.features?.length || 0
    });
    
    // Log walking route data for debugging
    if (walkingRouteGeoJson && walkingRouteGeoJson.features && walkingRouteGeoJson.features.length > 0) {
        console.log("Walking route data:", walkingRouteGeoJson.features[0]);
        console.log("Walking route coordinates:", walkingRouteGeoJson.features[0].geometry.coordinates);
    } else {
        console.log("No walking route data available");
    }
    
    // Find the passenger's position to center the map
    let passengerLocation = null;
    
    if (passengerGeoJson && passengerGeoJson.features && passengerGeoJson.features.length > 0) {
        passengerLocation = passengerGeoJson.features[0].geometry.coordinates;
        console.log("Found passenger location:", passengerLocation);
    }
    
    // If no passenger location found, check if we have hexagons to center on
    if (!passengerLocation && hexagonGeoJson && hexagonGeoJson.features && hexagonGeoJson.features.length > 0) {
        // Get the center of the first hexagon
        const firstHexagon = hexagonGeoJson.features[0];
        const coords = firstHexagon.geometry.coordinates[0];
        
        // Calculate the center of the hexagon
        let sumLng = 0, sumLat = 0;
        for (const point of coords) {
            sumLng += point[0];
            sumLat += point[1];
        }
        passengerLocation = [sumLng / coords.length, sumLat / coords.length];
        console.log("Using hexagon center as fallback location");
    }
    
    // If still no location, use a default location in NYC
    if (!passengerLocation) {
        console.warn("No location data found, using default NYC location");
        // Default to NYC
        passengerLocation = [-73.9857, 40.7484];
    }
    
    console.log("Map center location:", passengerLocation);
    
    // Initialize the map
    map = new atlas.Map('passengerMap', {
        center: passengerLocation,
        zoom: 15,  // Closer zoom for pedestrian view
        style: 'road',
        authOptions: {
            authType: 'subscriptionKey',
            subscriptionKey: AZURE_MAPS_KEY
        }
    });
    
    // Wait until the map resources are ready
    map.events.add('ready', function() {
        console.log("Map is ready");
        
        // Create a single data source for all features
        datasource = new atlas.source.DataSource();
        map.sources.add(datasource);
        
        // Add all the GeoJSON data to the data source
        const allFeatures = {
            type: 'FeatureCollection',
            features: []
        };
        
        // Add hexagons
        if (hexagonGeoJson && hexagonGeoJson.features) {
            console.log(`Adding ${hexagonGeoJson.features.length} hexagons`);
            allFeatures.features = allFeatures.features.concat(hexagonGeoJson.features);
        }
        
        // Add drivers
        if (driverGeoJson && driverGeoJson.features) {
            console.log(`Adding ${driverGeoJson.features.length} drivers`);
            allFeatures.features = allFeatures.features.concat(driverGeoJson.features);
        }
        
        // Add passenger
        if (passengerGeoJson && passengerGeoJson.features) {
            console.log(`Adding passenger`);
            allFeatures.features = allFeatures.features.concat(passengerGeoJson.features);
        }
        
        // Add pickup points
        if (pickupGeoJson && pickupGeoJson.features) {
            console.log(`Adding ${pickupGeoJson.features.length} pickup points`);
            allFeatures.features = allFeatures.features.concat(pickupGeoJson.features);
        }
        
        // Add walking route
        if (walkingRouteGeoJson && walkingRouteGeoJson.features && walkingRouteGeoJson.features.length > 0) {
            console.log(`Adding ${walkingRouteGeoJson.features.length} walking routes`);
            allFeatures.features = allFeatures.features.concat(walkingRouteGeoJson.features);
        }
        
        // Add all features to the data source
        datasource.add(allFeatures);
        
        // Add layers for different feature types
        
        // Hexagon fill layer
        map.layers.add(new atlas.layer.PolygonLayer(datasource, null, {
            filter: ['has', 'hex_id'],
            fillColor: ['get', 'color'],
            fillOpacity: 0.5
        }));
        
        // Hexagon outline layer
        map.layers.add(new atlas.layer.LineLayer(datasource, null, {
            filter: ['has', 'hex_id'],
            strokeColor: ['get', 'color'],
            strokeWidth: 1
        }));
        
        // Walking route layer - add a background layer first
        map.layers.add(new atlas.layer.LineLayer(datasource, null, {
            filter: ['all', ['==', ['geometry-type'], 'LineString'], ['has', 'distance_km']],
            strokeColor: 'white',
            strokeWidth: 5,
            strokeOpacity: 0.5
        }));
        
        // Walking route layer - add the colored route on top
        map.layers.add(new atlas.layer.LineLayer(datasource, null, {
            filter: ['all', ['==', ['geometry-type'], 'LineString'], ['has', 'distance_km']],
            strokeColor: ['get', 'color'],
            strokeWidth: 3
        }));
        
        // Driver layer
        map.layers.add(new atlas.layer.BubbleLayer(datasource, null, {
            filter: ['has', 'driver_id'],
            color: ['get', 'color'],
            radius: 6,
            strokeWidth: 0
        }));
        
        // Passenger layer
        map.layers.add(new atlas.layer.BubbleLayer(datasource, null, {
            filter: ['has', 'passenger_id'],
            color: ['get', 'color'],
            radius: 8,
            strokeColor: 'black',
            strokeWidth: 1
        }));
        
        // Pickup point layer
        map.layers.add(new atlas.layer.BubbleLayer(datasource, null, {
            filter: ['has', 'estimated_time'],
            color: 'purple',
            radius: 6,
            strokeColor: 'white',
            strokeWidth: 1
        }));
        
        // Create a popup
        popup = new atlas.Popup({
            pixelOffset: [0, -10],
            closeButton: false
        });
        
        // Add a hover event to the map
        map.events.add('mousemove', function(e) {
            // Get the features under the mouse
            const features = map.layers.getRenderedShapes(e.position);
            
            if (features.length > 0) {
                let popupContent = null;
                
                // Check for hexagon
                const hexagon = features.find(f => f.properties && f.properties.hex_id);
                if (hexagon) {
                    const props = hexagon.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>Hex ID:</b> ${props.hex_id}<br>
                            <b>Demand:</b> ${props.demand_level.charAt(0).toUpperCase() + props.demand_level.slice(1)}<br>
                            <b>Waiting Passengers:</b> ${props.current_passenger_count}
                        </div>
                    `;
                }
                
                // Check for pickup point
                const pickup = features.find(f => f.properties && f.properties.estimated_time && !f.properties.driver_id);
                if (pickup && !popupContent) {
                    const props = pickup.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>${props.name}</b><br>
                            Type: ${props.type}<br>
                            Est. Walking Time: ${props.estimated_time} min<br>
                            ${props.address ? `Address: ${props.address}` : ''}
                        </div>
                    `;
                }
                
                // Check for walking route
                const route = features.find(f => f.properties && f.properties.distance_km);
                if (route && !popupContent) {
                    const props = route.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>${props.name}</b><br>
                            Est. Walking Time: ${props.estimated_time} min<br>
                            Distance: ${props.distance_km} km
                        </div>
                    `;
                }
                
                // Check for driver
                const driver = features.find(f => f.properties && f.properties.driver_id);
                if (driver && !popupContent) {
                    const props = driver.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>Driver ID:</b> ${props.driver_id}<br>
                            <b>Status:</b> ${props.status.charAt(0).toUpperCase() + props.status.slice(1)}
                        </div>
                    `;
                }
                
                // Check for passenger
                const passenger = features.find(f => f.properties && f.properties.passenger_id);
                if (passenger && !popupContent) {
                    const props = passenger.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>Passenger ID:</b> ${props.passenger_id}<br>
                            <b>Status:</b> Looking for pickup
                        </div>
                    `;
                }
                
                // If we have content, show the popup
                if (popupContent) {
                    popup.setOptions({
                        content: popupContent,
                        position: e.position
                    });
                    popup.open(map);
                } else {
                    popup.close();
                }
            } else {
                popup.close();
            }
        });
        
        // Populate pickup list
        populatePickupList();
        
        console.log("Map setup complete");
    });
}

// Populate the pickup list in the sidebar
function populatePickupList() {
    try {
        const container = document.getElementById('pickupListContainer');
        if (!container) return;
        
        if (!pickupGeoJson || !pickupGeoJson.features || pickupGeoJson.features.length === 0) {
            // No pickup points available - don't show any message
            container.innerHTML = '';
            return;
        }
        
        let html = '';
        
        pickupGeoJson.features.forEach((feature, index) => {
            const props = feature.properties;
            html += `
                <div class="pickup-item">
                    <h4>${props.name}</h4>
                    <p><strong>Type:</strong> ${props.type}</p>
                    <p><strong>Est. Walking Time:</strong> ${props.estimated_time} min</p>
                    ${props.address ? `<p><strong>Address:</strong> ${props.address}</p>` : ''}
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error("Error populating pickup list:", error);
    }
}

// Request a ride from a pickup point
function requestRide(index) {
    try {
        alert(`You've requested a ride from pickup point ${index+1}. A driver will be notified in a real app.`);
        // In a real app, you would send this back to the server and update the UI
    } catch (error) {
        console.error("Error requesting ride:", error);
    }
} 