from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
import requests
from . import main
from .. import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('landing/index.html')

@bp.route('/about')
def about():
    return render_template('landing/about.html')

@bp.route('/features')
def features():
    return render_template('landing/features.html')

@bp.route('/contact')
def contact():
    return render_template('landing/contact.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/index.html')

@bp.route('/connect_location_service', methods=['POST'])
@login_required
def connect_location_service():
    try:
        # This is where you'll integrate with your existing server logic
        # Return dummy data for now
        return jsonify({
            'status': 'success',
            'latitude': 12.9716,  # Default Bangalore coordinates
            'longitude': 77.5946,
            'trustScore': '4.8',
            'cancellations': '2',
            'peakRides': '15',
            'earnings': '2,450'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/update_location', methods=['POST'])
@login_required
def update_location():
    data = request.get_json()
    
    if current_user and data:
        current_user.latitude = data.get('latitude')
        current_user.longitude = data.get('longitude')
        db.session.commit()
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error'}), 400

@bp.route('/proxy_driver_connect')
@login_required
def proxy_driver_connect():
    try:
        # Make the request from the server side
        response = requests.get('http://192.168.23.61:5001/driver_connect')
        return response.text, response.status_code, {'Content-Type': 'text/html'}
    except Exception as e:
        return str(e), 500

@bp.route('/ride_status')
@login_required
def ride_status():
    return render_template('dashboard/ride_status.html') 