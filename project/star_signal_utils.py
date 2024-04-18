import requests
import json
import swagger_client

from __future__ import print_function
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint
from config import WEATHER_API_KEY

### RapidAPI - Utility Functions
def get_moon_phase(lat, lon):
    url = "https://moon-phase.p.rapidapi.com/advanced"

    querystring = {"lat": lat,"lon": lon}

    headers = {
        "X-RapidAPI-Key": "6c925f5fc2msh9b0d7fdec48e8a5p1e3e99jsndb79e168c058",
        "X-RapidAPI-Host": "moon-phase.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    response = json.dumps(response.json(), indent=4)

    return response


### Weather API - Utility Functions
def get_clouds(lat, lon):
    # Configure API key authorization: ApiKeyAuth
    configuration = swagger_client.Configuration()
    configuration.api_key['key'] = WEATHER_API_KEY
    # Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
    # configuration.api_key_prefix['key'] = 'Bearer'

    # create an instance of the API class
    api_instance = swagger_client.APIsApi(swagger_client.ApiClient(configuration))
    q = '-34.6316667,139.6675000' # str | Pass US Zipcode, UK Postcode, Canada Postalcode, IP address, Latitude/Longitude (decimal degree) or city name. Visit [request parameter section](https://www.weatherapi.com/docs/#intro-request) to learn more.
    dt = '2024-04-16' # date | Date on or after 1st Jan, 2015 in yyyy-MM-dd format

    try:
        # Astronomy API
        api_response = api_instance.astronomy(q, dt)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling APIsApi->astronomy: %s\n" % e)