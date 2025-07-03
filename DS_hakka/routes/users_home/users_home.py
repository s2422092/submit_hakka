from flask import Blueprint, render_template, session, redirect, url_for, flash
import sqlite3
import os

users_home_bp = Blueprint('users_home', __name__, url_prefix='/users_home')

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@users_home_bp.route('/logout')
def logout():
    session.clear()
    flash("ログアウトしました")
    return redirect(url_for('general.explamation'))

@users_home_bp.route('/home')
def home():
    if 'id' not in session:
        flash("ログインしてください")
        return redirect(url_for('users_login.login'))

    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            store_id AS id,
            store_name AS name,
            description
        FROM store
        ORDER BY store_id
    """)
    stores = cursor.fetchall()
    conn.close()

    return render_template('users_home/home.html', stores=stores, u_name=session.get('u_name', 'ゲスト'))

@users_home_bp.route('/map_shop')
def map_shop():
    if 'id' not in session:
        flash("ログインしてください")
        return redirect(url_for('users_login.login'))

    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.store_id, s.store_name, s.description,
               s.email, s.representative,
               l.latitude, l.longitude
        FROM store s
        JOIN locations l ON s.store_id = l.store_id
        ORDER BY s.store_id
    """)

    stores = [
        {
            'id': row[0],
            'store_name': row[1],  # ★ 変更点: 'name' から 'store_name' に変更
            'description': row[2],
            'email': row[3],
            'representative': row[4],
            'lat': row[5],
            'lng': row[6]
        } for row in cursor.fetchall()
    ]

    conn.close()

    u_name = session.get('u_name', 'ゲスト')

    return render_template('users_home/map_shop.html', stores=stores, u_name=u_name)


from collections import defaultdict

@users_home_bp.route('/payment_history')
def payment_history():
    if 'id' not in session:
        flash("ログインしてください")
        return redirect(url_for('users_login.login'))

    user_id = session['id']

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            o.order_id, o.datetime, o.status,
            s.store_name, m.menu_name,
            oi.quantity, oi.price_at_order
        FROM orders AS o
        JOIN order_items AS oi ON o.order_id = oi.order_id
        JOIN menus AS m ON oi.menu_id = m.menu_id
        JOIN store AS s ON o.store_id = s.store_id
        WHERE o.user_id = ?
        ORDER BY o.datetime DESC;
    """
    rows = cursor.execute(query, (user_id,)).fetchall()
    conn.close()

    # grouped by order_id
    grouped_history = {}
    for row in rows:
        order_id = row['order_id']
        if order_id not in grouped_history:
            grouped_history[order_id] = []
        grouped_history[order_id].append({
            'datetime': row['datetime'],
            'status': row['status'],
            'store_name': row['store_name'],
            'menu_name': row['menu_name'],
            'quantity': row['quantity'],
            'price_at_order': row['price_at_order']
        })

    return render_template('users_home/payment_history.html',
                           grouped_history=grouped_history,
                           u_name=session.get('u_name'))


@users_home_bp.route('/details_payment_history/<int:order_id>')
def details_payment_history(order_id):
    if 'id' not in session:
        flash("ログインしてください")
        return redirect(url_for('users_login.login'))

    user_id = session['id']
    u_name = session.get('u_name', 'ゲスト')

    conn = get_db_connection()
    query = """
        SELECT
            o.order_id,
            o.datetime,
            o.total_amount,
            o.status,
            s.store_name,
            m.menu_name,
            oi.quantity,
            oi.price_at_order
        FROM orders AS o
        JOIN store AS s ON o.store_id = s.store_id
        JOIN order_items AS oi ON o.order_id = oi.order_id
        JOIN menus AS m ON oi.menu_id = m.menu_id
        WHERE o.user_id = ? AND o.order_id = ?
        ORDER BY oi.order_item_id ASC;
    """
    payment_details = conn.execute(query, (user_id, order_id)).fetchall()
    conn.close()

    return render_template(
        'users_home/details_payment_history.html',
        u_name=u_name,
        payment_details=payment_details
    )

@users_home_bp.route('/users_data')
def users_data():
    if 'id' not in session:
        flash("ログインしてください")
        return redirect(url_for('users_login.login'))

    u_name = session.get('u_name', 'ゲスト')

    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u_name, email, created_at
        FROM users_table
        WHERE id = ?
    """, (session['id'],))
    user_data = cursor.fetchone()
    conn.close()

    user = None
    if user_data:
        user = {
            'username': user_data[0],
            'email': user_data[1],
            'registration_date': user_data[2]
        }

    return render_template(
        'users_home/users_data.html',
        user=user,
        u_name=u_name
    )