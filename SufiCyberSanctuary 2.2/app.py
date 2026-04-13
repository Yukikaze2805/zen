from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "test123456"

# 本地内存存留言（重启消失，不影响测试）
messages = []

# 订阅者列表
subscribers = []

# ------------------- 页面路由 -------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shrine')
def shrine():
    return render_template('shrine.html')

# ------------------- 留言提交接口 -------------------
@app.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json()
    name = data.get("name", "匿名信眾")
    content = data.get("content")

    if not content:
        return jsonify({"error": "請輸入內容"}), 400

    messages.insert(0, {
        "id": len(messages) + 1,
        "name": name,
        "content": content,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return jsonify({"message": "呈送成功"}), 200

# ------------------- 邮箱订阅接口 -------------------
@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "請輸入郵箱地址"}), 400

    # 简单的邮箱格式验证
    import re
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({"error": "郵箱格式不正確"}), 400

    # 检查是否已经订阅
    for subscriber in subscribers:
        if subscriber['email'] == email:
            return jsonify({"error": "此郵箱已訂閱"}), 400

    subscribers.insert(0, {
        "id": len(subscribers) + 1,
        "email": email,
        "subscribe_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({"message": "訂閱成功"}), 200

# ------------------- 后台 -------------------
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == '123456':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html', messages=messages, subscribers=subscribers)

@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ------------------- 启动 -------------------
if __name__ == '__main__':
    app.run(debug=True)