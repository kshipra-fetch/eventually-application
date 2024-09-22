from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import json
import asyncio
from uagents.query import query
from uagents.envelope import Envelope
from uagents import Model
from datetime import datetime

app = Flask(__name__)

app.secret_key = 'seedforsessionstorage,'  # Set a secret key for session handling

# Define Model classes for the agent

class Event(Model):
    city: str

class Response(Model):
    message: str


class Location(Model):
    address: str

class Location_Response(Model):
    message: str

class Coordinates(Model):
    lat: str
    lon:str


class CarParkResponse(Model):
    message: str



event_agent_address = "agent1q2sqxumanj6ufxjhp4lql0ryth8yllez5mde7cjkn3x49xa8n6gtsqkex9x"
location_agent_address = "agent1q2w902q596cs2mk92m7nlwyrsat42vffsfc07w35frhdwydtmx9gc478pwv"
car_park_agent_address = "agent1qg8hcsvsrvxcuy3k7rter54gfpdzh6ukwgz997veaqupucr2qqdtzkjujrd"


def convert_event_date(event_date, year=None):
    # Assuming the year if not provided
    if year is None:
        year = datetime.now().year

    # Define the correct format for the date string
    date_format = "%d %b"

    # Extract the part of the string that contains the date
    date_part = event_date.split(',')[1].strip()

    # Parse the date part of the string
    parsed_date = datetime.strptime(date_part, date_format)

    # Construct the full date with year, month, and day
    full_date = parsed_date.replace(year=year)

    return full_date.year, full_date.month, full_date.day

def parse_event_message(message):
    events = []
    event_blocks = message.split("Title:")
    for block in event_blocks[1:]:
        event = {}
        lines = block.split('\n')
        event['title'] = lines[0].strip()
        # Attempt to parse the date string as a dictionary
        date_str = lines[1].replace('Date:', '').strip()
        try:
            # Convert the string representation of a dictionary into an actual dictionary
            event['date'] = json.loads(date_str.replace("'", '"'))  # JSON requires double quotes
        except json.JSONDecodeError:
            # Fallback if the date string is not properly formatted as a dictionary
            event['date'] = date_str
        event['location'] = lines[2].replace('Location:', '').strip().strip("[]").replace("'", "")
        event['description'] = lines[3].replace('Description:', '').strip()
        event['link'] = lines[4].replace('Link:', '').strip()
        events.append(event)
    return events

async def query_agent(city):
    print("Querying events agent")
    response = await query(destination=event_agent_address, message=Event(city=city), timeout=15.0)
    if isinstance(response, Envelope):
        data = json.loads(response.decode_payload())
        return data
    return {"message": "Error occurred while querying the agent"}


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/events', methods=['POST'])
def submit_city():
    city = request.form['city']
    session['from_lat']=request.form.get('latitude')
    session['from_lon']=request.form.get('longitude')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(query_agent(city))

    if isinstance(response, dict) and 'message' in response:
        try:
            events = parse_event_message(response['message'])
            session['events'] = events  # Store events in session
            print(session['events'])
            return redirect(url_for('events_details'))
        except Exception as e:
            print(f"Failed to parse or store events: {e}")
            return jsonify({'events': [], 'error': 'Failed to parse event data'})
    # else:
    #     return jsonify({'events': [], 'error': 'No valid response received'})

@app.route('/events-details')
def events_details():
    events=session['events']
    return render_template("events-details.html", events=events)


@app.route('/car-park')
async def car_park():
    event_location = request.args.get('event_location')
    event_title = request.args.get('event_title')
    event_date = request.args.get('event_date')
    session['year'],session['month'], session['day'] = convert_event_date(event_date)

    print("Querying location agent")
    response = await query(destination=location_agent_address, message=Location(address=event_location), timeout=30.0)
    # print(response)
    if isinstance(response, Envelope):
        data = json.loads(response.decode_payload())
        print(data)
        location_data = json.loads(data['message'])
        print(f"Latitude: {location_data['latitude']}, Longitude: {location_data['longitude']}")

        session['to_lat'] = location_data['latitude']
        session['to_lon'] = location_data['longitude']
        print(latitude)
        print(longitude)

        car_park_response = await query(destination=car_park_agent_address, message=Coordinates(lat=session['to_lat'], lon=session['to_lon']), timeout=30.0)
        if isinstance(car_park_response, Envelope):
            car_park_data = json.loads(car_park_response.decode_payload())
            car_park_addresses = json.loads(car_park_data["message"])
            car_parks = [{"location": address.split(": ")[1]} for address in car_park_addresses]

            print(json.dumps(car_parks, indent=4))
            session['car_parks'] = car_parks
        return redirect(url_for('car_park_details', event_location=event_location, event_title=event_title))

@app.route('/car-park-details')
def car_park_details():
    event_location = request.args.get('event_location')  # Capture the event location passed as a query parameter
    event_title = request.args.get('event_title')
    car_parks = session.get('car_parks', [])

    return render_template("car-park-details.html", event_location=event_location, event_title=event_title, car_parks=car_parks)

app.run(debug=True)