# routes/general/explamation.py
from flask import Blueprint, render_template

general_bp = Blueprint('general', __name__, url_prefix='/general')

@general_bp.route('/explamation')##ここでリンクの指定ただしhttp://localhost:5003/general/explamationこのリンクの/explamationここを指定
##そしてgeneral_bp = Blueprint('general', __name__, url_prefix='/general')ここのurl_prefix='/general'ここで/generalこれをしてしている
def explamation():
    ## render_template('general/explamation.html')ここでtemplateの中にあるデレクトリ名とファイル名を記述
    return render_template('general/explamation.html')
