from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models.store import Reward, Redemption, PointsTransaction
from app import db
from datetime import datetime
import random
import string

bp = Blueprint('store', __name__, url_prefix='/store')

@bp.route('/')
@login_required
def index():
    rewards = Reward.query.filter_by(is_active=True).all()
    return render_template('store/index.html', rewards=rewards)

@bp.route('/redeem', methods=['POST'])
@login_required
def redeem():
    data = request.get_json()
    reward_id = data.get('reward_id')
    
    reward = Reward.query.get_or_404(reward_id)
    
    if reward.available_quantity <= 0:
        return jsonify({'status': 'error', 'message': 'Reward out of stock'})
    
    if current_user.commit_points < reward.points_required:
        return jsonify({'status': 'error', 'message': 'Insufficient points'})
    
    try:
        # Generate coupon code
        coupon_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Create redemption record
        redemption = Redemption(
            user_id=current_user.id,
            reward_id=reward_id,
            points_spent=reward.points_required,
            coupon_code=coupon_code
        )
        
        # Create points transaction
        transaction = PointsTransaction(
            user_id=current_user.id,
            points=-reward.points_required,
            description=f"Redeemed {reward.name}",
            transaction_type='spent'
        )
        
        # Update user points and reward quantity
        current_user.commit_points -= reward.points_required
        reward.available_quantity -= 1
        
        db.session.add(redemption)
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully redeemed! Your coupon code is: {coupon_code}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}) 