from flask import Flask, render_template_string
import subprocess

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        body {
            background-color: rgb(24, 25, 26);
            color: white;
        }
        </style>
        </head>
        <body>
            <input type="button" value=" Relay On " onclick="relayOn()">
            <input type="button" value=" Relay Off " onclick="relayOff()">

            <script src="https://code.jquery.com/jquery-3.7.0.min.js" integrity="sha256-2Pmvv0kuTBOenSvLm6bvfBSSHrUJ+3A7x6P5Ebd07/g=" crossorigin="anonymous"></script>

            <script>
                function relayOn(){
                    $.ajax({
                    url: "relayOn",
                    context: document.body
                    });
                }
            </script>
            <script>
                function relayOff(){
                    $.ajax({
                    url: "relayOff",
                    context: document.body
                    });
                }
            </script>
        </body>
        </html>
         ''')

@app.route('/relayOn/')
def relay_on_function():
    subprocess.run(["python", "relayOn.py"])
    return 'OK.'

@app.route('/relayOff/')
def relay_off_function():
    subprocess.run(["python", "relayOff.py"])
    return 'OK.'

if __name__ == '__main__':
    app.run(host='0.0.0.0')
