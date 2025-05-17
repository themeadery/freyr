from flask import Flask, jsonify, render_template, send_from_directory
import os
import logging
from logging.handlers import RotatingFileHandler
import sqlite3

app = Flask(__name__)
app.json.sort_keys = False # Don't sort the keys in the JSON response to alphabetical order

# Set up logging
logging.basicConfig(
    handlers=[RotatingFileHandler('./log/freyrFlask.log', maxBytes=4000000, backupCount=3)],
    level=logging.DEBUG, # Set logging level. logging.WARNING = less info
    format='%(asctime)s - %(levelname)s - %(message)s')
logging.warning("Starting API") # Throw something in the log on start just so I know everything is working

def read_sqlite_database():
    # Connect to SQLite db
    try:
        database = "freyr.db"
        logging.info(f"Connecting to SQLite database: {database}")
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
    except sqlite3.Error as e:
        logging.error(f"Couldn't open SQLite database {database}: {e}")
        return jsonify({"error": "Database connection failed"}), 500
    # Read from SQLite db
    try:
        logging.info(f"Reading from SQLite database: {database}")
        result = cursor.execute("SELECT * FROM data ORDER BY time DESC LIMIT 1").fetchone()
        logging.info(f"SQLite database {database} read successfully.")
        logging.debug(f"Data: {result}")
    except sqlite3.Error as e:
        logging.error(f"Error reading SQLite database: {e}")
        return jsonify({"error": "Error reading database"}), 500
    finally:
        cursor.close()
        connection.close()
        logging.info(f"SQLite database {database} closed.")
    # Final error check and return JSON
    if result:
        logging.debug("JSON served successfully.")
        return jsonify({
            "time": result[0],
            "outdoorTemp": result[1],
            "outdoorDewpoint": result[2],
            "outdoorHumidity": result[3],
            "indoorTemp": result[4],
            "indoorDewpoint": result[5],
            "indoorHumidity": result[6],
            "localPressure": result[7]
        })
    else:
        logging.error("No data found in SQLite database.")
        return jsonify({"error": "No data found"}), 404

@app.route('/api')
def api():
    return read_sqlite_database()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
