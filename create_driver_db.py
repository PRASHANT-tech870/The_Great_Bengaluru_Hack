import sqlite3
import random
import uuid

# Constants for calculations
alpha = 1.5
beta = 3
w1 = 40
w2 = 60
max_distance = 5  # in km

def create_driver_db():
    """Create a new SQLite database with 15 drivers"""
    try:
        # Connect to SQLite database (will create if it doesn't exist)
        conn = sqlite3.connect('driver_data.db')
        cursor = conn.cursor()
        
        # Drop the table if it exists
        cursor.execute('DROP TABLE IF EXISTS drivers')
        
        # Create the drivers table
        cursor.execute('''
        CREATE TABLE drivers (
            driver_id TEXT PRIMARY KEY,
            no_of_peak_hrs_rides INTEGER DEFAULT 0,
            trust_score REAL DEFAULT 80,
            commit_points REAL DEFAULT 0,
            no_of_cancellations INTEGER DEFAULT 0,
            distance_traveled REAL DEFAULT 0
        )
        ''')
        
        # Generate 15 drivers with random initial values
        drivers = []
        for _ in range(15):
            driver_id = str(uuid.uuid4())[:8]
            peak_rides = random.randint(0, 20)
            cancellations = random.randint(0, 5)
            distance = random.uniform(0, 4)
            
            # Calculate initial trust score
            trust_score = 80 + (alpha * peak_rides) - (beta * cancellations)
            trust_score = max(0, min(100, trust_score))
            
            # Calculate initial commit points
            commit_points = w1 * (trust_score / 100) + w2 * (min(distance, max_distance) / max_distance)
            
            drivers.append((
                driver_id,
                peak_rides,
                trust_score,
                commit_points,
                cancellations,
                distance
            ))
        
        # Insert drivers into the database
        cursor.executemany('''
        INSERT INTO drivers (driver_id, no_of_peak_hrs_rides, trust_score, commit_points, no_of_cancellations, distance_traveled)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', drivers)
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print(f"Successfully created driver database with 15 drivers")
        
        # Print out the drivers for verification
        conn = sqlite3.connect('driver_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM drivers')
        rows = cursor.fetchall()
        
        print("\nDriver Database Contents:")
        print("-" * 100)
        print(f"{'Driver ID':<10} | {'Peak Rides':<10} | {'Trust Score':<11} | {'Commit Points':<13} | {'Cancellations':<13} | {'Distance (km)':<12}")
        print("-" * 100)
        
        for row in rows:
            print(f"{row['driver_id']:<10} | {row['no_of_peak_hrs_rides']:<10} | {row['trust_score']:<11.2f} | {row['commit_points']:<13.2f} | {row['no_of_cancellations']:<13} | {row['distance_traveled']:<12.2f}")
        
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error creating driver database: {e}")
        return False

if __name__ == "__main__":
    create_driver_db() 