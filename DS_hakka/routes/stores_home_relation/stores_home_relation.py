from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
import sqlite3
from geopy.geocoders import Nominatim
import os

stores_home_relation_bp = Blueprint('stores_home_relation', __name__, url_prefix='/stores_home_relation')


def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 行を辞書形式で取得
    return conn


@stores_home_relation_bp.route('/store_home_menu')
def store_home_menu():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    store_id = session.get('store_id')

    # DBからメニューを取得
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT menu_name, price, category, soldout FROM menus WHERE store_id = ?", (store_id,))
    menus = cur.fetchall()
    menu_items = conn.execute("SELECT menu_id, menu_name, category, price FROM menus WHERE store_id = ? AND soldout = 0", (store_id,)).fetchall()
    categories = conn.execute("""SELECT DISTINCT category FROM menus WHERE store_id = ? AND soldout = 0""", (store_id,)).fetchall()
    categories = [row['category'] for row in categories if row['category']]  # Noneを除外

    conn.close()

    return render_template('stores_home_relation/store_home_menu.html', store_name=store_name, menus=menus,menu_items=menu_items, categories=categories)



@stores_home_relation_bp.route('/store_analysis')
def store_analysis():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))
    
    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_home_relation/store_analysis.html', store_name=store_name)


@stores_home_relation_bp.route('/store_customer_history')
def store_customer_history():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_home_relation/store_customer_history.html', store_name=store_name)


@stores_home_relation_bp.route('/store_memo')
def store_memo():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_home_relation/store_memo.html', store_name=store_name)


@stores_home_relation_bp.route('/store_other')
def store_other():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_home_relation/store_other.html', store_name=store_name)


@stores_home_relation_bp.route('/store_reservation')
def store_reservation():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_home_relation/store_reservation.html', store_name=store_name)