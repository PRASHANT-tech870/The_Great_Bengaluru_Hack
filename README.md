# Ride-Hailing Platform - Solving Namma Yatri's Problem!

A dynamic ride-hailing platform that optimizes driver allocation and passenger pickup in high-demand areas using hexagonal geospatial mapping.

![Ride-Hailing Platform](https://www.google.com/imgres?q=namma%20yatri&imgurl=https%3A%2F%2Fmedia.assettype.com%2Fnewindianexpress%252F2024-07%252Fd44f15fc-fea5-44fe-925b-143f99547de8%252Fnamma%2520yatri.jpg&imgrefurl=https%3A%2F%2Fwww.newindianexpress.com%2Fbusiness%2F2024%2FJul%2F16%2Fbengaluru-based-namma-yatri-raises-rs-92-crore-funding-from-google-antler-and-others&docid=LhDPdxX-uLxNJM&tbnid=5O23Ug_a5AS5YM&vet=12ahUKEwiXpczu2Y2MAxUjxjgGHVpXOmkQM3oECFsQAA..i&w=1174&h=872&hcb=2&ved=2ahUKEwiXpczu2Y2MAxUjxjgGHVpXOmkQM3oECFsQAA)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Application](#running-the-application)
- [System Architecture](#system-architecture)
  - [Main Dashboard](#main-dashboard)
  - [Driver Interface](#driver-interface)
  - [Passenger Interface](#passenger-interface)
  - [Database](#database)
  - [Leaderboard](#leaderboard)
- [Technical Details](#technical-details)
  - [H3 Hexagonal Mapping](#h3-hexagonal-mapping)
  - [Demand Modeling](#demand-modeling)
  - [Driver Allocation](#driver-allocation)
  - [Trust Score & Commit Points](#trust-score--commit-points)
- [API Endpoints](#api-endpoints)
- [File Structure](#file-structure)
- [Future Enhancements](#future-enhancements)

## Overview

This platform simulates a ride-hailing service in New York City, using H3 hexagonal mapping to visualize and manage demand patterns. The system optimizes driver allocation to high-demand areas, provides incentives for drivers through a reward system, and offers passengers options to improve their ride experience during peak hours.

The application demonstrates how intelligent routing and demand prediction can create a more efficient transportation network, reducing wait times and improving the overall experience for both drivers and passengers.

## Features

- **Real-time Demand Visualization**: View high and low demand areas across NYC using hexagonal mapping
- **Driver Allocation System**: Intelligently notify and position drivers near high-demand areas
- **Passenger Decision System**: Allow passengers to choose between moving to a better pickup location or staying in place
- **Driver Rewards Program**: Motivate drivers with a tiered rewards system based on performance metrics
- **Trust Score & Commit Points**: Track driver reliability and commitment through a sophisticated scoring system
- **Interactive Maps**: Azure Maps integration for visualizing demand, drivers, and routes
- **Simulated Environment**: Test different scenarios with simulated driver responses and passenger behavior

## Getting Started

### Prerequisites

- Python 3.7+
- SQLite3
- Internet connection (for Azure Maps API)

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd GB\ Hack\ 2
   ```

2. Install the required Python packages:
   ```
   pip install flask h3 numpy requests
   ```

3. Initialize the driver database:
   ```
   cd APP
   python create_driver_db.py
   ```

### Running the Application

1. Start the Flask application:
   ```
   cd APP
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5001
   ```

3. The main dashboard will appear, showing the NYC map with hexagonal demand visualization.

## System Architecture

### Main Dashboard

The main dashboard (`index.html`) provides an overview of the entire system:

- **Demand Map**: Visualizes high-demand (red) and low-demand (green) areas using hexagons
- **Time Slot Selection**: Choose different times of day to see how demand patterns change
- **Driver Management**: Send notifications to drivers and simulate their responses
- **Statistics Panel**: View real-time statistics about demand and driver availability
- **Leaderboard Access**: View the driver performance leaderboard

### Driver Interface

The driver interface (`driver_map.html`) simulates the driver's mobile app experience:

- **Location Visualization**: Shows the driver's current position on the map
- **Demand Awareness**: Highlights high-demand areas where drivers should position themselves
- **Pickup Recommendations**: When near high-demand areas, suggests optimal pickup points
- **Route Guidance**: Provides routes to pickup points with estimated travel times
- **Driver Statistics**: Displays the driver's performance metrics (trust score, commit points, etc.)

### Passenger Interface

The passenger interface (`passenger_map.html`) simulates the passenger's mobile app experience:

- **Location Visualization**: Shows the passenger's current position on the map
- **Pickup Options**: When in high-demand areas, displays available pickup points
- **Walking Routes**: Shows walking routes to the nearest pickup point
- **Decision System**: Offers options to "Move" to a better location or "Stay" in place
- **Feedback System**: Provides feedback on the passenger's decision

### Database

The system uses SQLite to store driver data (`driver_data.db`):

- **Driver Records**: Stores unique driver IDs and performance metrics
- **Performance Tracking**: Records peak hour rides, cancellations, and distance traveled
- **Scoring System**: Calculates and stores trust scores and commit points

### Leaderboard

The leaderboard (`driver_leaderboard.html`) motivates drivers through competition and rewards:

- **Driver Rankings**: Ranks drivers based on their commit points
- **Performance Statistics**: Shows detailed metrics for each driver
- **Reward Tiers**: Displays the rewards available at different performance levels
- **Visual Indicators**: Highlights top performers with special styling and icons

## Technical Details

### H3 Hexagonal Mapping

The application uses Uber's H3 geospatial indexing system to divide NYC into hexagonal cells:

- **Resolution 7**: Provides a good balance between granularity and performance
- **Hexagon Generation**: Creates hexagons covering the NYC bounding box
- **Demand Assignment**: Assigns demand levels to each hexagon based on time of day
- **Passenger Counts**: Simulates passenger counts within each hexagon

### Demand Modeling

The system models demand patterns across different times of day:

- **Peak Hours**: 07:00-09:30 (morning) and 16:30-19:00 (evening)
- **High Demand Areas**: 2-3 hexagons are designated as high-demand during peak hours
- **Passenger Distribution**: 30-50 passengers in high-demand areas, 0-9 in low-demand areas
- **Demand Visualization**: Color-coded hexagons (red for high demand, green for low demand)

### Driver Allocation

Drivers are intelligently positioned and notified about high-demand areas:

- **Initial Positioning**: 70% chance of placing drivers near high-demand areas
- **Notification System**: Alerts available drivers about nearby high-demand areas
- **Response Simulation**: Simulates driver responses to notifications (70% acceptance rate)
- **Pickup Points**: Generates strategic pickup points within high-demand hexagons

### Trust Score & Commit Points

The system uses a sophisticated scoring mechanism to evaluate and reward drivers:

- **Trust Score Formula**: `trust_score = current_trust + (alpha * peak_rides) - (beta * cancellations)`
- **Commit Points Formula**: `commit_points = w1 * (trust_score / 100) + w2 * (distance_traveled / max_distance)`
- **Reward Tiers**: Platinum (500+ points), Gold (300+ points), Silver (200+ points), Bronze (100+ points)
- **Rewards**: Cash bonuses and service discounts based on tier level

## API Endpoints

The application provides several API endpoints:

- **`/`**: Main dashboard view
- **`/get_data`**: Retrieves hexagon and driver data for the map
- **`/send_notifications`**: Sends notifications to available drivers
- **`/simulate_responses`**: Simulates driver responses to notifications
- **`/driver_connect`**: Driver interface with pickup recommendations
- **`/passenger_connect`**: Passenger interface with pickup options
- **`/ride_status`**: Displays ride status and updates driver metrics
- **`/passenger_decision`**: Handles passenger decisions to move or stay
- **`/driver_leaderboard`**: Displays the driver performance leaderboard

## File Structure

```
APP/
├── app.py                  # Main Flask application
├── data_generator.py       # Generates demand patterns and driver data
├── create_driver_db.py     # Initializes the driver database
├── driver_data.db          # SQLite database for driver metrics
├── static/
│   ├── css/
│   │   └── style.css       # Main stylesheet
│   └── js/
│       ├── main.js         # Dashboard JavaScript
│       ├── driver.js       # Driver interface JavaScript
│       └── passenger.js    # Passenger interface JavaScript
└── templates/
    ├── index.html          # Main dashboard template
    ├── driver_map.html     # Driver interface template
    ├── passenger_map.html  # Passenger interface template
    ├── ride_status.html    # Ride status template
    ├── passenger_decision.html # Passenger decision template
    └── driver_leaderboard.html # Driver leaderboard template
```

## Future Enhancements

- **Real-time Data Integration**: Connect to real traffic and demand data
- **Machine Learning Models**: Implement predictive models for demand forecasting
- **Mobile Applications**: Develop native mobile apps for drivers and passengers
- **Payment Integration**: Add simulated payment processing
- **Social Features**: Add driver-to-driver and passenger-to-passenger communication
- **Advanced Analytics**: Provide deeper insights into system performance
- **Expanded Reward System**: More sophisticated incentives and gamification elements

---

Created for The Great Bengaluru Hack - A demonstration of intelligent transportation systems using geospatial data and optimization algorithms. 