import json

data = json.load(open('assignment1.ipynb', 'r'))

source = """# Ukraine 2025 动态冲突地图：真实世界底图 + 行政区 + 动态气泡
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import urllib.request
import json
import ssl

# ---------- 参数 ----------
MIN_SIZE_FOR_ZERO = 0.01
MAX_MARKER_SIZE = 66
MIN_VISIBLE_SIZE = 8
MARKER_ALPHA = 0.82
TOP_N_REGIONS = 5
INTERP_STEPS = 6
FAST_FRAME_MS = 80

# ---------- 前置检查 ----------
if "df" not in globals():
    raise ValueError("请先运行第2个单元，确保已加载统一 CSV 数据 df。")

required_cols = [year_col, country_col, week_col]
if not all(c is not None for c in required_cols):
    raise ValueError(f"缺少必要字段：year={year_col}, country={country_col}, week/date={week_col}")

geo_cols = {c.lower().strip(): c for c in df.columns}

def find_geo_col(candidates):
    for cand in candidates:
        for k, orig in geo_cols.items():
            if cand in k:
                return orig
    return None

lat_col = find_geo_col(["latitude", "lat"])
lon_col = find_geo_col(["longitude", "long", "lon"])
events_col = find_geo_col(["events", "count"])
admin_col = admin1_col if "admin1_col" in globals() and admin1_col is not None else (find_geo_col(["admin1"]) or "ADMIN1")

if lat_col is None or lon_col is None:
    raise ValueError(f"缺少地理列: lat={lat_col}, lon={lon_col}")

# ---------- 数据准备（乌克兰 2025） ----------
ukraine_df = df[
    df[country_col].astype(str).str.contains(r"\\bukraine\\b", case=False, na=False, regex=True)
    & (pd.to_numeric(df[year_col], errors="coerce") == 2025)
].copy()

ukraine_df[lat_col] = pd.to_numeric(ukraine_df[lat_col], errors="coerce")
ukraine_df[lon_col] = pd.to_numeric(ukraine_df[lon_col], errors="coerce")
ukraine_df["_date_"] = pd.to_datetime(ukraine_df[week_col], errors="coerce")
ukraine_df = ukraine_df.dropna(subset=[lat_col, lon_col, "_date_"]).copy()
ukraine_df = ukraine_df[
    (ukraine_df["_date_"] >= "2025-01-01") &
    (ukraine_df["_date_"] < "2026-01-01")
]

if ukraine_df.empty:
    raise ValueError("No valid geographical coordinates found for Ukraine in 2025.")

# 乌克兰包围盒过滤异常点
in_bbox = ukraine_df[lat_col].between(43, 53) & ukraine_df[lon_col].between(22, 41)
outlier_count = int((~in_bbox).sum())
if outlier_count > 0:
    print(f"Detected and filtered out-of-bound outlier coordinates: {outlier_count}")
ukraine_df = ukraine_df.loc[in_bbox].copy()

if ukraine_df.empty:
    raise ValueError("No data left after filtering out-of-bound geo-coordinates for Ukraine.")

if events_col is not None:
    ukraine_df["event_count"] = pd.to_numeric(ukraine_df[events_col], errors="coerce").fillna(0).clip(lower=0)
else:
    ukraine_df["event_count"] = 1

ukraine_df["Month"] = ukraine_df["_date_"].dt.strftime("%Y-%m")
months = pd.period_range("2025-01", "2025-12", freq="M").astype(str).tolist()

# 坐标级聚合（月）
agg = (
    ukraine_df.groupby(["Month", lat_col, lon_col], as_index=False)
    .agg(event_count=("event_count", "sum"), region=(admin_col, "first"))
)

coord_lookup = agg[[lat_col, lon_col, "region"]].drop_duplicates().reset_index(drop=True)
coord_lookup["coord_id"] = coord_lookup.index
agg = agg.merge(coord_lookup[[lat_col, lon_col, "coord_id"]], on=[lat_col, lon_col], how="left")

full_index = pd.MultiIndex.from_product([months, coord_lookup["coord_id"]], names=["Month", "coord_id"])
full_df = full_index.to_frame(index=False).merge(coord_lookup, on="coord_id", how="left")
full_df = full_df.merge(agg[["Month", "coord_id", "event_count"]], on=["Month", "coord_id"], how="left")
full_df["event_count"] = full_df["event_count"].fillna(0)

max_events = full_df["event_count"].max()
if max_events > 0:
    full_df["size_plot"] = np.where(
        full_df["event_count"] > 0,
        (np.sqrt(full_df["event_count"]) / np.sqrt(max_events)) * (MAX_MARKER_SIZE - MIN_VISIBLE_SIZE) + MIN_VISIBLE_SIZE,
        MIN_SIZE_FOR_ZERO,
    )
else:
    full_df["size_plot"] = MIN_SIZE_FOR_ZERO

# ---------- 导入乌克兰行政区数据 ----------
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

ukraine_adm0_geojson = None
ukraine_adm1_geojson = None
adm0_featureidkey = None
adm0_location = None
adm1_featureidkey = None
adm1_locations = None

# 乌克兰 ADM0 国界（用于完整黄色填充和清晰国境线）
try:
    api_url_adm0 = "https://www.geoboundaries.org/api/current/gbOpen/UKR/ADM0/"
    req = urllib.request.Request(api_url_adm0, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
        api_info_adm0 = json.loads(response.read().decode("utf-8"))

    geojson_url_adm0 = api_info_adm0.get("simplifiedGeometryGeoJSON") or api_info_adm0.get("gjDownloadURL")
    if geojson_url_adm0:
        req = urllib.request.Request(geojson_url_adm0, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            ukraine_adm0_geojson = json.loads(response.read().decode("utf-8"))

    if ukraine_adm0_geojson and "features" in ukraine_adm0_geojson and len(ukraine_adm0_geojson["features"]) > 0:
        props0 = ukraine_adm0_geojson["features"][0].get("properties", {})
        key0 = None
        for k in ["shapeName", "NAME_0", "name", "Name", "ADM0_EN"]:
            if k in props0:
                key0 = k
                break

        if key0 is not None:
            adm0_featureidkey = f"properties.{key0}"
            adm0_location = [ukraine_adm0_geojson["features"][0].get("properties", {}).get(key0, "Ukraine")]
        else:
            ukraine_adm0_geojson = None
except Exception as e:
    print(f"Warning: Could not download Ukraine ADM0 GeoJSON ({e}).")

# 乌克兰 ADM1 行政区
try:
    api_url = "https://www.geoboundaries.org/api/current/gbOpen/UKR/ADM1/"
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
        api_info = json.loads(response.read().decode("utf-8"))

    geojson_url = api_info.get("simplifiedGeometryGeoJSON") or api_info.get("gjDownloadURL")
    if geojson_url:
        req = urllib.request.Request(geojson_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            ukraine_adm1_geojson = json.loads(response.read().decode("utf-8"))

    if ukraine_adm1_geojson and "features" in ukraine_adm1_geojson and len(ukraine_adm1_geojson["features"]) > 0:
        props = ukraine_adm1_geojson["features"][0].get("properties", {})
        candidate_keys = ["shapeName", "NAME_1", "name", "Name", "ADM1_EN"]
        chosen_key = None
        for k in candidate_keys:
            if k in props:
                chosen_key = k
                break

        if chosen_key is not None:
            adm1_featureidkey = f"properties.{chosen_key}"
            adm1_locations = [f.get("properties", {}).get(chosen_key, "") for f in ukraine_adm1_geojson["features"]]
        else:
            ukraine_adm1_geojson = None
except Exception as e:
    print(f"Warning: Could not download Ukraine ADM1 GeoJSON ({e}).")

# ---------- 构造图 ----------
fig = go.Figure()

# 乌克兰完整黄色填充 + 清晰单一国境线
if ukraine_adm0_geojson is not None and adm0_featureidkey is not None and adm0_location is not None:
    # 乌克兰底图填充：使用 ADM0，直接覆盖且不需要额外的粗边框，粗边框由底层的世界地图统一提供或者在这里提供
    fig.add_trace(go.Choropleth(
        geojson=ukraine_adm0_geojson,
        locations=adm0_location,
        z=[1],
        featureidkey=adm0_featureidkey,
        colorscale=[[0, "rgb(255,235,120)"], [1, "rgb(255,235,120)"]],
        zmin=1,
        zmax=1,
        marker_line_color="rgba(35,35,35,0.9)",
        marker_line_width=1.2, # 稍微加深主边缘，使其与相邻国家的灰色粗线无缝结合
        showscale=False,
        hoverinfo="skip",
    ))

# 乌克兰境内行政区边界（叠加显示）
if ukraine_adm1_geojson is not None and adm1_featureidkey is not None and adm1_locations is not None:
    fig.add_trace(go.Choropleth(
        geojson=ukraine_adm1_geojson,
        locations=adm1_locations,
        z=[1] * len(adm1_locations),
        featureidkey=adm1_featureidkey,
        colorscale=[[0, "rgba(255,235,120,0.0)"], [1, "rgba(255,235,120,0.0)"]],
        marker_line_color="rgba(35,35,35,0.5)", # 内部线更细更淡，防止杂乱
        marker_line_width=0.65,
        showscale=False,
        hoverinfo="skip",
    ))

# 邻国国家名
label_df = pd.DataFrame({
    "name": ["Poland", "Belarus", "Russia", "Moldova", "Romania", "Hungary", "Slovakia", "Lithuania"],
    "lat":  [51.8,      52.9,      52.7,      47.2,       45.8,      47.3,      48.8,       54.2],
    "lon":  [23.2,      28.8,      38.2,      28.9,       25.8,      22.0,      22.3,       23.8],
})
fig.add_trace(go.Scattergeo(
    lon=label_df["lon"], lat=label_df["lat"], mode="text", text=label_df["name"],
    textfont=dict(size=13, color="rgb(95,95,95)"), showlegend=False, hoverinfo="skip"
))

# 乌克兰自己名字也写上
fig.add_trace(go.Scattergeo(
    lon=[31.0], lat=[49.0], mode="text", text=["Ukraine"],
    textfont=dict(size=14, color="rgb(110,110,110)"), showlegend=False, hoverinfo="skip"
))

# 首都五角星（基辅）
fig.add_trace(go.Scattergeo(
    lon=[30.5234], lat=[50.4501],
    mode="markers+text",
    marker=dict(size=13, color="rgb(210,0,0)", symbol="star", line=dict(color="rgb(210,0,0)", width=0.5)),
    text=["Kyiv"],
    textposition="bottom center",
    textfont=dict(size=12, color="rgb(40,40,40)"),
    showlegend=False, hoverinfo="skip"
))

# 高事件省份：外置标签 + 黑色箭头（避免与气泡重叠）
if admin_col in ukraine_df.columns:
    top_regions = (
        ukraine_df.groupby(admin_col, as_index=False)["event_count"]
        .sum()
        .sort_values("event_count", ascending=False)
        .head(TOP_N_REGIONS)
    )
    region_cent = ukraine_df.groupby(admin_col, as_index=False).agg(lat=(lat_col, "mean"), lon=(lon_col, "mean"))
    top_regions = top_regions.merge(region_cent, on=admin_col, how="left")

    for i, row in top_regions.iterrows():
        anchor_lat = float(row["lat"])
        anchor_lon = float(row["lon"])

        if anchor_lon < 31.0:
            text_lon = anchor_lon - 2.2
            text_lat = anchor_lat + (0.65 if i % 2 == 0 else -0.65)
            elbow_lon = anchor_lon - 0.8
            text_pos = "middle left"
        else:
            text_lon = anchor_lon + 2.2
            text_lat = anchor_lat + (0.65 if i % 2 == 0 else -0.65)
            elbow_lon = anchor_lon + 0.8
            text_pos = "middle right"
        elbow_lat = anchor_lat

        fig.add_trace(go.Scattergeo(
            lon=[text_lon, elbow_lon, anchor_lon],
            lat=[text_lat, elbow_lat, anchor_lat],
            mode="lines",
            line=dict(width=2.0, color="rgb(55,55,55)"),
            showlegend=False,
            hoverinfo="skip",
        ))

        dy = anchor_lat - elbow_lat
        dx = anchor_lon - elbow_lon
        angle = 90 - np.degrees(np.arctan2(dy, dx))
        fig.add_trace(go.Scattergeo(
            lon=[anchor_lon], lat=[anchor_lat],
            mode="markers",
            marker=dict(size=8.5, color="black", symbol="triangle-up", angle=angle),
            showlegend=False,
            hoverinfo="skip",
        ))

        fig.add_trace(go.Scattergeo(
            lon=[text_lon], lat=[text_lat],
            mode="text",
            text=[f"<b>{row[admin_col]}</b>"],
            textfont=dict(size=12.5, color="rgb(40,40,40)", family="Arial"),
            textposition=text_pos,
            showlegend=False,
            hoverinfo="skip",
        ))

# 保证动画点序一致
full_df = full_df.sort_values(["Month", "coord_id"])

# 插值帧
frame_info = []
smooth_records = []

def format_month(yyyy_mm):
    d = pd.to_datetime(yyyy_mm + "-01")
    return d.strftime("%b %Y")

for i in range(len(months)):
    m_curr = months[i]
    df_curr = full_df[full_df["Month"] == m_curr].reset_index(drop=True)
    m_curr_label = format_month(m_curr)

    if i < len(months) - 1:
        m_next = months[i + 1]
        df_next = full_df[full_df["Month"] == m_next].reset_index(drop=True)

        for step in range(INTERP_STEPS):
            alpha = step / float(INTERP_STEPS)
            df_interp = df_curr.copy()
            df_interp["size_plot"] = df_curr["size_plot"] * (1 - alpha) + df_next["size_plot"] * alpha
            df_interp["event_count"] = df_curr["event_count"] * (1 - alpha) + df_next["event_count"] * alpha

            f_id = f"{m_curr}_step{step}"
            if step == 0:
                label_val = f"{m_curr_label}"
            elif step == INTERP_STEPS // 2:
                label_val = f"Mid-{m_curr_label[:3]}"
            else:
                label_val = ""

            df_interp["frame_id"] = f_id
            smooth_records.append(df_interp)
            frame_info.append((f_id, label_val))
    else:
        f_id = f"{m_curr}_step0"
        df_curr["frame_id"] = f_id
        smooth_records.append(df_curr)
        frame_info.append((f_id, m_curr_label))

smooth_full_df = pd.concat(smooth_records, ignore_index=True)

# 初始动态气泡
d0 = smooth_full_df[smooth_full_df["frame_id"] == frame_info[0][0]].copy()
d0_counts = d0["event_count"].to_numpy()
d0_text = [f"<b>{int(round(c))}</b>" if c >= 0.5 else "" for c in d0_counts]

fig.add_trace(go.Scattergeo(
    lon=d0[lon_col], lat=d0[lat_col], mode="markers+text",
    text=d0_text,
    textposition="middle center",
    textfont=dict(size=12, color="white", family="Arial"),
    marker=dict(size=d0["size_plot"], color=f"rgba(220,20,60,{MARKER_ALPHA})", line=dict(width=0.6, color="white")),
    customdata=np.column_stack([d0["region"].astype(str).to_numpy(), d0["event_count"].to_numpy()]),
    hovertemplate="Region: %{customdata[0]}<br>Event Count: %{customdata[1]:.0f}<extra></extra>",
    name="Conflict Events"
))
dynamic_trace_index = len(fig.data) - 1

frames = []
for f_id, _ in frame_info:
    dm = smooth_full_df[smooth_full_df["frame_id"] == f_id]
    dm_counts = dm["event_count"].to_numpy()
    dm_text = [f"<b>{int(round(c))}</b>" if c >= 0.5 else "" for c in dm_counts]

    frames.append(go.Frame(
        name=f_id,
        data=[go.Scattergeo(
            lon=dm[lon_col], lat=dm[lat_col], mode="markers+text",
            text=dm_text,
            textposition="middle center",
            textfont=dict(size=12, color="white", family="Arial"),
            marker=dict(size=dm["size_plot"], color=f"rgba(220,20,60,{MARKER_ALPHA})", line=dict(width=0.6, color="white")),
            customdata=np.column_stack([dm["region"].astype(str).to_numpy(), dm["event_count"].to_numpy()]),
            hovertemplate="Region: %{customdata[0]}<br>Event Count: %{customdata[1]:.0f}<extra></extra>",
            showlegend=False,
        )],
        traces=[dynamic_trace_index],
    ))
fig.frames = frames

# 地图视角 (缅甸版本风格配置，只用原生地图绘制其他国家)
fig.update_geos(
    projection_type="mercator",
    lataxis_range=[43.2, 54.8],
    lonaxis_range=[20.8, 41.4],
    showland=True, landcolor="rgb(215,215,215)", # 周围灰色大陆
    showcountries=True, countrycolor="rgb(125,125,125)", countrywidth=0.9, # 其他国家灰边界
    showcoastlines=False, showlakes=False, showrivers=False,
    showocean=True, oceancolor="rgb(220,238,255)", 
    showframe=False, bgcolor="rgb(220,238,255)",
    resolution=50, domain=dict(x=[0, 1], y=[0, 1])
)

# 控件
slider_steps = []
for f_id, label in frame_info:
    slider_steps.append({
        "label": label,
        "method": "animate",
        "args": [[f_id], {
            "mode": "immediate",
            "frame": {"duration": FAST_FRAME_MS, "redraw": True},
            "transition": {"duration": 0},
        }],
    })

sliders = [{
    "active": 0,
    "x": 0.16,
    "len": 0.80,
    "y": 0.035,
    "xanchor": "left",
    "yanchor": "bottom",
    "currentvalue": {"prefix": "Timeline: ", "font": {"size": 13, "color": "#333333"}},
    "steps": slider_steps,
}]

fig.update_layout(
    title="Dynamic Spatial Distribution of Conflict Events in Ukraine (2025)",
    autosize=True,
    height=920,
    margin=dict(l=0, r=0, t=58, b=0),
    paper_bgcolor="rgb(220,238,255)",
    plot_bgcolor="rgb(220,238,255)",
    dragmode=False,
    sliders=sliders,
    legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.8)"),
    updatemenus=[{
        "type": "buttons",
        "showactive": False,
        "x": 0.01,
        "y": 0.06,
        "xanchor": "left",
        "yanchor": "bottom",
        "buttons": [{
            "label": "Play",
            "method": "animate",
            "args": [None, {
                "frame": {"duration": FAST_FRAME_MS, "redraw": True},
                "transition": {"duration": 0},
                "fromcurrent": True,
            }],
        }, {
            "label": "Pause",
            "method": "animate",
            "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}],
        }],
    }],
)

uk_map_html = "ukraine_conflict_map_2025.html"
fig.write_html(uk_map_html)
print(f"Interactive HTML map successfully exported to: {uk_map_html}")

fig.show(config={"responsive": True, "displayModeBar": True})
"""

# Apply it properly as lines with newlines
source_lines = [line + '\n' for line in source.split('\n')]
# Remove the last newline from last line for consistency
source_lines[-1] = source_lines[-1].strip('\n')

data['cells'][-1]['source'] = source_lines

with open('assignment1.ipynb', 'w') as f:
    json.dump(data, f, indent=4)
