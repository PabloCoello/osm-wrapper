from numpy.lib.index_tricks import AxisConcatenator
import requests
import geopandas as gpd
import pandas as pd
import collections
from shapely.geometry import Point
from shapely.geometry import Polygon
from geopandas.tools import sjoin


def flatten(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def pack(row):
    row['bounds'] = Polygon([[row['bounds_minlon'], row['bounds_minlat']], [row['bounds_minlon'], row['bounds_maxlat']],
                             [row['bounds_maxlon'], row['bounds_maxlat']], [row['bounds_maxlon'], row['bounds_minlat']]])
    return row

def format_geom(geometry):
    return Polygon(list(map(lambda x: Point([list(x.values())[1], list(x.values())[0]]),geometry)))
    
def unpack(row):
    if (row['members'][0]['type'] != 'node') & (len(row['members']) > 0):
        elem = row['members'][0]
        elem['geometry'] = format_geom(elem['geometry'])
        toret = gpd.GeoDataFrame(elem, geometry='geometry', index=range(len(row['members'][0])))
    elif(row['members'][0]['type'] == 'node'):
        toret = gpd.GeoDataFrame(
            row['members'][0], geometry=gpd.points_from_xy(
                row['members'][0]['lon'], 
                row['members'][0]['lat']))
    else:
        return None
    
    for i, elem in enumerate(row['members']):
        try:
            elem['geometry'] = format_geom(elem['geometry'])
        except:
            pass
        toret = gpd.GeoDataFrame(
            pd.concat(
                [toret, 
                  gpd.GeoDataFrame(
                      elem, 
                      geometry='geometry', 
                      index=range(len(elem)))], 
                ignore_index=True))
        
    toret['by'] = 1
    return toret.dissolve(by='by')['geometry']
        
    


def get_osm(tag, type, country, admin_level, variables):
    '''
    returns geodataframe from open street maps
    
    params:
        -istag: Filter by existence of tags
        -tag: Filter by value of tag
            ex: 'building'= 'yes'
        -type: one of node, rel or way
        -country: ISO codificated country
        -admin_level: admin level of the area
        -name: name of the location to query
    '''

    overpass_url = "http://overpass-api.de/api/interpreter"

    overpass_query = """
    [out:json];
    area["ISO3166-1"="{}"][admin_level={}];
    ({}[{}](area);
    );
    out geom;
    """.format(country, admin_level, type, tag)

    response = requests.get(overpass_url,
                            params={'data': overpass_query})
    data = response.json()
    df = pd.DataFrame(list(map(flatten, data['elements'])))

    if type == 'node':
        variables.append('lat')
        variables.append('lon')
        return gpd.GeoDataFrame(
            df[variables], geometry=gpd.points_from_xy(df.lon, df.lat))
    else:
        res = []
        for row in df.iterrows():
            try:
                res.append(unpack(row[1])[1])
            except:
                res.append(None)
        df['bounds'] = res 
        df = df.dropna(subset=['bounds'])
            #df.apply(unpack, axis=1)
        variables.append('bounds')
        return gpd.GeoDataFrame(df[variables],geometry='bounds')
    
if __name__ == '__main__':
    nodes = get_osm(
        tag='historic',
        type='node', 
        country='ES',
        admin_level='2',
        variables=['type','id','tags_historic','tags_name','tags_description']
    )
    nodes.to_file('nodes.shp')

    relations = get_osm(
        tag='historic',
        type='rel', 
        country='ES',
        admin_level='2',
        variables=['type','id','tags_historic','tags_name','tags_description'] 
        )
    relations.to_file('relations.shp')