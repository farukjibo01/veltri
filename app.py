from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import datetime

app = Flask(__name__)
CORS(app)

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veltri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Message table
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def home():
    return jsonify({'message': 'Welcome to Veltri API! 🚀'})

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({'error': 'Username already taken!'}), 400
    
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': f'Welcome to Veltri, {username}!'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username, password=password).first()
    if not user:
        return jsonify({'error': 'Invalid username or password!'}), 401
    
    return jsonify({'message': f'Welcome back, {username}!'}), 200

@app.route('/send-message', methods=['POST'])
def send_message():
    data = request.json
    username = data.get('username')
    content = data.get('content')
    
    if not username or not content:
        return jsonify({'error': 'Missing data'}), 400
    
    new_message = Message(username=username, content=content)
    db.session.add(new_message)
    db.session.commit()
    
    return jsonify({'message': 'Message sent!', 'id': new_message.id}), 201

@app.route('/get-messages', methods=['GET'])
def get_messages():
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    result = []
    for m in messages:
        result.append({
            'username': m.username,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%H:%M')
        })
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
