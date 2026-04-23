import re
with open("ukraine_conflict_map_2025.html", "r") as f:
    html = f.read()
    if 'rgb(215,215,215)' in html: print('Found gray land color')
    match = re.search(r'landcolor\":\"(.*?)\"', html)
    if match: print('landcolor matches:', match.group(1))
    
    matches = re.findall(r'\"colorscale\":\[(.*?)\}', html)
    print('Colorscales found:', matches[:3])
