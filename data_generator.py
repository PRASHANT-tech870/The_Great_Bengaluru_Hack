import h3
import numpy as np
from datetime import datetime, timedelta
import random
import uuid
from functools import lru_cache

# Define a bounding box for NYC
NYC_BOUNDING_BOX = {
    "min_lat": 40.4774,
    "max_lat": 40.9176,
    "min_lon": -74.2591,
    "max_lon": -73.7004
}

# Choose an H3 resolution (7 is a good balance for city-level analysis)
H3_RESOLUTION = 7

# Generate time slots in 30-minute intervals for a full day
def generate_time_slots():
    start_time = datetime.strptime("00:00", "%H:%M")
    end_time = datetime.strptime("23:30", "%H:%M")
    time_delta = timedelta(minutes=30)
    
    time_slots = []
    current_time = start_time
    
    while current_time <= end_time:
        time_slots.append(current_time.strftime("%H:%M"))
        current_time += time_delta
    
    return time_slots

# Generate hexagons covering the bounding box
@lru_cache(maxsize=1)  # Replacing st.cache_data with Python's lru_cache
def generate_hexagons():
    hexagons = set()
    lat_range = np.linspace(NYC_BOUNDING_BOX["min_lat"], NYC_BOUNDING_BOX["max_lat"], 50)
    lon_range = np.linspace(NYC_BOUNDING_BOX["min_lon"], NYC_BOUNDING_BOX["max_lon"], 50)

    for lat in lat_range:
        for lon in lon_range:
            hex_id = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
            hexagons.add(hex_id)
    
    return list(hexagons)

# Generate passenger counts based on demand level
def generate_passenger_count(demand_level):
    if demand_level == 'high':
        return random.randint(30, 50)
    else:  # low
        return random.randint(0, 9)

# Initialize demand patterns and passenger counts for each time slot
@lru_cache(maxsize=1)  # Replacing st.cache_data with Python's lru_cache
def initialize_demand_patterns(hexagons):
    time_slots = generate_time_slots()
    demand_patterns = {}
    passenger_counts = {}
    
    # Define peak hours (morning and evening)
    morning_peak_start = datetime.strptime("07:00", "%H:%M")
    morning_peak_end = datetime.strptime("09:30", "%H:%M")
    evening_peak_start = datetime.strptime("16:30", "%H:%M")
    evening_peak_end = datetime.strptime("19:00", "%H:%M")
    
    # Select a few hexagons (2-3) to be high demand areas during peak hours
    num_high_demand_areas = random.randint(2, 3)
    high_demand_hexagons = random.sample(hexagons, num_high_demand_areas)
    
    for time_slot in time_slots:
        slot_time = datetime.strptime(time_slot, "%H:%M")
        is_morning_peak = morning_peak_start <= slot_time <= morning_peak_end
        is_evening_peak = evening_peak_start <= slot_time <= evening_peak_end
        
        demand_patterns[time_slot] = {}
        passenger_counts[time_slot] = {}
        
        for hex_id in hexagons:
            if hex_id in high_demand_hexagons:
                if is_morning_peak or is_evening_peak:
                    # High demand during peak hours
                    demand_patterns[time_slot][hex_id] = 'high'
                else:
                    # Low demand during non-peak hours
                    demand_patterns[time_slot][hex_id] = 'low'
            else:
                # Mostly low demand areas
                demand_patterns[time_slot][hex_id] = 'low'
            
            # Generate passenger count based on demand level
            passenger_counts[time_slot][hex_id] = generate_passenger_count(demand_patterns[time_slot][hex_id])
    
    return demand_patterns, passenger_counts

# Get demand color based on demand level
def get_demand_color(demand_level):
    if demand_level == 'high':
        return 'red'
    else:  # low
        return 'green'

# Add a function to generate drivers around high-demand areas
def generate_drivers(hexagons, demand_patterns, time_slot):
    drivers = []
    high_demand_hexagons = [hex_id for hex_id, level in demand_patterns[time_slot].items() if level == 'high']
    
    if not high_demand_hexagons:
        return drivers
    
    # Find hexagons in the 1-2 rings surrounding high demand areas
    surrounding_hexagons = set()
    for hex_id in high_demand_hexagons:
        # Get ring 1 (adjacent hexagons)
        ring1 = h3.grid_ring(hex_id, 1)
        # Get ring 2 (second layer of hexagons)
        ring2 = h3.grid_ring(hex_id, 2)
        
        surrounding_hexagons.update(ring1)
        surrounding_hexagons.update(ring2)
    
    # Remove any high demand hexagons from the surrounding set
    surrounding_hexagons = [h for h in surrounding_hexagons if h not in high_demand_hexagons]
    
    # Generate 20-30 drivers
    num_drivers = random.randint(20, 30)
    
    for i in range(num_drivers):
        # Select a random surrounding hexagon to place driver in
        if surrounding_hexagons:
            target_hex = random.choice(surrounding_hexagons)
            # Get the center of the hexagon
            center = h3.cell_to_latlng(target_hex)
            
            # Generate a position randomly distributed within the hexagon
            # Get the hexagon boundary vertices
            boundary = h3.cell_to_boundary(target_hex)
            
            # Choose a random approach:
            # 1. Random position within the hexagon using weighted average of vertices
            # 2. Random position near the center with random offset
            if random.choice([True, False]):
                # Approach 1: Random position within hexagon using weighted vertices
                weights = [random.random() for _ in range(len(boundary))]
                weight_sum = sum(weights)
                weights = [w/weight_sum for w in weights]
                
                lat = sum(v[0] * w for v, w in zip(boundary, weights))
                lng = sum(v[1] * w for v, w in zip(boundary, weights))
            else:
                # Approach 2: Random position near center with offset
                # Distance from center (in degrees, roughly 0.0001-0.001 degrees = ~10-100 meters)
                distance = random.uniform(0.0001, 0.001)
                # Random angle
                angle = random.uniform(0, 2 * np.pi)
                
                # Calculate new position
                lat = center[0] + distance * np.cos(angle)
                lng = center[1] + distance * np.sin(angle)
            
            # Create driver object
            driver = {
                'id': str(uuid.uuid4())[:8],  # Generate a unique ID
                'lat': lat,
                'lng': lng,
                'status': 'available',  # available, notified, accepted, en_route
                'target_hex': None
            }
            
            drivers.append(driver)
    
    return drivers

# Function to simulate driver responses to notifications
def simulate_driver_responses(drivers, passenger_counts, time_slot):
    # Count of drivers who accepted notifications
    accepted_count = 0
    
    for driver in drivers:
        if driver['status'] == 'notified':
            # 70% chance of accepting the ride
            if random.random() < 0.7:
                driver['status'] = 'accepted'
                accepted_count += 1
            else:
                driver['status'] = 'available'  # Driver rejected the notification
    
    return accepted_count