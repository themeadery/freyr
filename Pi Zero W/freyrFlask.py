from flask import Flask, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO
import os
import logging
from logging.handlers import RotatingFileHandler
import sqlite3

app = Flask(__name__)
app.json.sort_keys = False # Don't sort the keys in the JSON response to alphabetical order
socketio = SocketIO(app)

# Set up logging
logging.basicConfig(
    handlers=[RotatingFileHandler('./log/freyrFlask.log', maxBytes=4000000, backupCount=3)],
    level=logging.WARNING, # Set logging level. logging.WARNING = less info
    format='%(asctime)s - %(levelname)s - %(message)s')
logging.warning("Starting freyrFlask") # Throw something in the log on start just so I know everything is working

# Tap into the werkzeug logger
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.WARNING) # Set the logging level to WARNING or higher to reduce output

def read_sqlite_database():
    # Connect to SQLite db
    try:
        database = "./sql/freyr.db"
        logging.info(f"Connecting to SQLite database: {database}")
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
    except sqlite3.Error as e:
        logging.error(f"Couldn't open SQLite database {database}: {e}")
        return jsonify({"error": "Database connection failed"}), 500
    # Read from SQLite db
    try:
        logging.info(f"Reading from SQLite database: {database}")
        result = cursor.execute("SELECT * FROM data ORDER BY rowid DESC LIMIT 1").fetchone()
        logging.info(f"SQLite database {database} read successfully.")
        logging.debug(f"Data: {result}")
    except sqlite3.Error as e:
        logging.error(f"Error reading SQLite database: {e}")
        return jsonify({"error": "Error reading database"}), 500
    finally:
        connection.close()
        logging.info(f"SQLite database {database} closed.")
    # Final error check and return JSON
    if result:
        logging.debug("JSON served successfully.")
        return jsonify({
            "time": result[0],
            "epoch": result[1],
            "outdoorTemp": result[2],
            "outdoorDewpoint": result[3],
            "outdoorHumidity": result[4],
            "indoorTemp": result[5],
            "indoorDewpoint": result[6],
            "indoorHumidity": result[7],
            "localPressure": result[8],
            "uv": result[9],
            "wind": result[10],
            "windGust": result[11],
            "indoorGas": result[12],
            "piTemp": result[13],
            "picowTemp": result[14]
        })
    else:
        logging.error("No data found in SQLite database.")
        return jsonify({"error": "No data found"}), 404

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api')
def api():
    return read_sqlite_database()

# Inter-process communication with 'freyr.py'
@app.route('/notify', methods=['POST'])
def notify():
    logging.info("Received notification of new images.")
    socketio.emit('new_images') # Will trigger images in page to refresh
    logging.info("Emitted notification to browser to refresh images.")
    return 'Notified clients', 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
