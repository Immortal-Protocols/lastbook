"""Browser-linked readings keep the destination's metadata without saved-page privileges."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from engine import reading_links as links

ROOT = Path(__file__).resolve().parents[2]
TOKEN = 'a1' * 16

def fixture():
    records = [dict(id='source',path='pages/first.html',kind='html',title='First'),
               dict(id='下一页 é/#',path='pages/next é.html',kind='html',title='Next <img src=x>'),
               dict(id='manual',path='documents/manual.pdf',kind='pdf',title='Manual'),
               dict(id='movie',path='videos/movie.mp4',kind='video',title='Movie'),
               dict(id='unknown',path='assets/unknown.bin',kind='bin',title='Unsupported')]
    return {'by_id':{r['id']:r for r in records},'by_path':{r['path']:r for r in records}}

class ReadingLinks(unittest.TestCase):
    def setUp(self):
        self.cat=fixture();self.source=self.cat['by_id']['source']
    def rewrite(self,data):
        return links.rewrite(data,self.source,self.cat,TOKEN,lambda p:True)
    def test_real_anchors_preserve_text_and_ignore_raw_text_comments_and_fake_tags(self):
        source=b'''<meta name=x content="<a href='next%20%C3%A9.html'>"><!-- <a href=next%20%C3%A9.html> -->
<script>const x="<a href='next%20%C3%A9.html'>"</script><textarea><a href=next%20%C3%A9.html></textarea>
<p>Original text <a class='x' href='next%20%C3%A9.html'>next</a>.</p>'''
        result=self.rewrite(source)
        self.assertEqual(result.count(b'/ui/reading-link?'),1)
        self.assertIn(b'<p>Original text <a class="x"',result)
        self.assertTrue(result.endswith(b'>next</a>.</p>'))
        self.assertIn(source.split(b'<p>')[0],result)
    def test_local_unicode_records_and_pdf_page_route(self):
        target,frag=links.destination('next%20%C3%A9.html#section',self.source,self.cat,lambda p:True)
        self.assertEqual(target['id'],'下一页 é/#')
        self.assertEqual(links.route(target),'#/read/%E4%B8%8B%E4%B8%80%E9%A1%B5%20%C3%A9%2F%23')
        result=self.rewrite(b'<a href="../documents/manual.pdf#page=7">manual</a>')
        self.assertIn(b'page=7',result)
        self.assertEqual(links.route(self.cat['by_id']['manual'],'page=7'),'#/read/manual?p=7&view=pdf')
        self.assertEqual(links.route(self.cat['by_id']['movie']),'#/watch/movie')
    def test_external_unknown_self_anchors_missing_files_and_ambiguous_attributes_keep_old_path(self):
        for href in ['#anchor','first.html#anchor','https://example.org/pages/next%20%C3%A9.html','//example.org/x',
                     '/api/setup/state','/pages/no.html','/assets/unknown.bin','/pages/%2e%2e/documents/manual.pdf','/pages/a%2fb.html','next\\x.html']:
            with self.subTest(href=href):self.assertIsNone(links.destination(href,self.source,self.cat,lambda p:True))
        self.assertIsNone(links.destination('next%20%C3%A9.html',self.source,self.cat,lambda p:False))
        for data in [b'<a href="next%20%C3%A9.html" href="first.html">x</a>',b'\xff<a href="next%20%C3%A9.html">x</a>']:
            self.assertEqual(self.rewrite(data),data)
        source=b'<a href="next%20%C3%A9.html">x</a>'
        self.assertEqual(links.rewrite(source,self.source,self.cat,'bad',lambda p:True),source)
    def test_many_links_preserve_order_and_check_each_file_once(self):
        calls=[];source=('\n<a href="next%20%C3%A9.html">字</a>'*10000).encode()
        result=links.rewrite(source,self.source,self.cat,TOKEN,lambda p:calls.append(p) or True)
        self.assertEqual(result.count(b'/ui/reading-link?'),10000)
        self.assertEqual(result.count('字'.encode()),10000)
        self.assertEqual(calls,['pages/next é.html'])
    def test_link_expansion_is_bounded_and_falls_back_without_partial_changes(self):
        source=b'<a href="next%20%C3%A9.html">next</a>'*10
        with patch.object(links,'MAX_PAGE',1024):
            self.assertEqual(self.rewrite(source),source)

    def test_relay_refuses_wrong_source_target_token_and_escapes_metadata(self):
        params=dict(source='source',target='下一页 é/#',token=TOKEN)
        data=links.relay(self.cat,params,lambda p:True)
        self.assertIn(b'data-automatic="no"',data)
        self.assertIn(b'Next &lt;img src=x&gt;',data)
        self.assertNotIn(b'<img',data)
        self.assertIn(b'data-automatic="yes"',links.relay(self.cat,params,lambda p:True,True))
        for change in [dict(source='manual'),dict(target='source'),dict(target='unknown'),dict(token='x'),dict(page='7'),dict(extra='x')]:
            self.assertIsNone(links.relay(self.cat,{**params,**change},lambda p:True))
        self.assertIsNone(links.relay(self.cat,params,lambda p:False))

class HTTPReadingLinks(unittest.TestCase):
    def test_real_http_headers_user_activation_and_duplicate_parameters(self):
        import server
        cat=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            lib=Path(tmp)
            for r in cat['by_id'].values():
                p=lib/r['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'<a href="next%20%C3%A9.html">next</a>')
            with patch.object(server,'LIB',lib),patch.object(server.library,'ROOT',lib),patch.object(server,'catalog',return_value=cat):
                http=server.HTTPServer(('127.0.0.1',0),server.Handler)
                thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
                try:
                    origin='http://127.0.0.1:'+str(http.server_port)
                    with urlopen(origin+'/pages/first.html?lb-reader='+TOKEN) as r:
                        page=r.read();self.assertIn(b'/ui/reading-link?',page)
                        self.assertEqual(r.headers['Content-Security-Policy'],server.Handler.SAVED_PAGE_CSP)
                        self.assertNotIn('allow-scripts',r.headers['Content-Security-Policy'])
                        self.assertNotIn('allow-same-origin',r.headers['Content-Security-Policy'])
                    url=origin+'/ui/reading-link?'+urlencode(dict(source='source',target='下一页 é/#',token=TOKEN))
                    with urlopen(url) as r:
                        self.assertIn(b'data-automatic="no"',r.read());self.assertEqual(r.headers['Cache-Control'],'no-store')
                        self.assertNotIn('unsafe-inline',r.headers['Content-Security-Policy'])
                    with urlopen(Request(url,method='HEAD')) as r:
                        self.assertEqual(r.status,200);self.assertEqual(r.read(),b'');self.assertGreater(int(r.headers['Content-Length']),0)
                    request=Request(url,headers={'Sec-Fetch-User':'?1','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'iframe'})
                    with urlopen(request) as r:self.assertIn(b'data-automatic="yes"',r.read())
                    for wrong in [url+'&target=manual',url.replace(TOKEN,'bad'),url.replace('source=source','source=manual')]:
                        with self.assertRaises(HTTPError) as e:urlopen(wrong)
                        self.assertEqual(e.exception.code,400)
                        e.exception.close()
                    with urlopen(origin+'/pages/first.html') as r:self.assertNotIn(b'/ui/reading-link?',r.read())
                finally:http.shutdown();http.server_close();thread.join(3)

@unittest.skipUnless(shutil.which('node'),'Node is required')
class ParentProtocol(unittest.TestCase):
    def test_parent_accepts_only_connected_same_origin_active_frame_matching_source_token_and_local_route(self):
        program=r'''
const fs=require('fs'),vm=require('vm');let handler=null,removed=0;
const window={addEventListener:(t,f)=>handler=f,removeEventListener:(t,f)=>{if(handler===f){handler=null;removed++}}};
const context={window,location:{origin:'http://127.0.0.1:8890'},document:{getElementById:()=>null}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const frame={isConnected:true,contentWindow:{}},navigations=[],token='a1'.repeat(16);
const listen=()=>window.LastbookReadingLinks.listen(frame,'source',token,r=>navigations.push(r));
const good={origin:context.location.origin,source:frame.contentWindow,data:{type:'lastbook-reading-link',source:'source',token,route:'#/read/next'}};
for(const change of [{origin:'null'},{origin:'https://example.org'},{source:{}},{data:{...good.data,token:'b1'.repeat(16)}},{data:{...good.data,source:'other'}},{data:{...good.data,route:'https://example.org'}},{data:{...good.data,route:'#/ask'}}]){const stop=listen();handler({...good,...change});stop()}
if(navigations.length)throw Error('Accepted an invalid message');
frame.isConnected=false;listen();handler(good);if(navigations.length)throw Error('Accepted old frame');frame.isConnected=true;
listen();handler(good);if(navigations.join()!=='#/read/next'||handler!==null)throw Error('Valid navigation failed or listener retained');
listen();handler({...good,data:{...good.data,route:'#/read/manual?p=7&view=pdf'}});
if(navigations[1]!=='#/read/manual?p=7&view=pdf')throw Error('Lost PDF page');
process.stdout.write('protocol passed');
'''
        result=subprocess.run([shutil.which('node'),'-e',program,str(ROOT/'web/reading-links.js')],capture_output=True,text=True,check=True,timeout=15)
        self.assertEqual(result.stdout,'protocol passed')

    def test_relay_button_requires_a_real_click_when_activation_metadata_is_absent(self):
        program=r'''const fs=require('fs'),vm=require('vm');
const run=automatic=>{let click,posted=[];const button={addEventListener:(t,f)=>click=f};
const data={token:'a1'.repeat(16),source:'source',route:'#/read/next',automatic};
const window={parent:{postMessage:(...v)=>posted.push(v)}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{window,location:{origin:'http://127.0.0.1:8890'},document:{body:{dataset:data},getElementById:()=>button}});
return {click,posted}};
const manual=run('no');if(manual.posted.length)throw Error('Automatic navigation without activation metadata');
manual.click({isTrusted:false});if(manual.posted.length)throw Error('Synthetic button accepted');
manual.click({isTrusted:true});if(manual.posted.length!==1||manual.posted[0][1]!=='http://127.0.0.1:8890')throw Error('Trusted fallback failed');
const automatic=run('yes');if(automatic.posted.length!==1)throw Error('Activated navigation failed');'''
        subprocess.run([shutil.which('node'),'-e',program,str(ROOT/'web/reading-links.js')],capture_output=True,text=True,check=True,timeout=15)
