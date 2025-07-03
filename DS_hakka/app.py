from __init__ import create_app

app = create_app()


# 🔒 セッションなどに必要なシークレットキーを設定
app.secret_key = 'your_secret_key_here'  # ← 好きなランダムな文字列でOK


if __name__ == '__main__':
    print("アクセスURL: http://localhost:5003/general/explamation")
    app.run(debug=True, port=5003)