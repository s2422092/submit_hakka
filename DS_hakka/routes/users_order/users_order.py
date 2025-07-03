# routes/users_order/users_order.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import datetime
from functools import wraps

# --- PayPay関連のインポート ---
import paypayopa
import polling
import uuid
import os
import json
import logging
import time
from dotenv import load_dotenv # .envから環境変数を読み込むため

# --- .envファイルの読み込みとPayPay設定 ---
load_dotenv() # ファイルの先頭、またはPayPay関連コードの直前で一度だけ呼び出す

# ロギング設定 (既存のものがあればそのまま、なければここに追加)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境変数の取得と検証
_DEBUG = os.environ.get("_DEBUG", "False").lower() == "true"
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
MERCHANT_ID = os.environ.get("MERCHANT_ID")
FRONTEND_BASE_URL_FOR_API = os.environ.get("FLASK_APP_BASE_URL", default="http://127.0.0.1:5003")

# PayPay OPA クライアントの初期化
client = paypayopa.Client(
    auth=(API_KEY, API_SECRET),
    production_mode=False) # production_modeをFalseに設定し、サンドボックス環境を使用
client.set_assume_merchant(MERCHANT_ID)

users_order_bp = Blueprint('users_order', __name__, url_prefix='/users_order')

def get_db_connection():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id' not in session:
            flash("この操作にはログインが必要です。")
            return redirect(url_for('users_login.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@users_order_bp.route('/menu/<int:store_id>')
@login_required
def menu(store_id):
    """選択された店舗のメニューページを表示する"""
    session['current_store_id'] = store_id
    
    conn = get_db_connection()
    store = conn.execute("SELECT * FROM store WHERE store_id = ?", (store_id,)).fetchone()
    if store is None:
        flash("指定された店舗は存在しません。")
        conn.close()
        return redirect(url_for('users_home.home'))
    
    menu_items = conn.execute("SELECT menu_id, menu_name, category, price FROM menus WHERE store_id = ? AND soldout = 0", (store_id,)).fetchall()
    categories = conn.execute("""SELECT DISTINCT category FROM menus WHERE store_id = ? AND soldout = 0""", (store_id,)).fetchall()
    categories = [row['category'] for row in categories if row['category']]  # Noneを除外

    conn.close()

    carts = session.get('carts', {})
    current_cart = carts.get(str(store_id), {})

    return render_template(
        'users_order/menu.html',
        store=store,
        menu_items=menu_items,
        cart=current_cart,
        u_name=session.get('u_name', 'ゲスト'),
        categories=categories
    )

@users_order_bp.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    if 'current_store_id' not in session:
        return jsonify({'error': '店舗を選択してください'}), 400
    data = request.get_json()
    try:
        menu_id = int(data['menu_id'])
        quantity = int(data['quantity'])
    except (TypeError, ValueError, KeyError):
        return jsonify({'error': '不正なデータ形式です'}), 400
    store_id = session['current_store_id']
    conn = get_db_connection()
    menu_item = conn.execute("SELECT menu_name, price, store_id FROM menus WHERE menu_id = ?", (menu_id,)).fetchone()
    conn.close()
    if not menu_item or menu_item['store_id'] != store_id:
        return jsonify({'error': '無効な商品です'}), 400
    carts = session.get('carts', {})
    store_id_str, menu_id_str = str(store_id), str(menu_id)
    current_cart = carts.get(store_id_str, {})
    if menu_id_str in current_cart:
        current_cart[menu_id_str]['quantity'] += quantity
    else:
        current_cart[menu_id_str] = {
            'menu_id': menu_id, 'name': menu_item['menu_name'],
            'price': menu_item['price'], 'quantity': quantity
        }
    carts[store_id_str] = current_cart
    session['carts'] = carts
    session.modified = True
    total_items = sum(item['quantity'] for item in current_cart.values())
    return jsonify({'message': 'カートに追加しました', 'cart_count': total_items})

@users_order_bp.route('/cart_confirmation')
@login_required
def cart_confirmation():
    if 'current_store_id' not in session:
        return redirect(url_for('users_home.home'))
    store_id = session['current_store_id']
    carts = session.get('carts', {})
    current_cart = carts.get(str(store_id), {})

    total_quantity = sum(item['quantity'] for item in current_cart.values())
    total_price = sum(item['quantity'] * item['price'] for item in current_cart.values())
    
    conn = get_db_connection()
    store = conn.execute("SELECT store_name FROM store WHERE store_id = ?", (store_id,)).fetchone()
    conn.close()
    if not store:
        return redirect(url_for('users_home.home'))
        
    return render_template(
        'users_order/cart_confirmation.html',
        cart=current_cart,
        total_quantity=total_quantity,
        total_price=total_price,
        store_name=store['store_name'],
        store_id=store_id,
        u_name=session.get('u_name', 'ゲスト')
    )

@users_order_bp.route('/payment_selection')
@login_required
def payment_selection():
    """決済方法選択と最終確認ページ"""
    if 'current_store_id' not in session:
        flash("店舗が選択されていません。")
        return redirect(url_for('users_home.home'))

    store_id = session['current_store_id']
    carts = session.get('carts', {})
    current_cart = carts.get(str(store_id), {})

    if not current_cart:
        flash("カートが空です。")
        return redirect(url_for('users_order.menu', store_id=store_id))

    total_price = sum(item['quantity'] * item['price'] for item in current_cart.values())
    
    conn = get_db_connection()
    store = conn.execute("SELECT store_name FROM store WHERE store_id = ?", (store_id,)).fetchone()
    conn.close()

    # BlueprintのURLプレフィックスとPayPay APIのベースURLを結合して渡す
    paypay_api_base_url = f"{FRONTEND_BASE_URL_FOR_API}{users_order_bp.url_prefix}/paypay"

    return render_template(
        'users_order/payment_selection.html',
        cart=list(current_cart.values()), # JavaScriptで扱いやすいようにリストに変換して渡す
        total_price=total_price,
        store_name=store['store_name'],
        u_name=session.get('u_name', 'ゲスト'),
        paypay_api_base_url=paypay_api_base_url
    )

@users_order_bp.route('/create_order', methods=['POST'])
@login_required
def create_order():
    """
    注文をデータベースに保存する（PayPayとは独立した汎用的な注文作成ルート）。
    このルートをPayPay決済の完了後に利用する場合は、
    決済ステータスの確認後にJavaScriptから呼び出すようにしてください。
    """
    if 'current_store_id' not in session:
        return jsonify({"error": "店舗が選択されていません。"}), 400

    user_id = session['id']
    store_id = session['current_store_id']
    carts = session.get('carts', {})
    current_cart = carts.get(str(store_id), {})

    if not current_cart:
        return jsonify({"error": "カートが空です。"}), 400

    total_price = sum(item['quantity'] * item['price'] for item in current_cart.values())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        current_time = datetime.datetime.now()
        cursor.execute("""
            INSERT INTO orders (user_id, store_id, status, datetime, payment_method, total_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, store_id, 'pending', current_time, 'Unknown', total_price)) # ステータスと決済方法を汎用的に
        
        order_id = cursor.lastrowid

        order_items_data = [
            (order_id, item['menu_id'], item['quantity'], item['price'])
            for item in current_cart.values()
        ]
        
        cursor.executemany("""
            INSERT INTO order_items (order_id, menu_id, quantity, price_at_order)
            VALUES (?, ?, ?, ?)
        """, order_items_data)

        conn.commit()

        # ここで`last_order_id`を設定するのは、このルートを直接呼ぶ場合のため。
        # PayPay決済の場合は後述の`finalize_paypay_order`で設定します。
        session['last_order_id'] = order_id
        session.modified = True
        
        # 注文が完了したので、セッションから現在の店舗のカート情報を削除
        if str(store_id) in session['carts']:
            del session['carts'][str(store_id)]
            session.modified = True
            
        logger.info(f"汎用注文 {order_id} が作成されました。")
        return jsonify({"message": "注文が作成されました。", "order_id": order_id}), 200

    except sqlite3.Error as e:
        conn.rollback()
        logger.exception(f"汎用注文作成中にエラーが発生しました: {e}")
        return jsonify({"error": f"注文処理中にエラーが発生しました: {e}"}), 500
    finally:
        conn.close()

@users_order_bp.route('/clear_cart')
@login_required
def clear_cart():
    """現在選択中の店舗のカートを空にする"""
    if 'current_store_id' in session and 'carts' in session:
        store_id_str = str(session['current_store_id'])
        
        if store_id_str in session['carts']:
            del session['carts'][store_id_str]
            session.modified = True
            flash('現在のカートを空にしました。')
    
    if 'current_store_id' in session:
        return redirect(url_for('users_order.menu', store_id=session['current_store_id']))
    else:
        return redirect(url_for('users_home.home'))
    
@users_order_bp.route('/back_to_home')
@login_required
def back_to_home_and_clear_cart():
    """
    現在の店舗のカート情報をクリアし、ホーム画面に戻るためのルート
    """
    if 'current_store_id' in session:
        store_id_str = str(session['current_store_id'])
        
        if 'carts' in session and store_id_str in session['carts']:
            del session['carts'][store_id_str]
            session.modified = True
    
    session.pop('current_store_id', None)
    
    return redirect(url_for('users_home.home'))

@users_order_bp.route('/update_cart_item', methods=['POST'])
@login_required
def update_cart_item():
    """カート内の商品の数量を更新する"""
    if 'current_store_id' not in session:
        return redirect(url_for('users_home.home'))

    try:
        menu_id_str = request.form['menu_id']
        new_quantity = int(request.form['quantity'])
    except (KeyError, ValueError):
        flash("不正なリクエストです。")
        return redirect(url_for('users_order.cart_confirmation'))

    store_id_str = str(session['current_store_id'])
    carts = session.get('carts', {})

    if store_id_str in carts and menu_id_str in carts[store_id_str]:
        if new_quantity > 0:
            carts[store_id_str][menu_id_str]['quantity'] = new_quantity
            flash("数量を更新しました。")
        else:
            del carts[store_id_str][menu_id_str]
            flash("商品をカートから削除しました。")
        
        session['carts'] = carts
        session.modified = True
    
    return redirect(url_for('users_order.cart_confirmation'))

@users_order_bp.route('/delete_cart_item', methods=['POST'])
@login_required
def delete_cart_item():
    """カートから商品を削除する"""
    if 'current_store_id' not in session:
        return redirect(url_for('users_home.home'))

    try:
        menu_id_str = request.form['menu_id']
    except KeyError:
        flash("不正なリクエストです。")
        return redirect(url_for('users_order.cart_confirmation'))

    store_id_str = str(session['current_store_id'])
    carts = session.get('carts', {})

    if store_id_str in carts and menu_id_str in carts[store_id_str]:
        del carts[store_id_str][menu_id_str]
        session['carts'] = carts
        session.modified = True
        flash("商品をカートから削除しました。")

    return redirect(url_for('users_order.cart_confirmation'))

# --- PayPay関連のAPIエンドポイント ---

@users_order_bp.route('/paypay/create-qr', methods=['POST'])
def create_qr():
    """PayPayのQRコード支払いを生成するエンドポイント"""
    req = request.json
    logger.info(f"Received create-qr request at /users_order/paypay/create-qr: {req}")

    merchant_payment_id = uuid.uuid4().hex

    converted_order_items = []
    for item in req["orderItems"]:
        converted_order_items.append({
            "name": item["name"],
            "quantity": item["quantity"],
            "unitPrice": {
                "amount": item["price"],
                "currency": "JPY"
            }
        })

    payment_details = {
        "merchantPaymentId": merchant_payment_id,
        "codeType": "ORDER_QR",
        "orderItems": converted_order_items,
        "amount": req["amount"],
        "redirectUrl": url_for('users_order.reservation_number', _external=True),
        "redirectType": "WEB_LINK",
    }
    
    try:
        resp = client.Code.create_qr_code(data=payment_details)
        
        logger.info(f"QR code creation response from PayPay: {resp}")

        if resp.get('resultInfo', {}).get('code') == 'SUCCESS' and not resp.get('data', {}).get('url'):
            logger.error(f"PayPay QR code creation succeeded but 'url' field is missing in data. Full response: {json.dumps(resp, indent=2)}")
            return jsonify({"error": "QRコードURLが見つかりません。", "details": resp}), 500

        if _DEBUG:
            logger.info(f"DEBUG: PayPay OPAに送信された支払い詳細: {json.dumps(payment_details, indent=2)}")
        
        # セッションに merchantPaymentId を保存して、ポーリングと注文確定に利用できるようにする
        session['paypay_merchant_payment_id'] = merchant_payment_id
        session.modified = True

        return jsonify(resp)
    except Exception as e:
        logger.exception(f"QRコード作成エラー: {e}")
        return jsonify({"error": "QRコードの作成に失敗しました", "details": str(e)}), 500

def fetch_payment_details(merchant_id):
    """指定されたマーチャントIDの支払い詳細をPayPayから取得するヘルパー関数"""
    try:
        resp = client.Code.get_payment_details(merchant_id)
        logger.debug(f"Fetched payment details for {merchant_id}: {resp}")

        if resp.get('resultInfo', {}).get('code') == 'RATE_LIMIT':
            logger.warning(f"RATE_LIMIT エラー {merchant_id}。リトライします。")
            return 'RATE_LIMIT_ERROR'
        
        if resp.get('data') is None:
            error_code = resp.get('resultInfo', {}).get('code')
            error_message = resp.get('resultInfo', {}).get('message')
            if error_code:
                logger.warning(f"PayPay APIが {merchant_id} にエラーを返しました: {error_code} - {error_message}。保留または一時的な問題と見なします。")
            else:
                logger.warning(f"{merchant_id} の支払い詳細が 'None' データとして返されました。保留または見つからないと見なします。")
            return 'PENDING_NO_DATA'
            
        return resp['data']['status']
    except Exception as e:
        logger.exception(f"{merchant_id} の支払い詳細の取得中にエラーが発生しました: {e}")
        return 'FETCH_ERROR'

@users_order_bp.route('/paypay/order-status/<merch_id>', methods=['GET'])
def order_status(merch_id):
    """
    指定されたマーチャントIDの支払いステータスをポーリングし、結果を返すエンドポイント。
    """
    logger.info(f"注文ステータスを確認中 (マーチャントID: {merch_id})")
    
    status = fetch_payment_details(merch_id)
    if status == 'FETCH_ERROR':
        return jsonify({"error": "支払い詳細の取得に失敗しました。", "status": "FAILED"}), 500
    elif status == 'RATE_LIMIT_ERROR' or status == 'PENDING_NO_DATA':
        return jsonify({"data": {"status": "PENDING"}}), 200
    else:
        return jsonify({"data": {"status": status}}), 200
    
@users_order_bp.route('/finalize_paypay_order', methods=['POST'])
@login_required
def finalize_paypay_order():
    """
    PayPay決済が完了したことを確認した後、注文をデータベースに保存し、
    セッションに`last_order_id`を設定する。
    フロントエンドのポーリングが'COMPLETED'を検出した際に呼び出される。
    """
    user_id = session.get('id')
    store_id = session.get('current_store_id')
    
    if not user_id or not store_id:
        logger.error("finalize_paypay_order: セッションにユーザーIDまたは店舗IDがありません。")
        return jsonify({"error": "セッション情報が見つかりません。再ログインしてください。"}), 401

    carts = session.get('carts', {})
    current_cart = carts.get(str(store_id), {})

    if not current_cart:
        logger.error(f"finalize_paypay_order: 店舗ID {store_id} とユーザー {user_id} のカートが空です。")
        return jsonify({"error": "カートが空です。"}), 400

    total_price = sum(item['quantity'] * item['price'] for item in current_cart.values())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        current_time = datetime.datetime.now()
        cursor.execute("""
            INSERT INTO orders (user_id, store_id, status, datetime, payment_method, total_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, store_id, '注文受付中', current_time, 'PayPay', total_price))
        
        order_id = cursor.lastrowid

        order_items_data = [
            (order_id, item['menu_id'], item['quantity'], item['price'])
            for item in current_cart.values()
        ]
        
        cursor.executemany("""
            INSERT INTO order_items (order_id, menu_id, quantity, price_at_order)
            VALUES (?, ?, ?, ?)
        """, order_items_data)

        conn.commit()

        # 注文が完了したので、セッションから現在の店舗のカート情報を削除
        if str(store_id) in session['carts']:
            del session['carts'][str(store_id)]
            session.modified = True
            
        # 取得した注文IDをセッションに保存
        session['last_order_id'] = order_id
        session.modified = True

        logger.info(f"ユーザー {user_id} の注文 {order_id} がPayPay経由で正常に確定されました。")
        return jsonify({"message": "注文が確定されました。", "order_id": order_id}), 200

    except sqlite3.Error as e:
        conn.rollback()
        logger.exception(f"ユーザー {user_id} の注文確定中にエラーが発生しました: {e}")
        return jsonify({"error": f"注文処理中にエラーが発生しました: {e}"}), 500
    finally:
        conn.close()

@users_order_bp.route('/reservation_number')
@login_required
def reservation_number():
    """予約（注文）番号表示ページ"""
    # セッションからlast_order_idとpaypay_merchant_payment_idを取得し、同時に削除
    order_id = session.get('last_order_id', 'N/A')
    merchant_payment_id = session.get('paypay_merchant_payment_id', 'N/A')

    # 不正アクセス判定だけ pop() で行い、データ表示には get() を使う
    if order_id == 'N/A' and merchant_payment_id == 'N/A':
        flash("不正なアクセスです。")
        return redirect(url_for('users_home.home'))

    # 必要ならここで pop() する（再アクセス時に消す）
    # session.pop('last_order_id', None)
    # session.pop('paypay_merchant_payment_id', None)

    return render_template(
        'users_order/reservation_number.html',
        order_id=order_id,
        merchant_payment_id=merchant_payment_id
    )
