# Glider Flight Planner

Glider Flight Planner is a web application designed to assist glider pilots in planning their flights. The app provides a visual representation of flight paths on a map based on user-defined parameters.

## ⚠️ Disclaimer

This application is provided as a tool to assist glider pilots in planning their flights. While every effort has been made to ensure the accuracy of the information provided, users should always exercise caution and verify information with other sources before relying on it for flight planning or any other purposes. **Use this application at your own risk.** The developers and contributors are not responsible for any inaccuracies or for any decisions made based on the information provided by this application.

## Features

- **Interactive Map**: Displays a folium map based on selected center locations.
- **Data Table**: An editable table that allows users to select multiple or all center locations.
- **Flight Parameters**: Users can input wind direction, wind speed, glide ratio, best glide speed (Vg), and safety margin to adjust the flight path calculations.
- **Responsive Design**: Utilizes Bootstrap for a polished and mobile-friendly user interface.

## Installation

1. Clone the repository:
```
git clone https://github.com/AlexCodeGlider/gliderFlightPlanner.git
```

2. Navigate to the project directory and install the required packages:
```
cd gliderFlightPlanner
pip install -r requirements.txt
```

3. Run the Flask app:
```
flask run
```

4. Open a web browser and navigate to `http://127.0.0.1:5000/` to access the app.

## Usage

1. Select desired center locations from the data table.
2. Input flight parameters in the provided form.
3. Click "Submit" to view the flight path on the map.

## Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute.

## License

This project is licensed under the MIT License. See the [LICENSE.md](LICENSE.md) file for details.
