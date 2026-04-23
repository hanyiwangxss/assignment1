import plotly.graph_objects as go

fig = go.Figure()

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

fig.write_html("test_map.html")
