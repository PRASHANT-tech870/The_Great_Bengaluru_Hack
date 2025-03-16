from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import h3
import json
import time
import random
import uuid
import numpy as np
import requests
import sqlite3
from data_generator import (
    generate_hexagons, 
    initialize_demand_patterns, 
    generate_time_slots, 
    get_demand_color,
    generate_drivers,
    simulate_driver_responses
)

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'  # Required for session
# Azure Maps API key
AZURE_MAPS_KEY = "G7xUTF4IzMFbdQbLtbpNH8xIosAvM7VUnmgmJMFKn4dwT7aAURDCJQQJ99BCACYeBjF1GyYrAAAgAZMP1rMG"

# Add headers to allow iframe embedding
@app.after_request
def add_header(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

# Function to get route from Azure Maps Routing API
def get_azure_route(start_lng, start_lat, end_lng, end_lat, mode="car"):
    """
    Get a route from Azure Maps Routing API
    Returns a GeoJSON LineString with the route coordinates
    
    Parameters:
    - start_lng, start_lat: Starting coordinates
    - end_lng, end_lat: Ending coordinates
    - mode: Travel mode (car, pedestrian)
    """
    try:
        # Azure Maps Routing API endpoint
        url = f"https://atlas.microsoft.com/route/directions/json?api-version=1.0&subscription-key={AZURE_MAPS_KEY}"
        
        # Request parameters
        params = {
            "query": f"{start_lat},{start_lng}:{end_lat},{end_lng}",
            "routeType": "fastest",
            "traffic": "true",
            "travelMode": mode,
            "computeTravelTimeFor": "all",
            "instructionsType": "text",
            "routeRepresentation": "polyline"
        }
        
        # Make the request
        response = requests.get(url, params=params)
        data = response.json()
        
        # Extract route points from the response
        if 'routes' in data and len(data['routes']) > 0:
            # Get the first route
            route = data['routes'][0]
            
            # Extract the points from the route's legs
            coordinates = []
            for leg in route['legs']:
                for point in leg['points']:
                    coordinates.append([point['longitude'], point['latitude']])
            
            # Get travel time and distance
            travel_time_minutes = int(route['summary']['travelTimeInSeconds'] / 60)
            distance_km = round(route['summary']['lengthInMeters'] / 1000, 1)
            
            return {
                "coordinates": coordinates,
                "travel_time_minutes": travel_time_minutes,
                "distance_km": distance_km
            }
        else:
            # If no route found, return a straight line as fallback
            return {
                "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
                "travel_time_minutes": int(((end_lat - start_lat)**2 + (end_lng - start_lng)**2)**0.5 / 0.008),
                "distance_km": round(((end_lat - start_lat)**2 + (end_lng - start_lng)**2)**0.5 * 111, 1)
            }
    except Exception as e:
        print(f"Error getting route from Azure Maps: {e}")
        # Return a straight line as fallback
        return {
            "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
            "travel_time_minutes": int(((end_lat - start_lat)**2 + (end_lng - start_lng)**2)**0.5 / 0.008),
            "distance_km": round(((end_lat - start_lat)**2 + (end_lng - start_lng)**2)**0.5 * 111, 1)
        }

# Function to get POIs from Azure Maps Search API
def get_azure_pois(lat, lng, radius=500, limit=3):
    """
    Get Points of Interest (POIs) from Azure Maps Search API
    Returns a list of POIs with name, type, lat, lng, and address
    
    Parameters:
    - lat, lng: Center coordinates
    - radius: Search radius in meters
    - limit: Maximum number of results to return
    """
    try:
        # Azure Maps Search API endpoint
        url = f"https://atlas.microsoft.com/search/poi/category/json?api-version=1.0&subscription-key={AZURE_MAPS_KEY}&query=restaurant,cafe,store&limit={limit}&lat={lat}&lon={lng}&radius={radius}"
        
        response = requests.get(url)
        data = response.json()
        
        pois = []
        if 'results' in data:
            for poi in data['results']:
                poi_data = {
                    'name': poi.get('poi', {}).get('name', f"POI {len(pois)+1}"),
                    'type': poi.get('poi', {}).get('categories', ['Landmark'])[0],
                    'lat': poi.get('position', {}).get('lat', lat),
                    'lng': poi.get('position', {}).get('lon', lng),
                    'address': poi.get('address', {}).get('freeformAddress', '')
                }
                pois.append(poi_data)
        
        return pois
    except Exception as e:
        print(f"Error getting POIs from Azure Maps: {e}")
        return []

# Function to get driver data from SQLite database
def get_driver_data(driver_id):
    """
    Get driver data from the SQLite database
    Returns a dictionary with driver information
    
    Parameters:
    - driver_id: The ID of the driver to retrieve
    """
    try:
        conn = sqlite3.connect('driver_data.db')
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM drivers WHERE driver_id = ?
        ''', (driver_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'driver_id': row['driver_id'],
                'no_of_peak_hrs_rides': row['no_of_peak_hrs_rides'],
                'trust_score': row['trust_score'],
                'commit_points': row['commit_points'],
                'no_of_cancellations': row['no_of_cancellations'],
                'distance_traveled': row['distance_traveled']
            }
        else:
            return None
    except Exception as e:
        print(f"Error getting driver data from database: {e}")
        return None

# Function to update driver data in the SQLite database
def update_driver_data(driver_id, field, increment=1, distance=0):
    """
    Update driver data in the SQLite database
    
    Parameters:
    - driver_id: The ID of the driver to update
    - field: The field to update (no_of_peak_hrs_rides or no_of_cancellations)
    - increment: The amount to increment the field by (default: 1)
    - distance: The distance to add to distance_traveled (default: 0)
    """
    try:
        conn = sqlite3.connect('driver_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if driver exists
        cursor.execute('SELECT * FROM drivers WHERE driver_id = ?', (driver_id,))
        driver = cursor.fetchone()
        
        if driver:
            # Update the specified field
            cursor.execute(f'''
            UPDATE drivers SET {field} = {field} + ? WHERE driver_id = ?
            ''', (increment, driver_id))
            
            # Get current driver data for calculations
            current_trust = driver['trust_score']
            peak_rides = driver['no_of_peak_hrs_rides'] + (increment if field == 'no_of_peak_hrs_rides' else 0)
            cancellations = driver['no_of_cancellations'] + (increment if field == 'no_of_cancellations' else 0)
            current_distance = driver['distance_traveled'] + distance
            
            # Constants for calculations
            alpha = 1.5
            beta = 3
            w1 = 40
            w2 = 60
            max_distance = 5  # in km
            
            # Calculate new trust score using the formula
            # new_trust = current_trust + (alpha * peak_rides) - (beta * cancellations)
            new_trust = current_trust + (alpha * increment if field == 'no_of_peak_hrs_rides' else 0) - (beta * increment if field == 'no_of_cancellations' else 0)
            
            # Ensure trust score stays within 0-100 range
            new_trust = max(0, min(100, new_trust))
            
            # Update trust score
            cursor.execute('''
            UPDATE drivers SET trust_score = ? WHERE driver_id = ?
            ''', (new_trust, driver_id))
            
            # Calculate commit points using the formula
            # commit_points = w1 * (trust_score / 100) + w2 * (distance_traveled / max_distance)
            commit_points = w1 * (new_trust / 100) + w2 * (min(current_distance, max_distance) / max_distance)
            
            # Update commit points
            cursor.execute('''
            UPDATE drivers SET commit_points = ? WHERE driver_id = ?
            ''', (commit_points, driver_id))
            
            # Update distance_traveled if provided
            if distance > 0:
                cursor.execute('''
                UPDATE drivers SET distance_traveled = distance_traveled + ? WHERE driver_id = ?
                ''', (distance, driver_id))
            
            conn.commit()
            conn.close()
            return True
        else:
            conn.close()
            return False
    except Exception as e:
        print(f"Error updating driver data in database: {e}")
        return False

# Global variables to store state (replacing Streamlit session state)
global_state = {
    'drivers': [],
    'notifications_sent': False,
    'accepted_count': 0,
    'passenger_counts': {},
    'current_time_slot': None
}

@app.route('/')
def index():
    # Generate time slots
    time_slots = generate_time_slots()
    
    return render_template('index.html', 
                          time_slots=time_slots,
                          azure_maps_key=AZURE_MAPS_KEY)

@app.route('/get_data', methods=['POST', 'GET'])
def get_data():
    # For POST requests from the main dashboard
    if request.method == 'POST':
        selected_time_slot = request.json.get('time_slot')
        
        # Generate hexagons
        hexagons = generate_hexagons()
        
        # Initialize demand patterns and passenger counts if not already done
        if not global_state['passenger_counts']:
            demand_patterns, passenger_counts = initialize_demand_patterns(tuple(hexagons))
            global_state['passenger_counts'] = passenger_counts
            global_state['demand_patterns'] = demand_patterns
        else:
            demand_patterns = global_state['demand_patterns']
            passenger_counts = global_state['passenger_counts']
        
        # Generate drivers if time slot changes or if they don't exist yet
        if global_state['current_time_slot'] != selected_time_slot:
            global_state['current_time_slot'] = selected_time_slot
            global_state['drivers'] = generate_drivers(hexagons, demand_patterns, selected_time_slot)
            global_state['notifications_sent'] = False
            global_state['accepted_count'] = 0
        
        # Prepare data for map
        hexagon_data = []
        for hex_id in hexagons:
            # Get the boundary of the hexagon
            hex_boundary = h3.cell_to_boundary(hex_id)
            # Convert to format expected by Azure Maps (lng, lat)
            hex_boundary = [[lng, lat] for lat, lng in hex_boundary]
            
            # Get demand level and passenger count for this hexagon at the selected time slot
            demand_level = demand_patterns[selected_time_slot][hex_id]
            
            # Store both original and current passenger counts
            original_passenger_count = passenger_counts[selected_time_slot][hex_id]
            
            # Use global state passenger counts if notifications have been sent
            if global_state['notifications_sent'] and hex_id in global_state['passenger_counts'][selected_time_slot]:
                current_passenger_count = global_state['passenger_counts'][selected_time_slot][hex_id]
            else:
                current_passenger_count = original_passenger_count
            
            color = get_demand_color(demand_level)
            
            hexagon_data.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [hex_boundary]
                },
                "properties": {
                    "hex_id": hex_id,
                    "demand_level": demand_level,
                    "original_passenger_count": original_passenger_count,
                    "current_passenger_count": current_passenger_count,
                    "color": color
                }
            })
        
        # Prepare driver data for map
        driver_data = []
        for driver in global_state['drivers']:
            if driver['status'] in ['available', 'notified']:
                icon_color = 'blue' if driver['status'] == 'available' else 'orange'
                driver_data.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [driver['lng'], driver['lat']]
                    },
                    "properties": {
                        "driver_id": driver['id'],
                        "status": driver['status'],
                        "color": icon_color
                    }
                })
        
        # Calculate statistics for the selected time slot
        demand_counts = {
            'high': sum(1 for v in demand_patterns[selected_time_slot].values() if v == 'high'),
            'low': sum(1 for v in demand_patterns[selected_time_slot].values() if v == 'low')
        }
        
        # Use global state passenger counts if notifications have been sent
        if global_state['notifications_sent']:
            total_passengers = sum(global_state['passenger_counts'][selected_time_slot].values())
        else:
            total_passengers = sum(passenger_counts[selected_time_slot].values())
        
        available_drivers = sum(1 for d in global_state['drivers'] if d['status'] == 'available')
        notified_drivers = sum(1 for d in global_state['drivers'] if d['status'] == 'notified')
        
        stats = {
            'high_demand_areas': demand_counts['high'],
            'low_demand_areas': demand_counts['low'],
            'available_drivers': available_drivers,
            'total_passengers': total_passengers,
            'avg_passengers_per_hexagon': round(total_passengers / len(hexagons), 1),
            'notifications_sent': global_state['notifications_sent'],
            'notified_drivers': notified_drivers,
            'accepted_count': global_state['accepted_count']
        }
        
        return jsonify({
            'hexagon_geojson': {
                "type": "FeatureCollection",
                "features": hexagon_data
            },
            'driver_geojson': {
                "type": "FeatureCollection",
                "features": driver_data
            },
            'stats': stats
        })
    
    # For GET requests from the driver map
    else:
        # Get driver ID from query parameters or use the one from session
        driver_id = request.args.get('driver_id', '')
        time_slot = global_state.get('current_time_slot') or generate_time_slots()[0]
        
        # Find the driver in the global state
        driver = None
        for d in global_state.get('drivers', []):
            if d['id'] == driver_id:
                driver = d
                break
        
        # If driver not found, return empty data
        if not driver:
            return jsonify({
                'azure_maps_key': AZURE_MAPS_KEY,
                'hexagon_geojson': {"type": "FeatureCollection", "features": []},
                'driver_geojson': {"type": "FeatureCollection", "features": []},
                'driver_id': driver_id,
                'is_near_high_demand': False,
                'pickup_geojson': {"type": "FeatureCollection", "features": []},
                'route_geojson': {"type": "FeatureCollection", "features": []}
            })
        
        # Generate hexagons
        hexagons = generate_hexagons()
        
        # Prepare hexagon data
        hexagon_data = []
        for hex_id in hexagons:
            hex_boundary = h3.cell_to_boundary(hex_id)
            hex_boundary = [[lng, lat] for lat, lng in hex_boundary]
            
            demand_level = global_state['demand_patterns'][time_slot][hex_id]
            original_passenger_count = global_state['passenger_counts'][time_slot][hex_id]
            
            if global_state.get('notifications_sent') and hex_id in global_state['passenger_counts'][time_slot]:
                current_passenger_count = global_state['passenger_counts'][time_slot][hex_id]
            else:
                current_passenger_count = original_passenger_count
            
            color = get_demand_color(demand_level)
            
            hexagon_data.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [hex_boundary]
                },
                "properties": {
                    "hex_id": hex_id,
                    "demand_level": demand_level,
                    "original_passenger_count": original_passenger_count,
                    "current_passenger_count": current_passenger_count,
                    "color": color
                }
            })
        
        # Prepare driver data
        driver_data = []
        for d in global_state.get('drivers', []):
            if d['status'] in ['available', 'notified', 'connected']:
                if d['status'] == 'connected':
                    icon_color = 'yellow'
                elif d['status'] == 'available':
                    icon_color = 'blue'
                else:  # notified
                    icon_color = 'orange'
                
                driver_data.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [d['lng'], d['lat']]
                    },
                    "properties": {
                        "driver_id": d['id'],
                        "status": d['status'],
                        "color": icon_color
                    }
                })
        
        # Check if driver is near high demand
        is_near_high_demand = False
        pickup_points = []
        routes = []
        
        if driver.get('target_hex'):
            target_hex = driver['target_hex']
            demand_level = global_state['demand_patterns'][time_slot].get(target_hex)
            is_near_high_demand = demand_level == 'high'
            
            if is_near_high_demand:
                # Generate pickup points and routes (similar to driver_connect)
                num_pickup_points = random.randint(2, 3)
                center_lat, center_lng = h3.cell_to_latlng(target_hex)
                boundary = h3.cell_to_boundary(target_hex)
                
                for i in range(num_pickup_points):
                    if i == 0:
                        distance = random.uniform(0.0001, 0.0005)
                        angle = random.uniform(0, 2 * np.pi)
                        pickup_lat = center_lat + distance * np.cos(angle)
                        pickup_lng = center_lng + distance * np.sin(angle)
                        point_type = "Central Intersection"
                    elif i == 1:
                        vertex_idx = random.randint(0, len(boundary) - 1)
                        vertex = boundary[vertex_idx]
                        pickup_lat = vertex[0] * 0.9 + center_lat * 0.1
                        pickup_lng = vertex[1] * 0.9 + center_lng * 0.1
                        point_type = "Street Corner"
                    else:
                        weights = [random.random() for _ in range(len(boundary))]
                        weight_sum = sum(weights)
                        weights = [w/weight_sum for w in weights]
                        
                        pickup_lat = sum(v[0] * w for v, w in zip(boundary, weights))
                        pickup_lng = sum(v[1] * w for v, w in zip(boundary, weights))
                        point_type = "Landmark"
                    
                    pickup_name = f"Pickup Point {i+1} ({point_type})"
                    
                    driver_lat, driver_lng = driver['lat'], driver['lng']
                    distance_degrees = ((pickup_lat - driver_lat)**2 + (pickup_lng - driver_lng)**2)**0.5
                    estimated_minutes = int(distance_degrees / 0.008)
                    
                    pickup_points.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [pickup_lng, pickup_lat]
                        },
                        "properties": {
                            "name": pickup_name,
                            "type": point_type,
                            "estimated_time": estimated_minutes,
                            "passengers": random.randint(5, 15)
                        }
                    })
                    
                    # Get route from Azure Maps Routing API
                    route_data = get_azure_route(driver_lng, driver_lat, pickup_lng, pickup_lat)
                    
                    routes.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": route_data["coordinates"]
                        },
                        "properties": {
                            "name": f"Route to {pickup_name}",
                            "estimated_time": route_data["travel_time_minutes"],
                            "distance_km": route_data["distance_km"],
                            "color": ["#FF5733", "#33FF57", "#3357FF"][i % 3]
                        }
                    })
        
        # Generate pickup points and routes if near high demand
        pickup_points = []
        routes = []
        
        if is_near_high_demand and driver.get('target_hex'):
            # Generate 2-3 pickup points
            num_pickup_points = random.randint(2, 3)
            
            # Get the center of the hexagon
            center_lat, center_lng = h3.cell_to_latlng(driver['target_hex'])
            
            # Get the boundary of the hexagon
            boundary = h3.cell_to_boundary(driver['target_hex'])
            
            # Driver coordinates
            driver_lat = driver['lat']
            driver_lng = driver['lng']
            
            # Generate pickup points
            session_pickup_points = []  # For storing in session
            
            for i in range(num_pickup_points):
                if i == 0:
                    # First point near center
                    distance = random.uniform(0.0005, 0.001)
                    angle = random.uniform(0, 2 * np.pi)
                    pickup_lat = center_lat + distance * np.cos(angle)
                    pickup_lng = center_lng + distance * np.sin(angle)
                    pickup_name = "Central Pickup"
                    point_type = "Central Intersection"
                elif i == 1:
                    # Second point near a random vertex
                    vertex_idx = random.randint(0, len(boundary) - 1)
                    vertex = boundary[vertex_idx]
                    pickup_lat = vertex[0] * 0.9 + center_lat * 0.1
                    pickup_lng = vertex[1] * 0.9 + center_lng * 0.1
                    pickup_name = "Corner Pickup"
                    point_type = "Street Corner"
                else:
                    # Third point at a random position
                    weights = [random.random() for _ in range(len(boundary))]
                    weight_sum = sum(weights)
                    weights = [w/weight_sum for w in weights]
                    
                    pickup_lat = sum(v[0] * w for v, w in zip(boundary, weights))
                    pickup_lng = sum(v[1] * w for v, w in zip(boundary, weights))
                    pickup_name = "Landmark Pickup"
                    point_type = "Landmark"
                
                # Calculate estimated time (roughly 50 km/h = 0.008 degrees per minute)
                distance_degrees = ((pickup_lat - driver_lat)**2 + (pickup_lng - driver_lng)**2)**0.5
                estimated_minutes = int(distance_degrees / 0.008)
                
                # Store pickup point for session
                session_pickup_points.append({
                    'id': str(uuid.uuid4())[:8],
                    'lat': pickup_lat,
                    'lng': pickup_lng,
                    'name': pickup_name,
                    'type': point_type,
                    'estimated_time': estimated_minutes
                })
                
                pickup_points.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [pickup_lng, pickup_lat]
                    },
                    "properties": {
                        "id": str(uuid.uuid4())[:8],
                        "name": pickup_name,
                        "type": point_type,
                        "estimated_time": estimated_minutes,
                        "passengers": random.randint(5, 15)
                    }
                })
                
                # Get route from Azure Maps Routing API
                route_data = get_azure_route(driver_lng, driver_lat, pickup_lng, pickup_lat)
                
                routes.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": route_data["coordinates"]
                    },
                    "properties": {
                        "id": str(uuid.uuid4())[:8],
                        "name": f"Route to {pickup_name}",
                        "estimated_time": route_data["travel_time_minutes"],
                        "distance_km": route_data["distance_km"],
                        "color": ["#FF5733", "#33FF57", "#3357FF"][i % 3]  # Different colors for routes
                    }
                })
            
            # Store pickup points in session
            session['session_pickup_points'] = session_pickup_points
        
        return jsonify({
            'azure_maps_key': AZURE_MAPS_KEY,
            'hexagon_geojson': {
                "type": "FeatureCollection",
                "features": hexagon_data
            },
            'driver_geojson': {
                "type": "FeatureCollection",
                "features": driver_data
            },
            'driver_id': driver_id,
            'is_near_high_demand': is_near_high_demand,
            'pickup_geojson': {
                "type": "FeatureCollection",
                "features": pickup_points
            },
            'route_geojson': {
                "type": "FeatureCollection",
                "features": routes
            }
        })

@app.route('/send_notifications', methods=['POST'])
def send_notifications():
    # Mark all available drivers as notified
    for driver in global_state['drivers']:
        if driver['status'] == 'available':
            driver['status'] = 'notified'
    
    global_state['notifications_sent'] = True
    
    return jsonify({'success': True, 'message': 'Notifications sent to all available drivers!'})

@app.route('/simulate_responses', methods=['POST'])
def simulate_responses():
    selected_time_slot = request.json.get('time_slot')
    
    # Simulate driver responses
    accepted_count = simulate_driver_responses(
        global_state['drivers'], 
        global_state['passenger_counts'], 
        selected_time_slot
    )
    global_state['accepted_count'] = accepted_count
    
    # Reduce passenger counts in high demand areas
    for hex_id, demand_level in global_state['demand_patterns'][selected_time_slot].items():
        if demand_level == 'high' and hex_id in global_state['passenger_counts'][selected_time_slot]:
            # Reduce by number of accepted drivers (up to the current count)
            current_count = global_state['passenger_counts'][selected_time_slot][hex_id]
            reduction = min(accepted_count, current_count)
            global_state['passenger_counts'][selected_time_slot][hex_id] = current_count - reduction
    
    return jsonify({
        'success': True, 
        'message': f"{accepted_count} drivers accepted ride requests!"
    })

@app.route('/driver_connect', methods=['GET'])
def driver_connect():
    # Get current time slot (use the global state or default to first time slot)
    time_slot = global_state.get('current_time_slot') or generate_time_slots()[0]
    
    # Get action parameter (if any)
    action = request.args.get('action', None)
    driver_id = request.args.get('driver_id', None)
    pickup_id = request.args.get('pickup_id', None)
    
    # If action is accept_pickup, update driver data and return ride status page
    if action == 'accept_pickup' and driver_id and pickup_id:
        # Get pickup point from session
        session_pickup_points = session.get('session_pickup_points', [])
        pickup_point = next((p for p in session_pickup_points if p.get('id') == pickup_id), None)
        
        if pickup_point:
            # Calculate distance for this ride (from driver to pickup)
            driver_location = session.get('driver_location', None)
            if driver_location and 'lat' in driver_location and 'lng' in driver_location:
                # Calculate distance using Haversine formula
                from math import radians, sin, cos, sqrt, atan2
                
                def haversine(lat1, lon1, lat2, lon2):
                    # Convert latitude and longitude from degrees to radians
                    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                    
                    # Haversine formula
                    dlon = lon2 - lon1
                    dlat = lat2 - lat1
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * atan2(sqrt(a), sqrt(1-a))
                    distance = 6371 * c  # Radius of Earth in kilometers
                    
                    return distance
                
                distance = haversine(
                    driver_location['lat'], 
                    driver_location['lng'], 
                    pickup_point['lat'], 
                    pickup_point['lng']
                )
                
                # Redirect to ride status page with the calculated distance
                return redirect(url_for('ride_status', driver_id=driver_id, outcome='completed', distance=distance))
        
        # If pickup point not found, redirect to driver map
        return redirect(url_for('driver_map'))
    
    # Generate hexagons if not already done
    hexagons = generate_hexagons()
    
    # Initialize demand patterns if not already done
    if not global_state.get('demand_patterns'):
        demand_patterns, passenger_counts = initialize_demand_patterns(tuple(hexagons))
        global_state['passenger_counts'] = passenger_counts
        global_state['demand_patterns'] = demand_patterns
    
    # Find high demand hexagons
    high_demand_hexagons = [hex_id for hex_id, level in global_state['demand_patterns'][time_slot].items() 
                           if level == 'high']
    
    # Decide whether to place driver near high demand (70% chance) or in low demand area (30% chance)
    near_high_demand = random.random() < 0.7
    
    driver_location = None
    target_hex = None
    is_near_high_demand = False
    
    if near_high_demand and high_demand_hexagons:
        # Choose a random high demand hexagon
        target_hex = random.choice(high_demand_hexagons)
        
        # Get hexagons in rings 1-2 around the high demand hexagon
        ring1 = h3.grid_ring(target_hex, 1)
        ring2 = h3.grid_ring(target_hex, 2)
        surrounding_hexagons = list(ring1) + list(ring2)
        
        # Choose a random hexagon from the surrounding ones
        if surrounding_hexagons:
            placement_hex = random.choice(surrounding_hexagons)
            
            # Get center coordinates
            center_lat, center_lng = h3.cell_to_latlng(placement_hex)
            
            # Add some randomness to the position within the hexagon
            distance = random.uniform(0.0001, 0.001)
            angle = random.uniform(0, 2 * np.pi)
            
            driver_lat = center_lat + distance * np.cos(angle)
            driver_lng = center_lng + distance * np.sin(angle)
            
            driver_location = {'lat': driver_lat, 'lng': driver_lng}
            is_near_high_demand = True
    else:
        # Choose a random low demand hexagon far from high demand areas
        low_demand_hexagons = [hex_id for hex_id, level in global_state['demand_patterns'][time_slot].items() 
                              if level == 'low']
        
        if low_demand_hexagons and high_demand_hexagons:
            # Get all hexagons that are at least 3 rings away from any high demand hexagon
            far_hexagons = []
            for hex_id in low_demand_hexagons:
                is_far = True
                for high_hex in high_demand_hexagons:
                    # Calculate distance between hexagons
                    if h3.grid_distance(hex_id, high_hex) < 3:
                        is_far = False
                        break
                if is_far:
                    far_hexagons.append(hex_id)
            
            # If we found far hexagons, use them, otherwise use any low demand hexagon
            target_hexagons = far_hexagons if far_hexagons else low_demand_hexagons
            
            # Choose a random hexagon
            placement_hex = random.choice(target_hexagons)
            
            # Get center coordinates
            center_lat, center_lng = h3.cell_to_latlng(placement_hex)
            
            # Add some randomness to the position within the hexagon
            distance = random.uniform(0.0001, 0.001)
            angle = random.uniform(0, 2 * np.pi)
            
            driver_lat = center_lat + distance * np.cos(angle)
            driver_lng = center_lng + distance * np.sin(angle)
            
            driver_location = {'lat': driver_lat, 'lng': driver_lng}
    
    # Store driver location in session for distance calculation
    if driver_location:
        session['driver_location'] = driver_location
    
    # Create a unique driver ID
    driver_id = str(uuid.uuid4())[:8]
    
    # Get driver data from the database
    driver_db_data = get_driver_data(driver_id)
    
    # If driver not found in database, get a random driver from the database
    if not driver_db_data:
        try:
            conn = sqlite3.connect('driver_data.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM drivers ORDER BY RANDOM() LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            
            if row:
                driver_db_data = {
                    'driver_id': row['driver_id'],
                    'no_of_peak_hrs_rides': row['no_of_peak_hrs_rides'],
                    'trust_score': row['trust_score'],
                    'commit_points': row['commit_points'],
                    'no_of_cancellations': row['no_of_cancellations'],
                    'distance_traveled': row['distance_traveled']
                }
                # Update driver_id to match the one from the database
                driver_id = driver_db_data['driver_id']
        except Exception as e:
            print(f"Error getting random driver from database: {e}")
            # Provide default values if database access fails
            driver_db_data = {
                'driver_id': driver_id,
                'no_of_peak_hrs_rides': random.randint(10, 200),
                'trust_score': random.randint(60, 100),
                'commit_points': random.randint(50, 500),
                'no_of_cancellations': random.randint(0, 20),
                'distance_traveled': 0
            }
    
    # Prepare data for map
    hexagon_data = []
    for hex_id in hexagons:
        hex_boundary = h3.cell_to_boundary(hex_id)
        hex_boundary = [[lng, lat] for lat, lng in hex_boundary]
        
        demand_level = global_state['demand_patterns'][time_slot][hex_id]
        original_passenger_count = global_state['passenger_counts'][time_slot][hex_id]
        
        if global_state.get('notifications_sent') and hex_id in global_state['passenger_counts'][time_slot]:
            current_passenger_count = global_state['passenger_counts'][time_slot][hex_id]
        else:
            current_passenger_count = original_passenger_count
        
        color = get_demand_color(demand_level)
        
        hexagon_data.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [hex_boundary]
            },
            "properties": {
                "hex_id": hex_id,
                "demand_level": demand_level,
                "original_passenger_count": original_passenger_count,
                "current_passenger_count": current_passenger_count,
                "color": color
            }
        })
    
    # Prepare driver data for map
    driver_data = []
    if driver_location:
        driver_data.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [driver_location['lng'], driver_location['lat']]
            },
            "properties": {
                "driver_id": driver_id,
                "status": "connected",
                "color": "yellow"
            }
        })
    
    # Add other drivers from global state
    for driver in global_state.get('drivers', []):
        if driver['id'] != driver_id:  # Skip the current driver
            if driver['status'] == 'available':
                icon_color = 'blue'
            elif driver['status'] == 'notified':
                icon_color = 'orange'
            else:  # accepted
                icon_color = 'green'
            
            driver_data.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [driver['lng'], driver['lat']]
                },
                "properties": {
                    "driver_id": driver['id'],
                    "status": driver['status'],
                    "color": icon_color
                }
            })
    
    # Generate pickup points and routes if near high demand
    pickup_points = []
    routes = []
    
    if is_near_high_demand and driver_location and target_hex:
        # Generate 2-3 pickup points
        num_pickup_points = random.randint(2, 3)
        
        # Get the center of the hexagon
        center_lat, center_lng = h3.cell_to_latlng(target_hex)
        
        # Get the boundary of the hexagon
        boundary = h3.cell_to_boundary(target_hex)
        
        # Driver coordinates
        driver_lat = driver_location['lat']
        driver_lng = driver_location['lng']
        
        # Generate pickup points
        session_pickup_points = []  # For storing in session
        
        for i in range(num_pickup_points):
            pickup_id = str(uuid.uuid4())[:8]  # Generate unique ID for pickup point
            
            if i == 0:
                # First point near center
                distance = random.uniform(0.0005, 0.001)
                angle = random.uniform(0, 2 * np.pi)
                pickup_lat = center_lat + distance * np.cos(angle)
                pickup_lng = center_lng + distance * np.sin(angle)
                pickup_name = "Central Pickup"
                point_type = "Central Intersection"
            elif i == 1:
                # Second point near a random vertex
                vertex_idx = random.randint(0, len(boundary) - 1)
                vertex = boundary[vertex_idx]
                pickup_lat = vertex[0] * 0.9 + center_lat * 0.1
                pickup_lng = vertex[1] * 0.9 + center_lng * 0.1
                pickup_name = "Corner Pickup"
                point_type = "Street Corner"
            else:
                # Third point at a random position
                weights = [random.random() for _ in range(len(boundary))]
                weight_sum = sum(weights)
                weights = [w/weight_sum for w in weights]
                
                pickup_lat = sum(v[0] * w for v, w in zip(boundary, weights))
                pickup_lng = sum(v[1] * w for v, w in zip(boundary, weights))
                pickup_name = "Landmark Pickup"
                point_type = "Landmark"
            
            # Calculate estimated time (roughly 50 km/h = 0.008 degrees per minute)
            distance_degrees = ((pickup_lat - driver_lat)**2 + (pickup_lng - driver_lng)**2)**0.5
            estimated_minutes = int(distance_degrees / 0.008)
            
            # Store pickup point for session
            session_pickup_points.append({
                'id': pickup_id,
                'lat': pickup_lat,
                'lng': pickup_lng,
                'name': pickup_name,
                'type': point_type,
                'estimated_time': estimated_minutes
            })
            
            pickup_points.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [pickup_lng, pickup_lat]
                },
                "properties": {
                    "id": pickup_id,
                    "name": pickup_name,
                    "type": point_type,
                    "estimated_time": estimated_minutes,
                    "passengers": random.randint(5, 15)
                }
            })
            
            # Get route from Azure Maps Routing API
            route_data = get_azure_route(driver_lng, driver_lat, pickup_lng, pickup_lat)
            
            routes.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": route_data["coordinates"]
                },
                "properties": {
                    "id": pickup_id,
                    "name": f"Route to {pickup_name}",
                    "estimated_time": route_data["travel_time_minutes"],
                    "distance_km": route_data["distance_km"],
                    "color": ["#FF5733", "#33FF57", "#3357FF"][i % 3]  # Different colors for routes
                }
            })
        
        # Store pickup points in session
        session['session_pickup_points'] = session_pickup_points
    
    # Create a simplified driver map page to return to the driver device
    return render_template('driver_map.html', 
                          azure_maps_key=AZURE_MAPS_KEY,
                          driver_id=driver_id,
                          time_slot=time_slot,
                          is_near_high_demand=is_near_high_demand,
                          driver_data=driver_db_data,
                          hexagon_geojson={
                              "type": "FeatureCollection",
                              "features": hexagon_data
                          },
                          driver_geojson={
                              "type": "FeatureCollection",
                              "features": driver_data
                          },
                          pickup_geojson={
                              "type": "FeatureCollection",
                              "features": pickup_points
                          },
                          route_geojson={
                              "type": "FeatureCollection",
                              "features": routes
                          })

@app.route('/passenger_connect', methods=['GET'])
def passenger_connect():
    # Get current time slot (use the global state or default to first time slot)
    time_slot = global_state.get('current_time_slot') or generate_time_slots()[0]
    
    # Generate hexagons if not already done
    hexagons = generate_hexagons()
    
    # Initialize demand patterns if not already done
    if not global_state.get('demand_patterns'):
        demand_patterns, passenger_counts = initialize_demand_patterns(tuple(hexagons))
        global_state['passenger_counts'] = passenger_counts
        global_state['demand_patterns'] = demand_patterns
    
    # Find high demand hexagons
    high_demand_hexagons = [hex_id for hex_id, level in global_state['demand_patterns'][time_slot].items() 
                           if level == 'high']
    
    # Decide whether to place passenger in high demand area (70% chance) or outside it (30% chance)
    in_high_demand = random.random() < 0.7
    
    passenger_location = None
    passenger_hex = None
    
    if in_high_demand and high_demand_hexagons:
        # Choose a random high demand hexagon
        passenger_hex = random.choice(high_demand_hexagons)
        
        # Get center coordinates
        center_lat, center_lng = h3.cell_to_latlng(passenger_hex)
        
        # Get the boundary of the hexagon
        boundary = h3.cell_to_boundary(passenger_hex)
        
        # Generate a random position within the hexagon
        weights = [random.random() for _ in range(len(boundary))]
        weight_sum = sum(weights)
        weights = [w/weight_sum for w in weights]
        
        passenger_lat = sum(v[0] * w for v, w in zip(boundary, weights))
        passenger_lng = sum(v[1] * w for v, w in zip(boundary, weights))
        
        passenger_location = {'lat': passenger_lat, 'lng': passenger_lng}
    else:
        # Choose a random hexagon that is not high demand
        low_demand_hexagons = [hex_id for hex_id, level in global_state['demand_patterns'][time_slot].items() 
                              if level == 'low']
        
        if low_demand_hexagons:
            # Choose a random hexagon
            passenger_hex = random.choice(low_demand_hexagons)
            
            # Get center coordinates
            center_lat, center_lng = h3.cell_to_latlng(passenger_hex)
            
            # Get the boundary of the hexagon
            boundary = h3.cell_to_boundary(passenger_hex)
            
            # Generate a random position within the hexagon
            weights = [random.random() for _ in range(len(boundary))]
            weight_sum = sum(weights)
            weights = [w/weight_sum for w in weights]
            
            passenger_lat = sum(v[0] * w for v, w in zip(boundary, weights))
            passenger_lng = sum(v[1] * w for v, w in zip(boundary, weights))
            
            passenger_location = {'lat': passenger_lat, 'lng': passenger_lng}
    
    # Create a unique passenger ID
    passenger_id = str(uuid.uuid4())[:8]
    
    # Prepare data for map
    hexagon_data = []
    for hex_id in hexagons:
        hex_boundary = h3.cell_to_boundary(hex_id)
        hex_boundary = [[lng, lat] for lat, lng in hex_boundary]
        
        demand_level = global_state['demand_patterns'][time_slot][hex_id]
        original_passenger_count = global_state['passenger_counts'][time_slot][hex_id]
        
        if global_state.get('notifications_sent') and hex_id in global_state['passenger_counts'][time_slot]:
            current_passenger_count = global_state['passenger_counts'][time_slot][hex_id]
        else:
            current_passenger_count = original_passenger_count
        
        color = get_demand_color(demand_level)
        
        hexagon_data.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [hex_boundary]
            },
            "properties": {
                "hex_id": hex_id,
                "demand_level": demand_level,
                "original_passenger_count": original_passenger_count,
                "current_passenger_count": current_passenger_count,
                "color": color
            }
        })
    
    # Prepare driver data for map
    driver_data = []
    for driver in global_state.get('drivers', []):
        if driver['status'] in ['available', 'notified', 'connected']:
            if driver['status'] == 'connected':
                icon_color = 'yellow'
            elif driver['status'] == 'available':
                icon_color = 'blue'
            else:  # notified
                icon_color = 'orange'
            
            driver_data.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [driver['lng'], driver['lat']]
                },
                "properties": {
                    "driver_id": driver['id'],
                    "status": driver['status'],
                    "color": icon_color
                }
            })
    
    # Generate pickup points and walking route
    pickup_points = []
    walking_route = None
    
    # Check if passenger is in a high demand area
    is_in_high_demand = False
    if passenger_location and passenger_hex:
        is_in_high_demand = passenger_hex in high_demand_hexagons
    
    # Only generate pickup points if passenger is in a high demand area
    if is_in_high_demand and passenger_location:
        # Try to get POIs from Azure Maps Search API within the high demand hexagon
        center_lat, center_lng = h3.cell_to_latlng(passenger_hex)
        # Limit to exactly 3 POIs maximum
        pois = get_azure_pois(center_lat, center_lng, radius=300, limit=3)
        
        # If no POIs found or not enough, generate random pickup points within the high demand hexagon
        if len(pois) < 2:
            # Generate exactly 2-3 pickup points total (including any POIs already found)
            num_pickup_points = min(3, max(2, len(pois) + random.randint(1, 2)))
            
            # Get the boundary of the high demand hexagon
            boundary = h3.cell_to_boundary(passenger_hex)
            
            # Generate pickup points within the high demand hexagon
            for i in range(len(pois), num_pickup_points):
                if i == 0:
                    # First point near center
                    distance = random.uniform(0.0001, 0.0005)
                    angle = random.uniform(0, 2 * np.pi)
                    pickup_lat = center_lat + distance * np.cos(angle)
                    pickup_lng = center_lng + distance * np.sin(angle)
                    point_type = "Central Intersection"
                elif i == 1:
                    # Second point near a random vertex
                    vertex_idx = random.randint(0, len(boundary) - 1)
                    vertex = boundary[vertex_idx]
                    pickup_lat = vertex[0] * 0.9 + center_lat * 0.1
                    pickup_lng = vertex[1] * 0.9 + center_lng * 0.1
                    point_type = "Street Corner"
                else:
                    # Third point at a random position
                    weights = [random.random() for _ in range(len(boundary))]
                    weight_sum = sum(weights)
                    weights = [w/weight_sum for w in weights]
                    
                    pickup_lat = sum(v[0] * w for v, w in zip(boundary, weights))
                    pickup_lng = sum(v[1] * w for v, w in zip(boundary, weights))
                    point_type = "Landmark"
                
                pois.append({
                    "name": f"Pickup Point {i+1} ({point_type})",
                    "type": point_type,
                    "lat": pickup_lat,
                    "lng": pickup_lng,
                    "address": ""
                })
        
        # Ensure we have at most 3 POIs
        pois = pois[:3]
        
        # Create pickup points GeoJSON
        for poi in pois:
            # Calculate walking time (roughly 5 km/h = 0.0014 degrees per minute)
            distance_degrees = ((poi['lat'] - passenger_location['lat'])**2 + 
                               (poi['lng'] - passenger_location['lng'])**2)**0.5
            estimated_minutes = int(distance_degrees / 0.0014)
            
            pickup_points.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [poi['lng'], poi['lat']]
                },
                "properties": {
                    "name": poi['name'],
                    "type": poi['type'],
                    "estimated_time": estimated_minutes,
                    "address": poi['address']
                }
            })
        
        # Find the nearest pickup point
        if pickup_points:
            nearest_pickup = None
            min_distance = float('inf')
            
            for pickup in pickup_points:
                pickup_lng, pickup_lat = pickup['geometry']['coordinates']
                distance = ((pickup_lat - passenger_location['lat'])**2 + 
                           (pickup_lng - passenger_location['lng'])**2)**0.5
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_pickup = pickup
            
            # Get walking route to the nearest pickup point
            if nearest_pickup:
                nearest_lng, nearest_lat = nearest_pickup['geometry']['coordinates']
                
                # Ensure we're using the correct coordinates for the route
                route_data = get_azure_route(
                    passenger_location['lng'],  # Start longitude
                    passenger_location['lat'],  # Start latitude
                    nearest_lng,                # End longitude
                    nearest_lat,                # End latitude
                    mode="pedestrian"
                )
                
                # Create the walking route feature
                if route_data and "coordinates" in route_data and len(route_data["coordinates"]) > 0:
                    walking_route = {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": route_data["coordinates"]
                        },
                        "properties": {
                            "name": f"Walking route to {nearest_pickup['properties']['name']}",
                            "estimated_time": route_data["travel_time_minutes"],
                            "distance_km": route_data["distance_km"],
                            "color": "#4287f5"  # Blue color for walking route
                        }
                    }
                    print(f"Generated walking route with {len(route_data['coordinates'])} points")
                else:
                    print("Failed to generate walking route, route_data:", route_data)
    
    # Create passenger data
    passenger_data = []
    if passenger_location:
        passenger_data.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [passenger_location['lng'], passenger_location['lat']]
            },
            "properties": {
                "passenger_id": passenger_id,
                "color": "#FF00FF",  # Magenta color for passenger
                "is_in_high_demand": is_in_high_demand
            }
        })
    
    # Create a passenger map page to return
    return render_template('passenger_map.html', 
                          azure_maps_key=AZURE_MAPS_KEY,
                          passenger_id=passenger_id,
                          time_slot=time_slot,
                          is_in_high_demand=is_in_high_demand,
                          hexagon_geojson={
                              "type": "FeatureCollection",
                              "features": hexagon_data
                          },
                          driver_geojson={
                              "type": "FeatureCollection",
                              "features": driver_data
                          },
                          passenger_geojson={
                              "type": "FeatureCollection",
                              "features": passenger_data
                          },
                          pickup_geojson={
                              "type": "FeatureCollection",
                              "features": pickup_points
                          },
                          walking_route_geojson={
                              "type": "FeatureCollection",
                              "features": [walking_route] if walking_route else []
                          })

@app.route('/ride_status', methods=['GET'])
def ride_status():
    # Get driver ID from query parameters
    driver_id = request.args.get('driver_id', None)
    outcome = request.args.get('outcome', 'completed')  # Default to completed
    distance = float(request.args.get('distance', 0))  # Distance in km
    
    if not driver_id:
        return "Driver ID is required", 400
    
    # Get driver data from the database
    driver_data = get_driver_data(driver_id)
    
    if not driver_data:
        return "Driver not found", 404
    
    # Update driver data based on outcome
    if outcome == 'completed':
        # Always increment no_of_peak_hrs_rides when a ride is completed
        update_driver_data(driver_id, 'no_of_peak_hrs_rides', increment=1, distance=distance)
        # Get updated driver data
        driver_data = get_driver_data(driver_id)
    elif outcome == 'canceled':
        # If ride was canceled, increment no_of_cancellations
        update_driver_data(driver_id, 'no_of_cancellations', increment=1)
        # Get updated driver data
        driver_data = get_driver_data(driver_id)
    
    # Render the ride status template
    return render_template('ride_status.html', 
                          driver_id=driver_id,
                          driver_data=driver_data,
                          outcome=outcome,
                          distance_km=distance)

@app.route('/passenger_decision', methods=['GET'])
def passenger_decision():
    # Get decision parameter (move or stay)
    decision = request.args.get('decision', 'stay')
    
    # Render the passenger_decision template with the decision
    return render_template('passenger_decision.html', decision=decision)

@app.route('/driver_leaderboard')
def driver_leaderboard():
    try:
        # Connect to the database
        conn = sqlite3.connect('driver_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all drivers ordered by commit points (descending)
        cursor.execute('''
        SELECT * FROM drivers 
        ORDER BY commit_points DESC
        ''')
        
        drivers = []
        for row in cursor.fetchall():
            drivers.append({
                'driver_id': row['driver_id'],
                'no_of_peak_hrs_rides': row['no_of_peak_hrs_rides'],
                'trust_score': row['trust_score'],
                'commit_points': row['commit_points'],
                'no_of_cancellations': row['no_of_cancellations'],
                'distance_traveled': row['distance_traveled']
            })
        
        conn.close()
        
        # Calculate rewards based on commit points
        for driver in drivers:
            points = driver['commit_points']
            if points >= 500:
                driver['reward'] = "$50 Cash Reward + Premium Discount"
                driver['tier'] = "Platinum"
            elif points >= 300:
                driver['reward'] = "$25 Cash Reward + 30% Discount"
                driver['tier'] = "Gold"
            elif points >= 200:
                driver['reward'] = "20% Discount on Next Service"
                driver['tier'] = "Silver"
            elif points >= 100:
                driver['reward'] = "10% Discount on Next Service"
                driver['tier'] = "Bronze"
            else:
                driver['reward'] = "5% Discount on Next Service"
                driver['tier'] = "Standard"
        
        return render_template('driver_leaderboard.html', drivers=drivers)
    except Exception as e:
        print(f"Error fetching driver leaderboard: {e}")
        return "Error loading leaderboard", 500

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=5001, debug=True)