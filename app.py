from flask import Flask, render_template, request, session, redirect, url_for
from pymongo import MongoClient
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
import bcrypt
import pickle
import numpy as np

app = Flask(__name__)

URI = ""
app.secret_key = '12345678'

client = MongoClient(URI)
db = client["farmer_data"]  
collection = db["farmer"]
collection2 = db["users"]
#Weather API
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)
openmeteo = openmeteo_requests.Client(session = retry_session)

with open('Gradientboost.pkl', 'rb') as f:
    model = pickle.load(f)

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)


@app.route('/')
@app.route('/home')
def home2():    
    return render_template('index.html')

@app.route('/about')
def about():
    return "About"

@app.route('/feature')
def feature():
    # Define the logic for your feature endpoint here
    return "Feature Page"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'email' in session:
        return 'Already logged in as ' + session['email']
    if request.method == 'POST':
        user = collection2.find_one({'email': request.form['email']})
        if user:
            if bcrypt.checkpw(request.form['password'].encode('utf-8'), user['password']):
                session['email'] = request.form['email']
                return redirect(url_for('profile'))
            else:
                return 'Invalid email/password combination. Please try again.'
        else:
            return 'User not found. Please sign up.'
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'email' in session:
        return 'Already logged in as ' + session['email']
    if request.method == 'POST':
        existing_user = collection2.find_one({'email': request.form['email']})
        if existing_user:
            return 'User with this email already exists. Please login instead.'
        else:
            hashed_password = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
            user = {
                'name': request.form['name'],
                'email': request.form['email'],
                'phoneno' : request.form['phoneno'],
                'password': hashed_password
            }
            collection2.insert_one(user)
            session['email'] = request.form['email']
            return redirect(url_for('profile'))
    return render_template('signup.html')

@app.route('/profile')
def profile():
    if 'email' in session:
        user = collection2.find_one({'email': session['email']})
        if user:
            return render_template('profile.html', user=user)
        else:
            return 'User not found.'
    else:
        return 'You are not logged in.'
    

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('home'))



@app.route('/updatedetails')
def farmer_details():
    return render_template('dataform.html')


@app.route('/submit', methods=['POST'])
def submit():
    if 'email' in session:    
        if request.method == 'POST':
            name = request.form['name']
            current_crop = request.form['current_crop']
            soil_conditions = request.form['soil_conditions']
            farm_area = request.form['farm_area']
            past_year_yield = request.form['past_year_yield']
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            nitrogen = request.form['nitrogen']
            phosphorous = request.form['phosphorous']
            potassium = request.form['potassium']
            # Check if data with the same name exists
            existing_data = collection.find_one({'name': name})
            if existing_data:
                # If data exists, delete the existing document
                collection.delete_one({'name': name})
                print("Data Deleted Successfully")

            # Create a dictionary for the new data
            farmer_data = {
                'name': name,
                'email': session['email'],  # Assuming the user is logged in and has an email in the session
                'current_crop': current_crop,
                'soil_conditions': soil_conditions,
                'farm_area': farm_area,
                'past_year_yield': past_year_yield,
                'latitude': latitude,
                'longitude': longitude,
                'nitrogen' : nitrogen,
                'phosphorous' : phosphorous,
                'potassium' : potassium,
            }

            # Insert new data into MongoDB
            collection.insert_one(farmer_data)
            print("Data Submitted Successfully" + str(farmer_data))  # Convert farmer_data to string
            return url_for('farmdata')
        
    else:
        return 'You are not logged in.'    

@app.route('/recommendations')
def recommendations():
    if 'email' not in session:
        return redirect('/login')
    
    # Fetch user's farmer data
    email = session['email']
    farmer_data = collection.find_one({'email': email})

    if farmer_data:
        # Get latitude and longitude from farmer data
        latitude = farmer_data['latitude']
        longitude = farmer_data['longitude']
        nitrogen = farmer_data['nitrogen']
        phosphorous = farmer_data['phosphorous']
        potassium = farmer_data['potassium']
        ph = 6.7
        # Make Open-Meteo API request
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ["temperature_2m", "relative_humidity_2m", "rain"],
            "timezone": "Asia/Singapore"
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]  # Assuming only one response for simplicity

        # Process weather data
        current = response.Current()
        current_temperature_2m = current.Variables(0).Value()
        current_relative_humidity_2m = current.Variables(1).Value()
        current_rain = current.Variables(2).Value()
        y = ['rice', 'maize', 'chickpea', 'kidneybeans', 'pigeonpeas',
       'mothbeans', 'mungbean', 'blackgram', 'lentil', 'pomegranate',
       'banana', 'mango', 'grapes', 'watermelon', 'muskmelon', 'apple',
       'orange', 'papaya', 'coconut', 'cotton', 'jute', 'coffee']
        # Make prediction using machine learning model
        #features = [nitrogen,phosphorous,potassium,current_temperature_2m, current_relative_humidity_2m,ph,current_rain]
        #features = [50,150,270,260.399999618530273,430.0,60.7,00.0]
    #     print(features)
    #     features = np.array([features])

    # # Use the model to make predictions
    #     predictions = model.predict(features)
        features = [int(nitrogen), int(phosphorous), int(potassium), float(current_temperature_2m),float(current_relative_humidity_2m), float(ph), float(current_rain)]
        features_2d = np.array([features])

# Use the model to make predictions
        predictions = model.predict(features_2d)

# Assuming 'predictions' is your prediction array
# And 'y.columns' are your column names

# Find the index of the '1' in the predictions
        index = np.where(predictions[0] == 1)[0][0]

# Use this index to get the corresponding crop name from y.columns
        predicted_crop = y[index]
        print(features)
        print(predicted_crop)
        return render_template('recommendations.html', recommendation=predicted_crop)
    
    else:
        return 'No farmer data found for this user. Try Logging In'


@app.route('/weatherPrediction')
def weather_prediction():
    if 'email' not in session:
        return redirect('/login')
    
    # Fetch user's farmer data
    email = session['email']
    farmer_data = collection.find_one({'email': email})
    print(farmer_data)
    if farmer_data:
        # Get latitude and longitude from farmer data
        latitude = farmer_data['latitude']
        longitude = farmer_data['longitude']
        
        # Make Open-Meteo API request
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ["temperature_2m", "precipitation"],
            "hourly": ["temperature_2m", "relative_humidity_2m", "rain", "temperature_80m"],
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "timezone": "Asia/Singapore"
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        # Process weather data
        current = response.Current()
        current_temperature_2m = current.Variables(0).Value()
        current_precipitation = current.Variables(1).Value()

        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
        hourly_rain = hourly.Variables(2).ValuesAsNumpy()
        hourly_temperature_80m = hourly.Variables(3).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )}
        hourly_data["temperature_2m"] = hourly_temperature_2m
        hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
        hourly_data["rain"] = hourly_rain
        hourly_data["temperature_80m"] = hourly_temperature_80m

        hourly_dataframe = pd.DataFrame(data=hourly_data)

        daily = response.Daily()
        daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
        daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()

        daily_data = {"date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        )}
        daily_data["temperature_2m_max"] = daily_temperature_2m_max
        daily_data["temperature_2m_min"] = daily_temperature_2m_min

        daily_dataframe = pd.DataFrame(data=daily_data)

        return render_template('weather_prediction.html', hourly_data=hourly_dataframe.to_html(), daily_data=daily_dataframe.to_html())
    
    else:
        return 'No farmer data found for this user. Try Logging In'



@app.route('/farmdata', methods=['GET', 'POST'])
def search():
    if 'email' in session:
        email = session['email']
        user_data = collection.find_one({'email': email})
        if user_data:
            return render_template('farm_data.html', user_data=user_data)
        else:
            return 'No data found for the current user.'
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=9999)
