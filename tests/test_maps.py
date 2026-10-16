"""Display coverage, georeferencing and SVG safety for the offline basemap."""
import base64
import hashlib
import io
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image
from fastapi.testclient import TestClient
import shapely

from homecoming.app import app
from homecoming.settings import ROOT
from homecoming.services.basemap import basemap, vector_context
from homecoming.services.maps import Context, make_scene, svg_scene, render_svg_asset


class MapTests(unittest.TestCase):
    def test_on_demand_svg_does_not_render_static_images(self):
        sections=[dict(coords=[[835000,816000],[835200,816100]],kind='network',
                       distance_m=223.6,cost=180,source='synthetic')]
        scene=make_scene(sections,[835000,816000],[835200,816100])
        with tempfile.TemporaryDirectory() as directory:
            with patch('homecoming.services.maps.raster_scene',side_effect=AssertionError('HD raster rendering')):
                files=render_svg_asset('synthetic',scene,'Test','SVG only',root=Path(directory))
            self.assertEqual(set(files),{'svg'})
            self.assertEqual([p.suffix for p in Path(directory).rglob('*') if p.is_file()],['.svg'])

    def test_point_selection_map_has_navigation_bounds(self):
        with TestClient(app) as client:
            response=client.get('/api/map/overview')
        self.assertEqual(response.status_code,200)
        svg=ET.fromstring(response.text)
        self.assertEqual(svg.attrib['viewBox'],'0 0 1000 650')
        self.assertEqual(svg.attrib['data-context-bounds'],'0 0 1000 650')
        self.assertEqual(svg.attrib['data-dynamic-background'],'true')
        image=svg.find("{http://www.w3.org/2000/svg}image[@id='pedestrian-background']")
        with Image.open(io.BytesIO(base64.b64decode(image.attrib['href'].split(',',1)[1]))) as background:
            self.assertEqual(background.size,(1600,1040))

    def test_selection_viewport_serves_terrain_and_paths(self):
        with TestClient(app) as client:
            response=client.get('/api/map/background?left=834950&bottom=815950&right=835250&top=816150')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'image/webp')
            with Image.open(io.BytesIO(response.content)) as image:
                self.assertEqual(image.width,1400)
            self.assertEqual(client.get('/api/map/background?left=nan&bottom=815950&right=835250&top=816150').status_code,400)
            self.assertEqual(client.get('/api/map/background?left=834950&bottom=815950&right=834951&top=816150').status_code,400)

    def test_original_background_is_complete_and_not_mode_filtered(self):
        context = basemap()
        self.assertEqual(len(context.geometry), 465892)
        self.assertEqual(int(shapely.get_num_coordinates(context.geometry).sum()),1963912)
        # The old renderer dropped most of these paths and broke the backdrop.
        extent = [832000, 814000, 842000, 824000]
        lines = context.lines(extent)
        self.assertGreater(len(lines), 2400)

    def test_terrain_is_local_and_georeferenced(self):
        directory = ROOT / 'assets/maps'
        metadata = json.loads((directory / 'terrain_relief.json').read_text())
        self.assertEqual(hashlib.sha256((directory / 'terrain_relief.png').read_bytes()).hexdigest(), metadata['image_sha256'])
        self.assertEqual(metadata['resolution_m'], 20)
        with Image.open(directory / 'terrain_relief.png') as image:
            self.assertEqual(list(image.size), metadata['size'])
            west,south,east,north=metadata['bounds']
            self.assertEqual(east-west,image.width*20)
            self.assertEqual(north-south,image.height*20)
            self.assertGreater(len(image.getcolors(image.width*image.height)), 1000)

    def test_svg_has_surroundings_and_keeps_vector_route(self):
        sections=[dict(coords=[[835000,816000],[835200,816100]],kind='network',
                       distance_m=223.6,cost=180,source='synthetic')]
        scene=make_scene(sections,[835000,816000],[835200,816100],Context())
        svg=ET.fromstring(svg_scene(scene,'Synthetic test','Display coverage'))
        self.assertEqual(svg.attrib['data-context-bounds'],'-500 -350 2000 1400')
        image=svg.find('{http://www.w3.org/2000/svg}image')
        self.assertEqual([float(image.attrib[k]) for k in ('x','y','width','height')],[-500,-350,2000,1400])
        with Image.open(io.BytesIO(base64.b64decode(image.attrib['href'].split(',',1)[1]))) as raster:
            self.assertEqual(raster.size,(2000,1400))
        route=svg.find("{http://www.w3.org/2000/svg}g[@class='route-lines']")
        self.assertEqual(len(route),2)  # white casing + original vector geometry
        self.assertEqual(route[1].attrib['vector-effect'],'non-scaling-stroke')
        self.assertIn('180.00 seconds',route[1][0].text)

    def test_close_zoom_detail_and_invalid_viewports(self):
        with TestClient(app) as client:
            query='left=834950&bottom=815950&right=835250&top=816150&cx=835100&cy=816050&scale=2'
            response=client.get('/api/map/context?'+query)
            self.assertEqual(response.status_code,200)
            self.assertIn('<polyline',response.text)
            self.assertNotIn('<script',response.text)
            self.assertEqual(client.get('/api/map/context?'+query.replace('left=834950','left=nan')).status_code,400)
            self.assertEqual(client.get('/api/map/context?'+query.replace('right=835250','right=834000')).status_code,400)
            self.assertEqual(vector_context([830000,810000,845000,830000],835100,816050,1),'')


if __name__=='__main__':
    unittest.main()
