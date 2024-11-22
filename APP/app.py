from flask import Flask, render_template, Response, jsonify
from flask_cors import CORS
import cv2
import os
import uuid
import time
from ultralytics import YOLO
import psycopg2
from label_mapping import class_mapping
import torch
torch.cuda.empty_cache()


cap = cv2.VideoCapture(1)
app = Flask(__name__)
CORS(app)

# Database connection
conn = psycopg2.connect(database="postgres", user="logesh", password="lo87sh76", host="localhost", port="5432")

# Load YOLOv8 model
model = YOLO(r"C:\Users\logesh\Desktop\bests.pt")


fruit_veg_model = YOLO(r"C:\Users\logesh\Desktop\bestveg.pt")


model.to('cuda')


fruit_veg_model.to('cuda')



# Directory to save captured frames
capture_dir = 'static/captures'
os.makedirs(capture_dir, exist_ok=True)

# Global variables
product_counts = {}
fruit_veg_counts={}
last_capture_time = 0
capture_interval = 7  # Interval in seconds
latest_capture = None
latest_detections = []

@app.route('/video_feed_fruits', methods=['GET'])
def video_feed_fruits():
    return Response(gen_frames_fruit_veg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/class_mapping', methods=['GET'])
def get_class_mapping():
    return jsonify(class_mapping)



@app.route('/get_product_liveness/<detected_class>', methods=['GET'])
def get_product_liveness(detected_class):
    # Get the product liveness from the mapping
    liveness = class_mapping.get(detected_class)

    if liveness is None:
        # Return a 404 error for unknown classes
        return jsonify({"error": "Unknown product class"}), 404

    return jsonify({"detected_class": detected_class, "liveness": liveness})



def gen_frames_fruit_veg():
    global last_capture_time, fruit_veg_counts, latest_capture, latest_detections
 # Ensure the correct camera index

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    while True:
        success, frame = cap.read()
        if not success:
            print("Error: Failed to capture image.")
            break

        frame = cv2.resize(frame, (640, 480))

        current_time = time.time()
        time_since_last_capture = current_time - last_capture_time

        if time_since_last_capture >= capture_interval:
            last_capture_time = current_time

            # Perform detection using the fruit and vegetable model
            results = fruit_veg_model(frame)

            # Save and annotate the frame as needed
            capture_filename = f"capture_fruits_{uuid.uuid4().hex}.png"
            capture_path = os.path.join(capture_dir, capture_filename)
            annotated_frame = results[0].plot()
            cv2.imwrite(capture_path, annotated_frame)

            latest_detections.clear()

            for box in results[0].boxes.data.tolist():
                x1, y1, x2, y2, conf, cls = box
                fruit_class = fruit_veg_model.names[int(cls)]

                # Update the fruit/vegetable count
                if fruit_class in fruit_veg_counts:
                    fruit_veg_counts[fruit_class] += 1
                else:
                    fruit_veg_counts[fruit_class] = 1

                latest_detections.append({
                    'box': [x1, y1, x2, y2],
                    'confidence': conf,
                    'class': fruit_class
                })

            latest_capture = f'/static/captures/{capture_filename}'

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    cap.release()




@app.route('/')
def index():
    return render_template('index.html')



def gen_frames():
    global last_capture_time, product_counts, latest_capture, latest_detections

     # Ensure the correct camera index (0 is for the default webcam)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    while True:
        success, frame = cap.read()
        if not success:
            print("Error: Failed to capture image.")
            break

        # Resize or modify the frame for better performance
        frame = cv2.resize(frame, (640, 480))

        current_time = time.time()
        time_since_last_capture = current_time - last_capture_time

        # Check if it's time to capture and process the frame
        if time_since_last_capture >= capture_interval:
            last_capture_time = current_time

            # Perform YOLO detection
            results = model(frame)

            # Save annotated image
            capture_filename = f"capture_{uuid.uuid4().hex}.png"
            capture_path = os.path.join(capture_dir, capture_filename)
            annotated_frame = results[0].plot()
            cv2.imwrite(capture_path, annotated_frame)

            # Reset detections, but keep the product count persistent
            latest_detections.clear()

            # Process detections
            for box in results[0].boxes.data.tolist():
                x1, y1, x2, y2, conf, cls = box
                product_class = model.names[int(cls)]

                # Update the product count
                if product_class in product_counts:
                    product_counts[product_class] += 1
                else:
                    product_counts[product_class] = 1

                # Store detection details
                latest_detections.append({
                    'box': [x1, y1, x2, y2],
                    'confidence': conf,
                    'class': product_class
                })

            latest_capture = f'/static/captures/{capture_filename}'

        # Encode the frame for streaming (important part for the video feed)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        # Yield the frame in the correct format for the video feed
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    cap.release()


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_latest_capture', methods=['GET'])
def get_latest_capture():
    if latest_capture and latest_detections:
        time_remaining = max(0, int(capture_interval - (time.time() - last_capture_time)))
        return jsonify({
            'image_url': latest_capture,
            'detections': latest_detections,
            'time_remaining': time_remaining
        })
    else:
        time_remaining = max(0, int(capture_interval - (time.time() - last_capture_time)))
        return jsonify({
            'message': 'Waiting for next capture',
            'time_remaining': time_remaining
        })

@app.route('/get_product_counts/<class_name>', methods=['GET'])
def get_product_counts(class_name):
    """Fetch product count details for a given class from the database."""
    try:
        cur = conn.cursor()
        query = """
        SELECT p.product_name, p.brand_name
        FROM products p
        JOIN product_classes pc ON p.product_id = pc.product_id
        WHERE pc.class_name = %s;
        """
        cur.execute(query, (class_name,))
        product_details = cur.fetchone()

        if not product_details:
            return jsonify({'message': 'Product not found'}), 404

        product_name, brand_name = product_details
        count = product_counts.get(class_name, 0)

        return jsonify({'product': f"{product_name} ({brand_name})", 'count': count})

    except Exception as e:
        print(f"Error fetching product count details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_product_count_details/<class_name>', methods=['GET'])
def get_product_count_details(class_name):
    """Fetch product count details for a given class from the database."""
    try:
        cur = conn.cursor()
        query = """
        SELECT p.product_name, p.brand_name
        FROM products p
        JOIN product_classes pc ON p.product_id = pc.product_id
        WHERE pc.class_name = %s;
        """
        cur.execute(query, (class_name,))
        product_details = cur.fetchone()

        if not product_details:
            return jsonify({'message': 'Product not found'}), 404

        # Extract product name and brand
        product_name, brand_name = product_details

        # Get the current count of the product from the in-memory product_counts dictionary
        count = product_counts.get(class_name, 0)

        # Return product name, brand, and count as JSON
        return jsonify({
            'product_name': product_name,
            'brand_name': brand_name,
            'count': count
        })

    except Exception as e:
        print(f"Error fetching product count details: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()

@app.route('/get_product_details/<class_name>', methods=['GET'])
def get_product_details(class_name):
    """Fetch product details for a given class from the database."""
    try:
        cur = conn.cursor()
        query = """
        SELECT p.product_id, p.product_name, p.brand_name, p.mfg_date, p.use_before, p.mrp, p.net_weight
        FROM products p
        JOIN product_classes pc ON p.product_id = pc.product_id
        WHERE pc.class_name = %s;
        """
        cur.execute(query, (class_name,))
        product_details = cur.fetchone()

        if product_details:
            mfg_date = product_details[3].strftime('%Y-%m-%d')
            use_before = product_details[4].strftime('%Y-%m-%d')

            return jsonify({
                'product_id': product_details[0],
                'product_name': product_details[1],
                'brand': product_details[2],
                'mfg_date': mfg_date,
                'use_before': use_before,
                'mrp': str(product_details[5]),
                'net_weight': product_details[6]
            })

        return jsonify({'error': 'Product not found'}), 404

    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()
        return jsonify({'error': 'Database query failed'}), 500

    finally:
        cur.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
