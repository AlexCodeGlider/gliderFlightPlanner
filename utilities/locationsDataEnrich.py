from geopy.geocoders import Nominatim
import pandas as pd

# Define a function to get location details
def get_location_details(lat, lon):
    # Initialize Nominatim API
    geolocator = Nominatim(user_agent="location_data_enricher")
    
    # Get location details
    location = geolocator.reverse((lat, lon), exactly_one=True)
    address = location.raw['address']
    
    return address.get('state'), address.get('county')

def enrich_locations():
    # Load your CSV data into a DataFrame
    df = pd.read_csv('/Users/alejandroleda/Documents/Py/gliderFlightPlanner/data/Crystal23.csv')

    # Apply the function to each row in your DataFrame
    df[['State', 'County']] = df.apply(lambda row: get_location_details(row['Lat'], row['Long']), axis=1, result_type='expand')

    # Save the enriched DataFrame back to CSV
    df.to_csv('/Users/alejandroleda/Documents/Py/gliderFlightPlanner/data/enriched_locations.csv', index=False)

if __name__ == '__main__':
    enrich_locations()
