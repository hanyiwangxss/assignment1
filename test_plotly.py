import urllib.request, json, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
url = "https://raw.githubusercontent.com/khinemyaezin/myanmar_geojson_data/main/state.json"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, context=ctx) as response:
    myanmar_geojson = json.loads(response.read().decode('utf-8'))

import plotly.graph_objects as go
import numpy as np

fig = go.Figure()
locs = [f['properties']['ST'] for f in myanmar_geojson['features']]
fig.add_trace(go.Choropleth(
    geojson=myanmar_geojson,
    locations=locs,
    z=[0]*len(locs),
    featureidkey="properties.ST",
    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
    marker_line_color="rgb(50,50,50)",
    marker_line_width=1.5,
    showscale=False,
    hovertemplate="%{location}<extra></extra>"
))
fig.update_geos(fitbounds="locations", visible=False)
fig.write_image("test.png")
