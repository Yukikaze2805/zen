from flask import Flask, render_template

app = Flask(__name__)

# 路由：定義訪問哪個網址顯示哪個文件
@app.route('/')
def index():
    # 返回入口頁面 (templates/index.html)
    return render_template('index.html')

@app.route('/shrine')
def shrine():
    # 返回神宮頁面 (templates/shrine.html)
    return render_template('shrine.html')

if __name__ == '__main__':
    # debug=True 確保您修改代碼後，服務器會自動重啟
    app.run(debug=True)