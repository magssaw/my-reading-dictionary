import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import logging
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Configure database
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    words = db.relationship('Word', backref='user', lazy=True)

class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def get_word_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            meanings = data[0].get('meanings', [])
            if meanings:
                definitions = meanings[0].get('definitions', [])
                if definitions:
                    return definitions[0].get('definition', 'No definition found.')
    return 'Definition not found.'

@app.route('/')
def index():
    app.logger.debug('Accessing index route')
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    app.logger.debug('Accessing register route')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
        else:
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    app.logger.debug('Accessing login route')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Logged in successfully')
            return redirect(url_for('dictionary'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    app.logger.debug('Accessing logout route')
    session.pop('user_id', None)
    flash('Logged out successfully')
    return redirect(url_for('index'))

@app.route('/dictionary', methods=['GET', 'POST'])
def dictionary():
    app.logger.debug('Accessing dictionary route')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        word = request.form['word']
        definition = get_word_definition(word)
        new_word = Word(word=word, definition=definition, user_id=session['user_id'])
        db.session.add(new_word)
        db.session.commit()
        flash(f'Word "{word}" added to your dictionary')

    user_words = Word.query.filter_by(user_id=session['user_id']).order_by(Word.id.desc()).all()
    return render_template('dictionary.html', words=user_words)


@app.errorhandler(500)
def internal_error(error):
    app.logger.error('Server Error: %s', (error))
    return "500 error: Internal Server Error", 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error('Unhandled Exception: %s', (e))
    return "500 error: Internal Server Error", 500

# Attempt database connection
with app.app_context():
    try:
        db.create_all()
        app.logger.info("Database tables created successfully")
    except Exception as e:
        app.logger.error(f"Error creating database tables: {str(e)}")
        print(f"Error creating database tables: {str(e)}", file=sys.stderr)

if __name__ == '__main__':
    app.run(debug=True)