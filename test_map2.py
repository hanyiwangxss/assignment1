import urllib.request, json, ssl
import plotly.graph_objects as go

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
url = "https://www.geoboundaries.org/api/current/gbOpen/UKR/ADM0/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req, context=ctx).read().decode()
data = json.loads(resp)
url2 = data.get("simplifiedGeometryGeoJSON") or data.get("gjDownloadURL")
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
resp2 = urllib.request.urlopen(req2, context=ctx).read().decode()
geojson = json.loads(resp2)

fig = go.Figure()

# Plot the ADM0 geojson
fig.add_trace(go.Choropleth(
    geojson=geojson,
    locations=["Ukraine"],
    z=[1],
    featureidkey="properties.shapeName",
    colorscale=[[0, "rgb(255,235,120)"], [1, "rgb(255,235,120)"]],
    zmin=1,
    zmax=1,
    marker_line_color="rgba(35,35,35,0.9)",
    marker_line_width=1.2,
    showscale=False,
))

fig.update_geos(
    projection_type="mercator",
    lataxis_range=[43.2, 54.8],
    lonaxis_range=[20.8, 41.4],
    showland=True, landcolor="rgb(215,215,215)",
    showcountries=True, countrycolor="rgb(125,125,125)", countrywidth=0.9,
    showcoastlines=False, showlakes=False, showrivers=False,
    showocean=True, oceancolor="rgb(220,238,255)",
    showframe=False, bgcolor="rgb(220,238,255)",
    resolution=50
)

fig.write_html("test_map2.html")
print("Done")
