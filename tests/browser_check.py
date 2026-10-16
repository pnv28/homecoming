"""Exercise the actual local interface with an isolated headless browser profile."""
import json
from pathlib import Path
import re
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/qa'
OUT.mkdir(parents=True,exist_ok=True)


def run():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/Applications/Helium.app/Contents/MacOS/Helium')
        context=browser.new_context(viewport={'width':1440,'height':1100},device_scale_factor=1)
        page=context.new_page();errors=[];searches=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:searches.append(request.post_data_json) if request.url.endswith('/api/search') else None)
        page.goto('http://127.0.0.1:8000',wait_until='networkidle')
        page.locator('#connection-dialog').wait_for(state='visible')
        page.screenshot(path=str(OUT/'connection.png'),full_page=True)
        page.locator('#skip-connection').click()
        page.screenshot(path=str(OUT/'upload.png'),full_page=True)
        page.locator('#applicant-name').fill('Alex Chan')
        page.locator('#district-select').select_option('Urban')
        assert len(searches)==0
        page.locator('#search-button').click()
        page.locator('#estate-list .estate-card').first.wait_for()
        page.locator('#estate-map img').wait_for()
        assert len(searches)==1
        assert page.locator('#estate-list .estate-card').count()==109
        assert 'Alex Chan' in page.locator('#results-title').inner_text()
        page.locator('#estate-map [data-quality=hd]').click()
        assert '@2x.webp' in page.locator('#estate-map img').get_attribute('src')
        page.locator('#estate-map [data-format=png]').click()
        page.locator('#estate-map img').evaluate('(img)=>img.decode()')
        assert '/api/export/png' in page.locator('#estate-map img').get_attribute('src')
        page.locator('#estate-map [data-display=svg]').click()
        svg=page.locator('#estate-map svg');svg.wait_for()
        assert page.locator('#estate-map .interactive-map-legend').count()==1
        assert svg.locator(':scope > rect').count()==0
        page.locator('#estate-map button[aria-label="Zoom in"]').click()
        assert svg.get_attribute('viewBox')!='0 0 1000 700'
        assert svg.get_attribute('data-context-bounds')=='-500 -350 2000 1400'
        page.wait_for_function('document.querySelector("#estate-map #local-path-detail polyline") !== null')
        assert page.locator('#estate-map #pedestrian-background').evaluate('(image)=>image.style.opacity')=='0'
        page.locator('#estate-map .map-viewer').screenshot(path=str(OUT/'route-detail.png'))
        for _ in range(10):page.locator('#estate-map button[aria-label="Zoom out"]').click()
        x,y,w,h=map(float,svg.get_attribute('viewBox').split())
        assert w==2000 and h==1400
        assert float(svg.locator(':scope > circle').first.get_attribute('r'))==22
        assert -500 <= x <= 1500-w and -350 <= y <= 1050-h
        # A large drag at the widest view must not reveal unmapped whitespace.
        area=svg.bounding_box()
        page.mouse.move(area['x']+area['width']/2,area['y']+area['height']/2)
        page.mouse.down();page.mouse.move(area['x']+area['width']/2+400,area['y']+area['height']/2+250,steps=5);page.mouse.up()
        assert svg.get_attribute('viewBox')=='-500 -350 2000 1400'
        page.locator('#estate-map .map-viewer').screenshot(path=str(OUT/'route-surroundings.png'))
        page.locator('#estate-map button[aria-label="Reset map zoom"]').click()
        assert svg.get_attribute('viewBox')=='0 0 1000 700'
        page.screenshot(path=str(OUT/'results.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'Map controls overflow on mobile'
        page.locator('#estate-map').screenshot(path=str(OUT/'mobile-map.png'))
        page.set_viewport_size({'width':1440,'height':1100})
        page.locator('#edit-preferences').click()
        page.locator('#hospital-select').select_option(index=2)
        page.wait_for_timeout(300)
        assert len(searches)==1,'Draft hospital changes must not search automatically'
        page.locator('#walk-tab').click()
        page.locator('#point-map svg').wait_for()
        page.locator('#point-map button[aria-label="Zoom in"]').click()
        assert page.locator('#point-map svg').get_attribute('viewBox')!='0 0 1000 650'
        assert page.locator('#start-lat').input_value()==''
        page.locator('#example-walk').click()
        assert page.locator('#start-lat').input_value()=='22.280111'
        # A nearby new coordinate exercises the real endpoint loader/calculation,
        # rather than merely retrieving the previously rehearsed route cache.
        page.locator('#start-lat').fill('22.280112')
        page.locator('#walk-button').click()
        page.locator('#walk-route-map img').wait_for(timeout=180000)
        page.locator('#walk-route-map img').evaluate('(img)=>img.decode()')
        assert '319 m' in page.locator('.walk-result-summary').inner_text()
        page.screenshot(path=str(OUT/'walk.png'),full_page=True)
        assert not errors,errors
        context.close()

        # Simulate a provider extraction while exercising the real browser form
        # and real ranking endpoint. No paid API request is needed for this check.
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();searches=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:searches.append(request.post_data_json) if request.url.endswith('/api/search') else None)
        page.route('**/api/connection',lambda route:route.fulfill(json={'connected':True,'model':'test'}))
        page.route('**/api/extract',lambda route:route.fulfill(json={'job_id':'mock-extract'}))
        fixture=dict(applicant_name='Jordan Lee',household_size=3,housing_district='Extended Urban',
                     wheelchair_required=True,household=[],hospital_mentioned=None,issues=[],
                     evidence=[dict(page=1,text='Synthetic operator-review test')])
        page.route('**/api/jobs/mock-extract',lambda route:route.fulfill(json={'status':'done','result':fixture}))
        page.route('**/api/overview/**',lambda route:route.fulfill(status=409,json={'detail':'Synthetic API-offline check.'}))
        page.goto('http://127.0.0.1:8000',wait_until='networkidle')
        page.locator('#api-key').fill('synthetic-test-key')
        page.locator('#connect-submit').click();page.locator('#connection-dialog').wait_for(state='hidden')
        page.locator('#pdf-input').set_input_files(str(ROOT/'assets/samples/application-form.pdf'))
        page.wait_for_function('document.getElementById("applicant-name").value === "Jordan Lee"')
        page.wait_for_timeout(400)
        assert len(searches)==0,'Extraction must stop at the operator review form'
        assert page.locator('[name=wheelchair][value=true]').is_checked()
        page.locator('#hospital-select').select_option(index=3)
        hospital=page.locator('#hospital-select').input_value()
        page.locator('#search-button').click();page.locator('#estate-list .estate-card').first.wait_for()
        assert len(searches)==1
        assert searches[0]['parameters']['hospital_id']==hospital
        assert searches[0]['parameters']['wheelchair'] is True
        assert searches[0]['confirmed'] is True
        context.close()

        context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        page=context.new_page();page.goto('http://127.0.0.1:8000',wait_until='networkidle')
        page.locator('#skip-connection').click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'Horizontal overflow on mobile'
        page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
        context.close();browser.close()
        assert not errors,errors
        report=dict(status='passed',manual_search=True,operator_gate=True,preferred_hospital=True,
                    hd_webp=True,png=True,svg_zoom_reset=True,svg_bounded_pan=True,svg_surrounding_context=True,
                    close_zoom_original_vectors=True,point_selection_map=True,on_demand_walk=True,
                    mobile_no_overflow=True,javascript_errors=errors)
        (OUT/'browser_report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    run()
