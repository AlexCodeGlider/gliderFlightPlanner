from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
import folium
from folium.features import DivIcon
import numpy as np
from math import radians, cos, sin, asin, sqrt, degrees, atan2
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import csv
import ast
import json
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Set the secret key to some random bytes for session encryption
app.secret_key = os.environ.get('SECRET_KEY')

# Use filesystem session type for demonstration purposes
app.config['SESSION_TYPE'] = 'filesystem'

Session(app)

def glide_range(altitude, arrival_altitude, glide_ratio, safety_margin, Vg, wind_speed, wind_direction, heading):
    """
    Calculate the glide range of an aircraft in the presence of wind.

    Parameters:
    altitude (float): The initial altitude from which the aircraft starts to glide in feet.
    arrival_altitude (float): The arrival altitude at the center location in feet.
    glide_ratio (float): The glide ratio of the aircraft.
    Vg (float): The glide speed of the aircraft in still air in knots.
    wind_speed (float): The speed of the wind in knots.
    wind_direction (float): The direction from which the wind is coming, in degrees.
    heading (float): The heading of the aircraft, in degrees.

    Returns:
    float: The glide range of the aircraft in nautical miles from the initial altitude
      from which the aircraft starts to glide to the arrival altitude.
    """
    initial_altitude = altitude - arrival_altitude

    # Convert speeds from knots to feet/s
    Vg = Vg * 1.68781
    wind_speed = wind_speed * 1.68781

    # Reverse wind direction
    wind_direction = (wind_direction + 180) % 360

    # Calculate the difference between the wind direction and the heading
    angle_diff = np.radians(wind_direction - heading)

    # Calculate the effective wind speed
    Vw = wind_speed * np.cos(angle_diff)

    safety_margin = 1 - safety_margin

    # Set a minimum safety margin to avoid multiplying by zero
    MIN_SAFETY_MARGIN = 0.01
    safety_margin = max(safety_margin, MIN_SAFETY_MARGIN)

    # Calculate the glide ratio in the presence of wind
    glide_ratio_wind = ((Vg - Vw) / Vg) * glide_ratio * safety_margin

    # Calculate the glide range in feet
    glide_range_wind_ft = initial_altitude * glide_ratio_wind

    # Convert the glide range to nautical miles
    glide_range_wind_nm = glide_range_wind_ft / 6076.12

    return glide_range_wind_nm

def haversine(lon1, lat1, d, brng):
    """
    Calculate the new coordinates given a starting point, distance and bearing
    """
    R = 3440.069 #Radius of the Earth in nautical miles
    brng = radians(brng) #convert bearing to radians

    lat1 = radians(lat1) #Current lat point converted to radians
    lon1 = radians(lon1) #Current long point converted to radians

    lat2 = asin( sin(lat1)*cos(d/R) + cos(lat1)*sin(d/R)*cos(brng) )

    lon2 = lon1 + atan2(sin(brng)*sin(d/R)*cos(lat1), cos(d/R)-sin(lat1)*sin(lat2))

    lat2 = degrees(lat2)
    lon2 = degrees(lon2)

    return [lat2, lon2]

def plot_map(lat1, lon1, glide_ratio, safety_margin, Vg, center_locations, polygon_altitudes, arrival_altitude_agl):
    m = folium.Map(location=[lat1, lon1], tiles=None, zoom_start=10)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satellite', overlay=False, control=True).add_to(m)
    folium.TileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Topographic', overlay=False, control=True).add_to(m)
    folium.TileLayer('https://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw', name='FAA Sectional Chart', attr="ChartBundle").add_to(m)
    folium.LayerControl().add_to(m)

    for altitude in polygon_altitudes:
        polygons_points = []

        for lat, lon, polygon_altitude, wind_speed, wind_direction, arrival_altitude_msl, name, type, description in center_locations:
            folium.Marker(
                location=[lat, lon],
                popup=f"{name}\nType: {type}\nArrival Alt: {arrival_altitude_msl}ft\nLocation Alt: {arrival_altitude_msl-arrival_altitude_agl}ft\nDescription: {description}",
                icon=folium.Icon(icon="plane-arrival", prefix='fa')
            ).add_to(m)
            # Only calculate the polygon rings for altitudes above arrival altitude and the location type is not a turnpoint
            if altitude >= arrival_altitude_msl and type != "T":
                polygon_points = []
                for heading in range(0, 360, 10):
                    range_nm = glide_range(altitude, arrival_altitude_msl, glide_ratio, safety_margin, Vg, wind_speed, wind_direction, heading)
                    new_point = haversine(lon, lat, range_nm, heading)
                    polygon_points.append(new_point)

                polygons_points.append(polygon_points)

        # Merge the polygons using a union operation
        merged_polygon = unary_union([Polygon(polygon_points) for polygon_points in polygons_points])

        # Handle both Polygon and MultiPolygon cases
        merged_polygons = list(merged_polygon.geoms) if isinstance(merged_polygon, MultiPolygon) else [merged_polygon]

        for merged_polygon in merged_polygons:
            # Only proceed if the geometry is a Polygon
            if isinstance(merged_polygon, Polygon):
                # Convert the merged polygon back to a list of points
                merged_polygon_points = [list(point) for point in merged_polygon.exterior.coords]
                # Draw the merged polygon on the map
                folium.Polygon(locations=merged_polygon_points, color='blue', fill=False).add_to(m)

                label_locs = [1, 10, 19, 28] # bearing of the label locations
                for loc in label_locs:
                    # Add a label with the altitude at the label locations
                    folium.Marker(
                      location=merged_polygon_points[loc],
                      icon=DivIcon(
                          icon_size=(150,36),
                          icon_anchor=(0,0),
                          html='<div style="font-size: 12pt; color: yellow; text-shadow: -1px 0 black, 0 1px black, 1px 0 black, 0 -1px black;">%s ft</div>' % (altitude),
                      )
                    ).add_to(m)
    return m.get_root().render()

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

GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS')
GMAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD')

def send_email(to_email, subject, content):
    """Send email using SMTP."""
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = subject
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = to_email

    # Connect to Gmail's SMTP server
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
        server.send_message(msg)

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
    return redirect(url_for('contact_us'))

if __name__ == "__main__":
    app.run(debug=True)
