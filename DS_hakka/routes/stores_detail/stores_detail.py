# --- 必要なライブラリのインポート ---
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3
import csv
from werkzeug.utils import secure_filename
import os
from functools import wraps
import io
import json
import pandas as pd
from datetime import datetime, date

# --- Blueprint の定義（URLのプレフィックス /stores を付与）---
stores_detail_bp = Blueprint('stores_detail', __name__, url_prefix='/stores')

# --- DB接続関数（共通処理）---
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 行を辞書形式で取得
    return conn

# --- 店舗用ホーム画面（ログイン必須）---
@stores_detail_bp.route('/store_home')
def store_home():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_id = session['store_id']
    store_name = session.get('store_name', 'ゲスト')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 商品ごとの売上金額合計を取得
    cursor.execute("""
        SELECT m.menu_name, m.category, oi.price_at_order, quantity,
               SUM(oi.quantity * oi.price_at_order) AS total_sales
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN menus m ON oi.menu_id = m.menu_id
        WHERE o.store_id = ? AND o.status != 'canceled'
        GROUP BY m.menu_name, m.category
        ORDER BY total_sales DESC
    """, (store_id,))
    product_sales = cursor.fetchall()

    # 本日の売上と注文数
    today_str = date.today().isoformat()
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) AS daily_sales,
               COUNT(*) AS daily_orders
        FROM orders
        WHERE store_id = ? AND DATE(datetime) = ? AND status != 'canceled'
    """, (store_id, today_str))
    today_stats = cursor.fetchone()
    daily_sales = today_stats['daily_sales']
    daily_orders = today_stats['daily_orders']

    # 今月の売上
    first_day_of_month = date.today().replace(day=1).isoformat()
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) AS monthly_sales
        FROM orders
        WHERE store_id = ? AND DATE(datetime) >= ? AND status != 'canceled'
    """, (store_id, first_day_of_month))
    monthly_sales = cursor.fetchone()['monthly_sales']

    conn.close()

    return render_template(
        'stores_detail/store_home.html',
        store_name=store_name,
        product_sales=product_sales,
        daily_sales=f"{daily_sales:,}",
        daily_orders=f"{daily_orders:,}",
        monthly_sales=f"{monthly_sales:,}"
    )

# --- 店舗メニュー一覧表示 ---
@stores_detail_bp.route('/store_home_menu')
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

    return render_template('stores_detail/store_home_menu.html', store_name=store_name, menus=menus,menu_items=menu_items, categories=categories)


# --- ヘルパー関数（CSV/Excelファイルを読み込む）---
def parse_menu_file(file):
    filename = file.filename
    menus = []
    
    try:
        # CSVファイル処理
        if filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
            csv_data = csv.DictReader(stream)
            required_headers = {'menu_name', 'price'}
            if not required_headers.issubset(set(csv_data.fieldnames or [])):
                return None, f'CSVヘッダーが無効です。必須ヘッダー({", ".join(required_headers)})がありません。'
            menus = list(csv_data)

        # Excelファイル処理
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file.stream, dtype=str)
            required_headers = {'menu_name', 'price'}
            if not required_headers.issubset(set(df.columns)):
                return None, f'Excelヘッダーが無効です。必須ヘッダー({", ".join(required_headers)})がありません。'
            df['category'] = df['category'].fillna('')
            df['soldout'] = df['soldout'].fillna('0')
            menus = df.to_dict('records')
        else:
            return None, '対応していないファイル形式です。.csvまたは.xlsxファイルをアップロードしてください。'
        
        return menus, None
    except Exception as e:
        return None, f"ファイルの読み込み中にエラーが発生しました: {e}"

# --- メニューデータのバリデーション ---
def validate_menu_data(menus_data):
    validated_menus = []
    errors = []
    for i, row in enumerate(menus_data):
        row_num_str = f"行 {i+2}" if len(menus_data) > 1 else "手動入力"
        
        menu_name = row.get('menu_name')
        price_str = str(row.get('price', '')).strip()
        soldout_str = str(row.get('soldout', '0')).strip()
        category = row.get('category', '')

        # 必須項目チェック
        if not menu_name or not price_str:
            errors.append(f"{row_num_str}: 必須項目 (menu_name, price) が空です。")
            continue

        # 価格チェック
        try:
            price = int(float(price_str))
            if price < 0:
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f"{row_num_str}: 価格の値 ('{price_str}') が不正です。0以上の数値を入力してください。")
            continue

        # 売り切れフラグチェック
        try:
            soldout = int(float(soldout_str))
            if soldout not in [0, 1]:
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f"{row_num_str}: 在庫の値 ('{soldout_str}') が不正です。0 (販売中) か 1 (売り切れ) で入力してください。")
            continue

        validated_menus.append({
            'menu_name': menu_name,
            'category': category,
            'price': price,
            'soldout': soldout
        })
    return validated_menus, errors

# --- Excelテンプレートをダウンロードさせるルート ---
@stores_detail_bp.route('/download-template')
def download_template():
    try:
        # テンプレート用データ
        template_data = {
            'menu_name': ['日替わり弁当', '唐揚げ単品', '緑茶'],
            'category': ['お弁当', '惣菜', 'ドリンク'],
            'price': [800, 350, 150],
            'soldout': [0, 0, 1]
        }
        df = pd.DataFrame(template_data)

        # Excelファイルをメモリに生成
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name='メニュー')
        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='menu_template.xlsx'
        )
    except Exception as e:
        flash(f"テンプレートファイルの生成中にエラーが発生しました: {e}", "error")
        return redirect(url_for('stores_detail.menu_registration'))

# --- メニュー登録画面（表示）---
@stores_detail_bp.route('/menu_registration', methods=['GET'])
def menu_registration():
    if 'store_id' not in session:
        flash("ログインしてください", "warning")
        return redirect(url_for('store.store_login'))

    store_id = session['store_id']
    store_name = session.get('store_name', 'ゲスト')

    # 既存メニューをDBから取得
    conn = get_db_connection()
    try:
        existing_menus = conn.execute(
            "SELECT menu_id, menu_name, category, price, soldout FROM menus WHERE store_id = ? ORDER BY menu_id DESC",
            (store_id,)
        ).fetchall()
    except sqlite3.Error as e:
        flash(f"メニューの読み込み中にエラーが発生しました: {e}", "error")
        existing_menus = []
    finally:
        conn.close()

    return render_template('stores_detail/menu_registration.html', store_name=store_name, menus=[dict(row) for row in existing_menus])

# --- メニューのプレビュー処理（アップロード or 手動） ---
@stores_detail_bp.route('/menu-preview', methods=['POST'])
def menu_preview():
    if 'store_id' not in session:
        flash("ログインしてください", "warning")
        return redirect(url_for('store.store_login'))

    menus_to_check = []
    errors = []
    file = request.files.get('product_csv')

    # ファイルアップロードされた場合
    if file and file.filename:
        menus_data, file_error = parse_menu_file(file)
        if file_error:
            flash(file_error, 'error')
            return redirect(url_for('stores_detail.menu_registration'))
        menus_to_check, errors = validate_menu_data(menus_data)

    # 手動入力の場合
    else:
        product_name = request.form.get('product_name')
        product_price_str = request.form.get('product_price')

        if product_name or product_price_str:
            if not product_name or not product_price_str:
                flash('手動で入力する場合、商品名と値段の両方が必須です。', 'error')
                return redirect(url_for('stores_detail.menu_registration'))
            
            manual_data = [{
                'menu_name': product_name,
                'price': product_price_str,
                'category': request.form.get('product_description', ''),
                'soldout': '0'
            }]
            menus_to_check, errors = validate_menu_data(manual_data)
        else:
            flash('登録するデータをアップロードするか、フォームに入力してください。', 'error')
            return redirect(url_for('stores_detail.menu_registration'))

    if errors:
        for error in errors:
            flash(error, 'warning')
        if not menus_to_check:
            flash('有効なデータがなかったため、プレビューできませんでした。', 'error')
            return redirect(url_for('stores_detail.menu_registration'))

    if not menus_to_check:
        flash('登録するデータがありません。', 'info')
        return redirect(url_for('stores_detail.menu_registration'))

    # 一時的にセッションに保存して次画面へ
    session['menus_to_confirm'] = menus_to_check
    return redirect(url_for('stores_detail.menu_check'))

# --- メニュー確認画面 ---
@stores_detail_bp.route('/menu-check', methods=['GET'])
def menu_check():
    if 'store_id' not in session:
        flash("ログインしてください", "warning")
        return redirect(url_for('store.store_login'))

    menus_to_check = session.get('menus_to_confirm', [])
    if not menus_to_check:
        flash('確認するメニューがありません。登録画面からやり直してください。', 'info')
        return redirect(url_for('stores_detail.menu_registration'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_detail/menu_check.html', store_name=store_name, menus_to_check=menus_to_check)

# --- メニュー最終登録処理 ---
@stores_detail_bp.route('/menu-finalize', methods=['POST'])
def menu_finalize():
    if 'store_id' not in session:
        flash("ログインしてください", "warning")
        return redirect(url_for('store.store_login'))

    store_id = session['store_id']
    menus_data_str = request.form.get('menus_data')

    if not menus_data_str:
        flash('登録データが見つかりませんでした。', 'error')
        return redirect(url_for('stores_detail.menu_registration'))

    try:
        menus_to_insert = json.loads(menus_data_str)
    except json.JSONDecodeError:
        flash('登録データの形式が不正です。', 'error')
        return redirect(url_for('stores_detail.menu_registration'))

    # DBにデータ挿入
    conn = get_db_connection()
    cursor = conn.cursor()
    inserted_count = 0
    try:
        for menu in menus_to_insert:
            cursor.execute(
                "INSERT INTO menus (store_id, menu_name, category, price, soldout) VALUES (?, ?, ?, ?, ?)",
                (store_id, menu['menu_name'], menu['category'], menu['price'], menu['soldout'])
            )
            inserted_count += 1
        conn.commit()
        flash(f'{inserted_count}件のメニューを登録しました。', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"データベースへの登録中にエラーが発生しました: {e}", "error")
    finally:
        conn.close()
        session.pop('menus_to_confirm', None)

    return redirect(url_for('stores_detail.menu_registration'))

# --- メニュー削除処理 ---
@stores_detail_bp.route('/menu-delete/<int:menu_id>', methods=['POST'])
def menu_delete(menu_id):
    if 'store_id' not in session:
        flash("ログインしてください", "warning")
        return redirect(url_for('store.store_login'))

    store_id = session['store_id']
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM menus WHERE menu_id = ? AND store_id = ?", (menu_id, store_id))
        conn.commit()
        if cursor.rowcount > 0:
            flash("メニューを削除しました。", "success")
        else:
            flash("削除対象のメニューが見つからないか、権限がありません。", "error")
    except sqlite3.Error as e:
        flash(f"削除中にエラーが発生しました: {e}", "error")
    finally:
        conn.close()

    return redirect(url_for('stores_detail.menu_registration'))

# --- 注文一覧表示 ---
@stores_detail_bp.route('/order-list')
def order_list():
    store_id = session.get('store_id')
    store_name = session.get('store_name', 'ゲスト')
    
    conn = get_db_connection()
    query = """
        SELECT
            o.order_id, o.datetime, o.total_amount, o.status,
            u.u_name, m.menu_name, oi.quantity, oi.price_at_order
        FROM orders AS o
        JOIN order_items AS oi ON o.order_id = oi.order_id
        JOIN menus AS m ON oi.menu_id = m.menu_id
        JOIN users_table AS u ON o.user_id = u.id
        WHERE o.store_id = ?
        ORDER BY o.datetime DESC;
    """
    orders_raw = conn.execute(query, (store_id,)).fetchall()
    conn.close()

    orders_dict = {}
    for row in orders_raw:
        order_id = row['order_id']
        if order_id not in orders_dict:
            orders_dict[order_id] = {
                'id': order_id, 'datetime': row['datetime'], 'status': row['status'],
                'user_name': row['u_name'], 'total_amount': row['total_amount'],
                'items_list': [] # ★★★ キー名を'items'から'items_list'に変更 ★★★
            }
        orders_dict[order_id]['items_list'].append({
            'name': row['menu_name'], 'quantity': row['quantity'], 'price': row['price_at_order']
        })
    
    orders_list = list(orders_dict.values())
    return render_template('stores_detail/order_list.html', orders=orders_list, store_name=store_name)

@stores_detail_bp.route('/update-order-status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    new_status = request.form.get('status')
    valid_statuses = ['注文受付中', '受付完了', '商品作成中', '作成直前', '受け取り待ち', 'completed', 'canceled']

    if new_status not in valid_statuses:
        flash("無効なステータスです")
        return redirect(url_for('stores_detail.order_list'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    flash("注文ステータスを更新しました")
    return redirect(url_for('stores_detail.order_list'))


# --- 操作手順ページ表示 ---
@stores_detail_bp.route('/procedure')
def procedure():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_detail/procedure.html', store_name=store_name)

# --- PayPay連携画面表示 ---
@stores_detail_bp.route('/paypay_linking')
def paypay_linking():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')
    return render_template('stores_detail/paypay_linking.html', store_name=store_name)

# --- 店舗情報表示 ---
@stores_detail_bp.route('/store_info')
def store_info():
    if 'store_id' not in session:
        flash("ログインしてください")
        return redirect(url_for('store.store_login'))

    store_name = session.get('store_name', 'ゲスト')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT store_name, email, location, representative, description, created_at FROM store WHERE store_id = ?", (session['store_id'],))
    store_data = cur.fetchone()
    conn.close()

    return render_template('stores_detail/store_info.html', store_name=store_name, store_data=store_data)