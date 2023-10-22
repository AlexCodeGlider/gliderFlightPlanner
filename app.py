from flask import Flask, render_template, request, redirect, url_for
import folium
from folium.features import DivIcon
import numpy as np
from math import radians, cos, sin, asin, sqrt, degrees, atan2
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union

app = Flask(__name__)

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

#@title ## Create a new map
def plot_map(lon1, lat1, lon2, lat2, glide_ratio, safety_margin, Vg, center_locations):
    m = folium.Map(location=[lat1, lon1], tiles=None, zoom_start=10)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satellite', overlay=False, control=True).add_to(m)
    folium.TileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Topographic', overlay=False, control=True).add_to(m)
    folium.TileLayer('https://wms.chartbundle.com/tms/1.0.0/sec/{z}/{x}/{y}.png?origin=nw', name='FAA Sectional Chart', attr="ChartBundle").add_to(m)
    folium.LayerControl().add_to(m)

    altitudes = [3000, 5000, 7000, 9000, 11000, 13000, 15000]

    for altitude in altitudes:
        polygons_points = []

        for lat, lon, arrival_altitude, wind_speed, wind_direction in center_locations:
            folium.Marker(
                location=[lat, lon],
                popup=f"Center Location: ({lat}, {lon})\nArrival Altitude: {arrival_altitude}ft",
                icon=folium.Icon(icon="plane-arrival", prefix='fa')
            ).add_to(m)
            # Only calculate the polygon rings for altitudes at least 2,000 feet above arrival altitude
            if altitude >= arrival_altitude + 2000:
                polygon_points = []
                for heading in range(0, 360, 10):
                    range_nm = glide_range(altitude, arrival_altitude, glide_ratio, safety_margin, Vg, wind_speed, wind_direction, heading)
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

                label_locs = [0, 9, 18, 27] # bearing of the label locations
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
    m.fit_bounds([[lat1, lon1], [lat2, lon2]])
    return m.get_root().render()

@app.route("/", methods=["GET", "POST"])
def index():
    map_html = ""
    if request.method == "POST":
        # Extract form values
        lat1 = float(request.form.get('lat1', 34.4847167))
        lon1 = float(request.form.get('lon1', -117.8264528))
        lat2 = float(request.form.get('lat2', 34.5614))
        lon2 = float(request.form.get('lon2', -117.6045))
        glide_ratio = int(request.form.get('glide_ratio', 40))
        safety_margin = float(request.form.get('safety_margin', 0.5))
        Vg = int(request.form.get('Vg', 51))

        # Here, add other form value extractions if needed
        
        # Call plot_map() to generate map HTML string
        map_html = plot_map(
            lat1, 
            lon1, 
            lat2, 
            lon2, 
            glide_ratio, 
            safety_margin, 
            Vg, 
            center_locations=[
                (34.5614, -117.6045, 3000, 10, 0), 
                (34.5614, -117.6045, 5000, 10, 0), 
                (34.5614, -117.6045, 7000, 10, 0), 
                (34.5614, -117.6045, 9000, 10, 0), 
                (34.5614, -117.6045, 11000, 10, 0), 
                (34.5614, -117.6045, 13000, 10, 0), 
                (34.5614, -117.6045, 15000, 10, 0)
                ]
            )

        # Return the generated output or redirect to another page
        # For now, just redirecting back to the form. You can enhance this to display the generated map or any other result.

        return render_template("index.html", map_html=map_html)

    return render_template("index.html", map_html=map_html)

if __name__ == "__main__":
    app.run(debug=True)
