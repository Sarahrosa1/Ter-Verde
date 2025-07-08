# app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = 'f5e1b2c3d4e5f6a7b8c9d0e1f' 

# --- Funções de Banco de Dados ---
def get_db_connection():
    conn = sqlite3.connect('tereverde.db')
    conn.row_factory = sqlite3.Row  
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT "visitor" 
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            operating_hours TEXT,
            status TEXT NOT NULL DEFAULT "disponivel" 
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            difficulty TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT "disponivel", 
            FOREIGN KEY (park_id) REFERENCES parks (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            event_date TEXT,
            event_time TEXT,
            description TEXT,
            FOREIGN KEY (park_id) REFERENCES parks (id) ON DELETE CASCADE
        )
    ''')

    admin_password_hash = generate_password_hash('admin123')
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', admin_password_hash, 'admin'))
    
    conn.commit()
    conn.close()

with app.app_context():
    init_db()

# --- Decoradores e Contexto do Usuário ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Você precisa estar logado para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Você precisa estar logado para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        if g.user['role'] != 'admin':
            flash('Acesso negado: Você não tem permissão de administrador.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        g.user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

@app.context_processor
def inject_user():
    return dict(current_user=g.user)

# --- Rotas Públicas ---
@app.route('/')
def index():
    conn = get_db_connection()
    parks = conn.execute('SELECT * FROM parks').fetchall()
    conn.close()
    return render_template('index.html', parks=parks)

@app.route('/park/<int:park_id>')
def park_detail(park_id):
    conn = get_db_connection()
    park = conn.execute('SELECT * FROM parks WHERE id = ?', (park_id,)).fetchone()
    trails = conn.execute('SELECT * FROM trails WHERE park_id = ?', (park_id,)).fetchall()
    events = conn.execute('SELECT * FROM events WHERE park_id = ?', (park_id,)).fetchall()
    conn.close()

    if park is None:
        flash('Parque não encontrado.', 'danger')
        return redirect(url_for('index'))
    return render_template('park_detail.html', park=park, trails=trails, events=events)

# --- Rotas de Autenticação ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        flash('Você já está logado.', 'info')
        if g.user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login realizado com sucesso!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        flash('Você já está logado.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not username or not password or not confirm_password:
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('As senhas não coincidem!', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing_user:
            flash('Nome de usuário já existe. Por favor, escolha outro.', 'danger')
            conn.close()
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, hashed_password, 'visitor'))
        conn.commit()
        conn.close()
        flash('Cadastro realizado com sucesso! Você pode fazer login agora.', 'success')
        return redirect(url_for('login'))
    return render_template('cadastro.html')

# --- Rotas Administrativas ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    # Buscar todos os parques
    parks_data = conn.execute('SELECT * FROM parks').fetchall()
    
    
    parks_with_items = []
    for park in parks_data:
        park_dict = dict(park) 
        
        
        trails_for_park = conn.execute('SELECT * FROM trails WHERE park_id = ?', (park['id'],)).fetchall()
        park_dict['trails'] = [dict(trail) for trail in trails_for_park] 
        
        
        events_for_park = conn.execute('SELECT * FROM events WHERE park_id = ?', (park['id'],)).fetchall()
        park_dict['events'] = [dict(event) for event in events_for_park] # Converte para lista de dicionários
        
        parks_with_items.append(park_dict)
    
    conn.close()
    
    return render_template('admin_dashboard.html', parks_with_items=parks_with_items)

# Gerenciamento de Parques
@app.route('/admin/park/add', methods=['GET', 'POST'])
@admin_required
def add_park():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        operating_hours = request.form.get('operating_hours')
        status = request.form.get('status', 'disponivel') 
        
        conn = get_db_connection()
        conn.execute('INSERT INTO parks (name, description, operating_hours, status) VALUES (?, ?, ?, ?)', (name, description, operating_hours, status))
        conn.commit()
        conn.close()
        flash('Parque adicionado com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_add_park.html')

@app.route('/admin/park/edit/<int:park_id>', methods=['GET', 'POST'])
@admin_required
def edit_park(park_id):
    conn = get_db_connection()
    park = conn.execute('SELECT * FROM parks WHERE id = ?', (park_id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        operating_hours = request.form.get('operating_hours')
        status = request.form.get('status', 'disponivel') 
        
        conn.execute('UPDATE parks SET name = ?, description = ?, operating_hours = ?, status = ? WHERE id = ?', (name, description, operating_hours, status, park_id))
        conn.commit()
        conn.close()
        flash('Parque atualizado com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))

    conn.close()
    if park is None:
        flash('Parque não encontrado para edição.', 'danger')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_park.html', park=park)

@app.route('/admin/park/delete/<int:park_id>', methods=['POST'])
@admin_required
def delete_park(park_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM parks WHERE id = ?', (park_id,))
    conn.commit()
    conn.close()
    flash('Parque e seus itens associados deletados com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

# Gerenciamento de Trilhas
@app.route('/admin/trail/add/<int:park_id>', methods=['GET', 'POST'])
@admin_required
def add_trail(park_id):
    conn = get_db_connection()
    park = conn.execute('SELECT name FROM parks WHERE id = ?', (park_id,)).fetchone()
    
    if park is None:
        flash('Parque não encontrado para adicionar trilha.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        difficulty = request.form['difficulty']
        description = request.form['description']
        status = request.form.get('status', 'disponivel') 
        
        conn.execute('INSERT INTO trails (park_id, name, difficulty, description, status) VALUES (?, ?, ?, ?, ?)', 
                     (park_id, name, difficulty, description, status))
        conn.commit()
        flash(f'Trilha "{name}" adicionada com sucesso ao parque "{park["name"]}"!', 'success')
        conn.close()
        return redirect(url_for('park_detail', park_id=park_id))
    
    conn.close()
    return render_template('admin_add_trail.html', park_id=park_id, park_name=park['name'])

@app.route('/admin/trail/edit/<int:trail_id>', methods=['GET', 'POST'])
@admin_required
def edit_trail(trail_id):
    conn = get_db_connection()
    trail = conn.execute('SELECT * FROM trails WHERE id = ?', (trail_id,)).fetchone()
    
    if trail is None:
        flash('Trilha não encontrada.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        difficulty = request.form['difficulty']
        description = request.form['description']
        status = request.form.get('status', 'disponivel') 
        
        conn.execute('UPDATE trails SET name = ?, difficulty = ?, description = ?, status = ? WHERE id = ?', (name, difficulty, description, status, trail_id))
        conn.commit()
        flash('Trilha atualizada com sucesso!', 'success')
        conn.close()
        return redirect(url_for('park_detail', park_id=trail['park_id']))
    
    conn.close()
    return render_template('admin_edit_trail.html', trail=trail)

@app.route('/admin/trail/delete/<int:trail_id>', methods=['POST'])
@admin_required
def delete_trail(trail_id):
    conn = get_db_connection()
    trail = conn.execute('SELECT park_id FROM trails WHERE id = ?', (trail_id,)).fetchone()
    if trail:
        park_id = trail['park_id']
        conn.execute('DELETE FROM trails WHERE id = ?', (trail_id,))
        conn.commit()
        flash('Trilha excluída com sucesso!', 'info')
        conn.close()
        return redirect(url_for('park_detail', park_id=park_id))
    else:
        flash('Trilha não encontrada.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

# Gerenciamento de Eventos
@app.route('/admin/event/add/<int:park_id>', methods=['GET', 'POST'])
@admin_required
def add_event(park_id):
    conn = get_db_connection()
    park = conn.execute('SELECT name FROM parks WHERE id = ?', (park_id,)).fetchone()
    if park is None:
        flash('Parque não encontrado.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        event_date = request.form['event_date']
        event_time = request.form['event_time']
        description = request.form['description']
        conn.execute('INSERT INTO events (park_id, name, event_date, event_time, description) VALUES (?, ?, ?, ?, ?)', (park_id, name, event_date, event_time, description))
        conn.commit()
        flash('Evento adicionado com sucesso!', 'success')
        conn.close()
        return redirect(url_for('park_detail', park_id=park_id))
    
    conn.close()
    return render_template('admin_add_event.html', park_id=park_id, park_name=park['name'])

@app.route('/admin/event/edit/<int:event_id>', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    
    if event is None:
        flash('Evento não encontrado.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        event_date = request.form['event_date']
        event_time = request.form['event_time']
        description = request.form['description']
        conn.execute('UPDATE events SET name = ?, event_date = ?, event_time = ?, description = ? WHERE id = ?', (name, event_date, event_time, description, event_id))
        conn.commit()
        flash('Evento atualizado com sucesso!', 'success')
        conn.close()
        return redirect(url_for('park_detail', park_id=event['park_id']))
    
    conn.close()
    return render_template('admin_edit_event.html', event=event)

@app.route('/admin/event/delete/<int:event_id>', methods=['POST'])
@admin_required
def delete_event(event_id):
    conn = get_db_connection()
    event = conn.execute('SELECT park_id FROM events WHERE id = ?', (event_id,)).fetchone()
    if event:
        park_id = event['park_id']
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        flash('Evento excluído com sucesso!', 'info')
        conn.close()
        return redirect(url_for('park_detail', park_id=park_id))
    else:
        flash('Evento não encontrado.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
