// Global variables
let map;
let datasource;
let popup;

// This function will be called after data is loaded
function initializeDriverMap() {
    console.log("Initializing driver map with data:", {
        driverId,
        isNearHighDemand,
        mapKey: AZURE_MAPS_KEY ? "Available" : "Missing",
        hexagonFeatures: hexagonGeoJson?.features?.length || 0,
        driverFeatures: driverGeoJson?.features?.length || 0,
        pickupFeatures: pickupGeoJson?.features?.length || 0,
        routeFeatures: routeGeoJson?.features?.length || 0
    });
    
    // Find the driver's position to center the map
    let driverLocation = null;
    let foundDriver = false;
    
    if (driverGeoJson && driverGeoJson.features) {
        for (const feature of driverGeoJson.features) {
            if (feature.properties.driver_id === driverId) {
                driverLocation = feature.geometry.coordinates;
                foundDriver = true;
                console.log("Found driver in GeoJSON with ID:", driverId);
                break;
            }
        }
        
        // If we didn't find the specific driver but there are other drivers, use the first one's location
        if (!foundDriver && driverGeoJson.features.length > 0) {
            driverLocation = driverGeoJson.features[0].geometry.coordinates;
            console.log("Using first driver's location as fallback");
        }
    }
    
    // If no driver location found, check if we have hexagons to center on
    if (!driverLocation && hexagonGeoJson && hexagonGeoJson.features && hexagonGeoJson.features.length > 0) {
        // Get the center of the first hexagon
        const firstHexagon = hexagonGeoJson.features[0];
        const coords = firstHexagon.geometry.coordinates[0];
        
        // Calculate the center of the hexagon
        let sumLng = 0, sumLat = 0;
        for (const point of coords) {
            sumLng += point[0];
            sumLat += point[1];
        }
        driverLocation = [sumLng / coords.length, sumLat / coords.length];
        console.log("Using hexagon center as fallback location");
    }
    
    // If still no location, use a default location in NYC
    if (!driverLocation) {
        console.warn("No location data found, using default NYC location");
        // Default to NYC
        driverLocation = [-73.9857, 40.7484];
    }
    
    console.log("Map center location:", driverLocation);
    
    // Initialize the map
    map = new atlas.Map('driverMap', {
        center: driverLocation,
        zoom: 13,
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
        
        // Add pickup points if near high demand
        if (isNearHighDemand && pickupGeoJson && pickupGeoJson.features) {
            console.log(`Adding ${pickupGeoJson.features.length} pickup points`);
            allFeatures.features = allFeatures.features.concat(pickupGeoJson.features);
        }
        
        // Add routes if near high demand
        if (isNearHighDemand && routeGeoJson && routeGeoJson.features) {
            console.log(`Adding ${routeGeoJson.features.length} routes`);
            allFeatures.features = allFeatures.features.concat(routeGeoJson.features);
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
        
        // Route layer
        map.layers.add(new atlas.layer.LineLayer(datasource, null, {
            filter: ['has', 'distance_km'],
            strokeColor: ['get', 'color'],
            strokeWidth: 3,
            strokeDashArray: [1, 2]
        }));
        
        // Add a second route layer with a wider stroke to create a halo effect
        map.layers.add(new atlas.layer.LineLayer(datasource, null, {
            filter: ['has', 'distance_km'],
            strokeColor: 'white',
            strokeWidth: 5,
            strokeOpacity: 0.5,
            strokeDashArray: [1, 2]
        }, {
            // Add this layer before the colored route layer
            before: map.layers.getLayers()[map.layers.getLayers().length - 1].getId()
        }));
        
        // Driver layer (all drivers except current)
        map.layers.add(new atlas.layer.BubbleLayer(datasource, null, {
            filter: ['all', 
                ['has', 'driver_id'],
                ['!=', ['get', 'driver_id'], driverId]
            ],
            color: ['get', 'color'],
            radius: 6,
            strokeWidth: 0
        }));
        
        // Current driver layer
        map.layers.add(new atlas.layer.BubbleLayer(datasource, null, {
            filter: ['==', ['get', 'driver_id'], driverId],
            color: 'yellow',
            radius: 8,
            strokeColor: 'black',
            strokeWidth: 1
        }));
        
        // Pickup point layer
        if (isNearHighDemand) {
            map.layers.add(new atlas.layer.BubbleLayer(datasource, null, {
                filter: ['has', 'passengers'],
                color: 'purple',
                radius: 6,
                strokeColor: 'white',
                strokeWidth: 1
            }));
        }
        
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
                const pickup = features.find(f => f.properties && f.properties.passengers);
                if (pickup && !popupContent) {
                    const props = pickup.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>${props.name}</b><br>
                            Type: ${props.type}<br>
                            Est. Time: ${props.estimated_time} min<br>
                            Passengers: ${props.passengers}
                        </div>
                    `;
                }
                
                // Check for route
                const route = features.find(f => f.properties && f.properties.distance_km);
                if (route && !popupContent) {
                    const props = route.properties;
                    popupContent = `
                        <div style="padding: 10px;">
                            <b>${props.name}</b><br>
                            Est. Time: ${props.estimated_time} min<br>
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
                            <b>Status:</b> ${props.status}
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
        
        // Update UI based on high demand proximity
        updateDriverUI();
        
        console.log("Map setup complete");
    });
}

// Update driver UI based on high demand proximity
function updateDriverUI() {
    try {
        if (isNearHighDemand) {
            $('#driverStatus').html('<span class="badge bg-success">Near High Demand Area</span>');
            $('#pickupOptions').show();
        } else {
            $('#driverStatus').html('<span class="badge bg-warning">In Low Demand Area</span>');
            $('#pickupOptions').hide();
        }
        
        // Populate pickup list
        populatePickupList();
    } catch (error) {
        console.error("Error updating driver UI:", error);
    }
}

// Populate the pickup list in the sidebar
function populatePickupList() {
    try {
        if (!isNearHighDemand || !pickupGeoJson || !pickupGeoJson.features) return;
        
        const container = document.getElementById('pickupListContainer');
        if (!container) return;
        
        let html = '';
        
        pickupGeoJson.features.forEach((feature, index) => {
            const props = feature.properties;
            html += `
                <div class="pickup-item">
                    <h4>${props.name}</h4>
                    <p><strong>Type:</strong> ${props.type}</p>
                    <p><strong>Est. Time:</strong> ${props.estimated_time} min</p>
                    <p><strong>Waiting Passengers:</strong> ${props.passengers}</p>
                    <button class="btn btn-sm btn-primary mt-2" onclick="acceptPickup(${index})">Accept</button>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error("Error populating pickup list:", error);
    }
}

// Accept a pickup
function acceptPickup(index) {
    try {
        // Get the pickup ID from the pickup GeoJSON
        const pickupId = pickupGeoJson.features[index].properties.id;
        
        // Redirect to the driver_connect endpoint with the accept_pickup action
        window.location.href = `/driver_connect?action=accept_pickup&driver_id=${driverId}&pickup_id=${pickupId}`;
    } catch (error) {
        console.error("Error accepting pickup:", error);
    }
} 