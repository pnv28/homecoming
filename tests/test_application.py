import asyncio
import base64
import io
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
from PIL import Image
from pydantic import ValidationError

from homecoming.app import app,SESSIONS
from homecoming.schemas import Parameters,SearchRequest,WalkRequest
from homecoming.services import data,deepseek,documents,jobs
from homecoming.settings import ROOT


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.key_patch=patch('homecoming.app.DEEPSEEK_API_KEY','')
        self.key_patch.start()
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close()
        self.key_patch.stop()

    def test_shared_key_is_private_and_survives_applicant_reset(self):
        with patch('homecoming.app.DEEPSEEK_API_KEY','synthetic-shared-server-key'):
            response=self.client.get('/api/bootstrap')
            self.assertTrue(response.json()['connected'])
            self.assertNotIn('synthetic-shared-server-key',response.text)
            home=self.client.get('/').text
            self.assertNotIn('connection-dialog',home)
            self.assertNotIn('id="api-key"',home)
            with TestClient(app) as other:
                self.assertTrue(other.get('/api/bootstrap').json()['connected'])
                self.assertNotEqual(self.client.cookies.get('homecoming_session'),other.cookies.get('homecoming_session'))
                search=self.client.post('/api/search',json={'confirmed':True,'parameters':{'housing_district':'Urban'}}).json()
                self.assertEqual(other.post('/api/overview/'+search['search_id']).status_code,404)
                self.assertEqual(self.client.post('/api/reset').status_code,200)
                self.assertTrue(self.client.get('/api/bootstrap').json()['connected'])
                self.assertTrue(other.get('/api/bootstrap').json()['connected'])
            self.assertEqual(self.client.post('/api/connection',json={'api_key':'replacement-key'}).status_code,404)
            self.assertEqual(self.client.delete('/api/connection').status_code,404)

    def test_https_session_and_same_origin_requests(self):
        with TestClient(app,base_url='https://homecoming.pidge.dev') as public:
            response=public.get('/api/health')
            self.assertIn('Secure',response.headers['set-cookie'])
            self.assertIn('HttpOnly',response.headers['set-cookie'])
            token=public.cookies.get('homecoming_session')
            response=public.post('/api/reset',headers={'Origin':'https://homecoming.pidge.dev'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(public.cookies.get('homecoming_session'),token)
            self.assertEqual(public.post('/api/reset',headers={'Origin':'https://other.example'}).status_code,403)
        self.assertNotIn('Secure',self.client.get('/api/health').headers['set-cookie'])

    def test_explicit_review_gate_and_hospital_selection(self):
        profile=dict(applicant_name='Synthetic Applicant',housing_district='Urban',wheelchair=True)
        with patch('homecoming.services.data.ranking') as rank,patch('homecoming.services.deepseek.overview') as overview:
            response=self.client.post('/api/search',json={'parameters':profile})
            self.assertEqual(response.status_code,422)
            response=self.client.post('/api/search',json={'confirmed':False,'parameters':profile})
            self.assertEqual(response.status_code,422)
            rank.assert_not_called();overview.assert_not_called()
        hospital=data.catalog()['lists']['hospital'][0]['id']
        profile['hospital_id']=hospital
        response=self.client.post('/api/search',json={'confirmed':True,'parameters':profile})
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result['parameters']['hospital_id'],hospital)
        self.assertEqual(len(result['estates']),109)
        self.assertEqual(result['snapshot']['run_id'],'20261016T102523Z-8e69faad')
        self.assertTrue(all(r['hospital_target_ids'] in ([],[hospital]) for r in result['estates']))

    def test_extraction_never_searches_and_is_session_scoped(self):
        self.client.get('/api/health')
        fixture=dict(applicant_name='Synthetic',wheelchair_required=True)
        with patch('homecoming.app.DEEPSEEK_API_KEY','synthetic-test-key'),patch('homecoming.services.documents.extract_pdf',return_value=fixture) as extract,patch('homecoming.services.data.ranking') as rank,patch('homecoming.services.deepseek.overview') as overview:
            response=self.client.post('/api/extract',files={'file':('form.pdf',b'%PDF- synthetic','application/pdf')})
            self.assertEqual(response.status_code,200,response.text)
            job_id=response.json()['job_id']
            for _ in range(100):
                result=self.client.get('/api/jobs/'+job_id).json()
                if result['status'] in ('done','failed'):break
                time.sleep(.01)
            self.assertEqual(result['result'],fixture)
            extract.assert_called_once_with(b'%PDF- synthetic','synthetic-test-key')
            rank.assert_not_called();overview.assert_not_called()
            with TestClient(app) as stranger:
                self.assertEqual(stranger.get('/api/jobs/'+job_id).status_code,404)

    def test_invalid_inputs_and_local_origin(self):
        for weights in [dict(bus=0,mtr=0,hospital=0),dict(bus=True,mtr=1,hospital=1),dict(bus=-1,mtr=1,hospital=1)]:
            with self.assertRaises(ValidationError):Parameters(weights=weights)
        self.assertEqual(self.client.post('/api/search',headers={'Origin':'https://example.com'},json={'confirmed':True,'parameters':{}}).status_code,403)
        self.assertEqual(self.client.post('/api/extract',files={'file':('bad.txt',b'not PDF')}).status_code,409)
        self.assertEqual(self.client.get('/api/export/png?asset=../../secrets').status_code,404)
        self.assertEqual(self.client.post('/api/walk',json={'start':{'latitude':91,'longitude':114},'end':{'latitude':22,'longitude':114}}).status_code,422)

    def test_provider_failures_are_sanitised(self):
        request=httpx.Request('POST','https://api.deepseek.com/chat/completions')
        with self.assertRaisesRegex(deepseek.ProviderError,'authenticate'):
            deepseek.checked(httpx.Response(401,request=request,json={'secret':'do-not-display'}))
        with self.assertRaisesRegex(deepseek.ProviderError,'rate limited'):
            deepseek.checked(httpx.Response(429,request=request))

    def test_provider_json_and_ocr_schema_are_checked(self):
        original_client=httpx.AsyncClient
        payload=dict(applicant_name='Synthetic Applicant',household_size=2,housing_district='Urban',
                     wheelchair_required=False,household=[dict(name=None,disability_codes=[1])],
                     hospital_mentioned=None,issues=[],evidence=[dict(page=1,text='Synthetic checked code 1')])
        def handler(request):
            body=json.loads(request.content)
            self.assertEqual(body['response_format'],{'type':'json_object'})
            self.assertEqual(body['model'],'deepseek-flash')
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]})
        transport=httpx.MockTransport(handler)
        with patch('homecoming.services.deepseek.httpx.AsyncClient',side_effect=lambda **kw:original_client(transport=transport,**kw)):
            result=deepseek.extract('synthetic-key',[{'type':'text','text':'Synthetic document'}])
        self.assertTrue(result['wheelchair_required'],'Any household member with code 1 must trigger wheelchair review')
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'choices':[{'message':{'content':'{"housing_district":"Not a valid category"}'}}]}))
        with patch('homecoming.services.deepseek.httpx.AsyncClient',side_effect=lambda **kw:original_client(transport=transport,**kw)):
            with self.assertRaisesRegex(deepseek.ProviderError,'validated'):
                deepseek.extract('synthetic-key','Synthetic document')

    def test_wrong_top_three_explanation_is_rejected(self):
        from homecoming.schemas import Overview,OverviewItem
        result=dict(estates=[dict(id='estate:real',name_en='Real estate',rank=1,ranking_status='complete',
            final_cost=10,bus_time_s=30,mtr_time_s=40,hospital_distance_m=100,
            bus_scaled_cost=5,mtr_scaled_cost=4,hospital_scaled_cost=2,missing_components=[],
            bus_warnings=[],mtr_warnings=[],hospital_warnings=[])],policy={})
        wrong=Overview(summary='Synthetic response',top_three=[OverviewItem(estate_id='estate:wrong',explanation='Wrong ID')])
        async def mock_chat(*args):return wrong
        with patch('homecoming.services.deepseek.chat',side_effect=mock_chat):
            with self.assertRaisesRegex(deepseek.ProviderError,'computed top estates'):
                deepseek.overview('synthetic-key',result,Parameters())

    def test_standard_pdf_renders_relevant_pages_in_memory(self):
        content=documents.content_from_pdf((ROOT/'assets/samples/application-form.pdf').read_bytes())
        images=[r['image_url']['url'] for r in content if r['type']=='image_url']
        self.assertEqual(len(images),3)
        for url in images:
            with Image.open(io.BytesIO(base64.b64decode(url.split(',',1)[1]))) as img:
                self.assertGreater(img.width,1000)
                self.assertGreater(img.height,200)
        labels=' '.join(r['text'] for r in content if r['type']=='text')
        self.assertNotIn('Original page 3',labels)

    def test_typed_and_scanned_demo_inputs_use_image_reading(self):
        from pypdf import PdfReader
        typed=ROOT/'assets/samples/synthetic-typed.pdf'
        scanned=ROOT/'assets/samples/synthetic-scanned.pdf'
        self.assertIn('Applicant surname: CHAN',PdfReader(typed).pages[0].extract_text())
        self.assertEqual(PdfReader(scanned).pages[0].extract_text(),'')
        for path in (typed,scanned):
            content=documents.content_from_pdf(path.read_bytes())
            self.assertEqual(sum(r['type']=='image_url' for r in content),2)
            response=self.client.get('/demo-form/'+('typed' if path==typed else 'scanned')+'.pdf')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.content,path.read_bytes())


if __name__=='__main__':
    unittest.main()
