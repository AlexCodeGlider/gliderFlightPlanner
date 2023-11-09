from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
import numpy as np
import csv
import ast
import json
import os
from utils import plot_map, send_email, GMAIL_ADDRESS
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Set the secret key to some random bytes for session encryption
app.secret_key = os.environ.get('SECRET_KEY')

# Use filesystem session type for demonstration purposes
app.config['SESSION_TYPE'] = 'filesystem'

Session(app)

@app.route('/')
def home():
    if 'agreed_to_terms' in session:
        return redirect(url_for('index'))
    else:
        return redirect(url_for('welcome'))

@app.route('/welcome', methods=['GET', 'POST'])
def welcome():
    if request.method == 'POST':
        if 'agree_terms' in request.form:  # Check if the checkbox is checked
            # User has agreed to terms and conditions
            session['agreed_to_terms'] = True
            return redirect(url_for('index'))
    return render_template('welcome.html')

@app.route("/index", methods=["GET", "POST"])
def index():
    if not session.get('agreed_to_terms'):
        return redirect(url_for('welcome'))
    
    data = []

    # Define the mapping for the Type column
    type_mapping = {
        'A': 'Airfield',
        'T': 'Turnpoint',
        'TA': 'Airfield/Turnpoint',
        'TL': 'Landable/Turnpoint',
        'AT': 'Airfield/Turnpoint',
        'L': 'Landable',
        'AL': 'Airport/Landable'
    }

    # Load data from CSV
    with open('data/enriched_locations.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Replace the value in the Type column using the mapping
            row['Type'] = type_mapping.get(row['Type'], row['Type'])
            data.append(row)

    # Load gliders data from the JSON file
    with open('data/gliders.json', 'r') as file:
        gliders = json.load(file)

    # Sort the gliders alphabetically by make and model
    gliders.sort(key=lambda glider: glider['make'] + " " + glider['model'])

    if request.method == "POST":
        # Extract selected rows from the table
        selected_rows = request.form.getlist('selectedRows[]')
        
        selected_glider = request.form['gliderSelection']
        if selected_glider != "other":
            for glider in gliders:
                selected_glider_name = glider['make'] + " " + glider['model']
                if selected_glider_name == selected_glider:
                    glide_ratio = float(glider['glide_ratio'])
                    vg = float(glider['vg'])
                    break
        else:
            glide_ratio = float(request.form['glideRatio'])
            vg = float(request.form['vg'])


        # Extract new form data
        wind_direction = float(request.form['windDirection'])
        wind_speed = float(request.form['windSpeed'])
        safety_margin = float(request.form['safetyMargin']) / 100
        location_names = request.form.getlist('locationName[]')
        altitudes = request.form.getlist('altitude[]')
        latitudes = request.form.getlist('latitude[]')
        longitudes = request.form.getlist('longitude[]')
        arrival_altitude = float(request.form['arrivalAltitude'])
        ring_spacing = request.form['ringSpacingSelection']

        # Create a form data dictionary
        form_data = {
            'selected_rows': [selected_rows],
            'glide_ratio': glide_ratio,
            'safety_margin': safety_margin,
            'vg': vg,
            'wind_speed': wind_speed,
            'wind_direction': wind_direction,
            'location_names': location_names,
            'altitudes': altitudes,
            'latitudes': latitudes,
            'longitudes': longitudes,
            'arrival_altitude': arrival_altitude,
            'ring_spacing': ring_spacing
        }
        
        return redirect(url_for('map_page', **form_data))

    return render_template("index.html", data=data, gliders_json=gliders)

@app.route('/user-guide')
def user_guide():
    return render_template('user_guide.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route("/map", methods=["GET"])
def map_page():
    data = []
    selected_rows_str = request.args.get('selected_rows')
    selected_rows = ast.literal_eval(selected_rows_str)
    wind_direction = float(request.args.get('wind_direction'))
    wind_speed = float(request.args.get('wind_speed'))
    arrival_altitude_agl = float(request.args.get('arrival_altitude'))
    ring_spacing = request.args.get('ring_spacing')
    
    # Retrieve dynamic form fields
    location_names = request.args.getlist('location_names')
    altitudes = request.args.getlist('altitudes')
    latitudes = request.args.getlist('latitudes')
    longitudes = request.args.getlist('longitudes')

    # Load data from CSV
    with open('data/Crystal23.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            data.append(row)
    
    # Define the altitude range
    min_altitude = 2000
    max_altitude = 18000

    if ring_spacing == 'thousands':
        polygon_altitudes = np.arange(min_altitude, max_altitude + 1000, 1000)
    elif ring_spacing == 'evenThousands':
        polygon_altitudes = np.arange(min_altitude, max_altitude + 1000, 2000)
    elif ring_spacing == 'oddThousands':
        # Start from the first odd thousand (3000) since 2000 is even
        polygon_altitudes = np.arange(min_altitude + 1000, max_altitude + 1000, 2000)

    center_locations =[]

    for polygon_altitude in polygon_altitudes:
        for row in data:
            if row['ID'] in selected_rows:
                center_locations.append(
                    (
                        float(row['Lat']), 
                        float(row['Long']), 
                        float(polygon_altitude), 
                        wind_speed, 
                        wind_direction,
                        float(row['Altitude']) + arrival_altitude_agl, # Add arrival altitude AGL to the center location altitude
                        row['Name'],
                        row['Type'],
                        row['Description']
                        )
                    )
                
    # Append additional center locations
    for i in range(len(location_names)):
        # Check if any field in the current row is empty
        if not (location_names[i] and altitudes[i] and latitudes[i] and longitudes[i]):
            continue  # Skip processing this row if any field is empty
        for polygon_altitude in polygon_altitudes:
            center_locations.append(
                (
                    float(latitudes[i]),
                    float(longitudes[i]),
                    float(polygon_altitude),
                    wind_speed,
                    wind_direction,
                    float(altitudes[i]) + arrival_altitude_agl,  # Add arrival altitude AGL to the center location altitude
                    location_names[i],
                    "A",  # Type for custom locations
                    "User-defined location"  # Description for custom locations
                )
            )
    
    # Initialize total latitude and longitude to zero
    total_lat = 0
    total_lon = 0

    # Iterate over the center locations
    for location in center_locations:
        total_lat += location[0]
        total_lon += location[1]

    # Calculate the average latitude and longitude
    avg_lat = total_lat / len(center_locations)
    avg_lon = total_lon / len(center_locations)

    # Retrieve form parameters from request arguments
    glide_ratio = float(request.args.get('glide_ratio'))
    safety_margin = float(request.args.get('safety_margin'))
    vg = float(request.args.get('vg'))
    
    # Generate the map using the form parameters
    map_html = plot_map(
        avg_lat, 
        avg_lon,
        glide_ratio,
        safety_margin,
        vg,
        center_locations,
        polygon_altitudes,
        arrival_altitude_agl
        ) 

    return render_template("map.html", map_html=map_html)

@app.route('/about-us')
def about_us():
    return render_template('about_us.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/contact-us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/submit_contact_form', methods=['POST'])
def submit_contact_form():
    # Extract form data
    name = request.form.get('name')
    email = request.form.get('email')
    message_content = request.form.get('message')

    # Send email
    subject = "[GliderFlightPlanner] New Contact Form Submission"
    content = f"Name: {name}\nEmail: {email}\nMessage: {message_content}"
    send_email(GMAIL_ADDRESS, subject, content)

    # Provide feedback to the user
    flash('Thank you for reaching out! We will get back to you as soon as possible.', 'success')

    # Redirect to the Contact Us page
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
