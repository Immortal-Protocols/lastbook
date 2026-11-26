"""Source language reaches plain text and local speech independently of UI language."""
import json, shutil, subprocess, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node')

VOICE = r'''
const fs=require('fs'),options=JSON.parse(process.argv[2]),spoken=[];
const voices=options.voices.map(v=>({...v,name:v.lang}));
const synth={getVoices:()=>voices,speak:u=>spoken.push({text:u.text,lang:u.lang,voice:u.voice.lang}),cancel(){},addEventListener(){}};
const document={addEventListener(){},removeEventListener(){}};
class Utterance{constructor(t){this.text=t}}
let click;const btn={hidden:true,classList:{toggle(){}},setAttribute(){},addEventListener:(k,f)=>click=f};
const src=fs.readFileSync(process.argv[1],'utf8');
const Speak=new Function('$','navigator','document','speechSynthesis','SpeechSynthesisUtterance',src+'\nreturn Speak;')(
 ()=>null,{language:options.navigator||'en-AU'},document,synth,Utterance);
(async()=>{
 const leave=Speak.attach(btn,async()=>options.text||'استعد للفيضانات',null,options.language);
 const ready=await Speak.ready(options.language);await Promise.resolve();
 await click();const shown=!btn.hidden;leave();
 process.stdout.write(JSON.stringify({ready,shown,spoken}));
})();
'''
READER = r'''
const fs=require('fs'),vm=require('vm'),options=JSON.parse(process.argv[2]);
const src=fs.readFileSync(process.argv[1],'utf8'),start=src.indexOf('function plainReadingText('),end=src.indexOf('/* --------------------------------------------------------------- wiki',start);
if(start<0||end<0)throw Error('reader not found');
const main={innerHTML:''},body={innerHTML:''},button={},languages=[];
const env={main,routeSeq:1,stale:()=>false,swap(){},setTitle(){},remember(){},backButton:()=>'',askLink:()=>'',saveButton:()=>'',ico:()=>'',fileUrl:p=>'/'+p,
 esc:x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'),
 innerWidth:800,sessionStorage:{getItem:()=>null,removeItem(){}},Speak:{attach:(b,t,n,language)=>{languages.push(language);return()=>{}}},
 $:sel=>sel==='[data-speak]'?button:sel==='#docbody'?body:null,$$:()=>[],
 api:async url=>url.startsWith('/api/doc/')?{id:'ar-doc',title:'الفيضانات',publisher:'Publisher',kind:'html',path:'pages/test.html',trust:'Reference',language:options.language}:{text:options.text}};
vm.createContext(env);vm.runInContext(src.slice(start,end),env);
(async()=>{await env.reader('ar-doc',1,'','text');process.stdout.write(JSON.stringify({html:body.innerHTML,speechLanguage:languages[0]}));})();
'''

class PublicLanguage(unittest.TestCase):
    def test_document_response_includes_explicit_source_language(self):
        import server
        record = dict(id='ar-doc', title='الفيضانات', kind='html', path='pages/test.html', language='ar', publisher='Publisher')
        self.assertEqual(server.public(record, full=True)['language'], 'ar')
        self.assertNotIn('language', server.public(record))

    def test_language_is_not_invented_for_unlabelled_records(self):
        import server
        record = dict(id='unknown', title='Unlabelled', kind='html', path='pages/unknown.html')
        self.assertNotIn('language', server.public(record, full=True))

@unittest.skipUnless(NODE, 'needs Node')
class DocumentLanguage(unittest.TestCase):
    def js(self, source, script, options):
        result = subprocess.run([NODE, '-e', source, str(ROOT / script), json.dumps(options)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def voice(self, language, voices, navigator='en-AU'):
        return self.js(VOICE, 'web/speak.js', dict(language=language, voices=voices, navigator=navigator))

    def test_document_language_wins_over_default_computer_voice(self):
        result = self.voice('ar', [dict(lang='en-AU', localService=True, default=True), dict(lang='ar-EG', localService=True)])
        self.assertTrue(result['ready'] and result['shown'])
        self.assertEqual(result['spoken'][0]['voice'], 'ar-EG')
        self.assertEqual(result['spoken'][0]['lang'], 'ar-EG')

    def test_exact_document_locale_wins_over_other_default_local_voice(self):
        result = self.voice('en-GB', [dict(lang='en-US', localService=True, default=True), dict(lang='en-GB', localService=True)])
        self.assertEqual(result['spoken'][0]['voice'], 'en-GB')

    def test_no_matching_local_voice_hides_button_and_never_uses_remote_or_english(self):
        result = self.voice('ar', [dict(lang='en-AU', localService=True, default=True), dict(lang='ar-SA', localService=False)])
        self.assertFalse(result['ready'] or result['shown'])
        self.assertEqual(result['spoken'], [])

    def test_no_document_language_keeps_computer_language_behavior(self):
        result = self.voice(None, [dict(lang='en-AU', localService=True, default=True), dict(lang='ar-SA', localService=True)])
        self.assertEqual(result['spoken'][0]['voice'], 'en-AU')

    def test_chinese_script_tag_can_use_matching_local_language_family(self):
        result = self.voice('zh-Hant', [dict(lang='en-AU', localService=True, default=True), dict(lang='zh-TW', localService=True)])
        self.assertEqual(result['spoken'][0]['voice'], 'zh-TW')

    def test_reader_propagates_language_to_speech_and_plain_text(self):
        result = self.js(READER, 'web/app.js', dict(language='ar', text='استعد للفيضانات\nEnglish source notes'))
        self.assertEqual(result['speechLanguage'], 'ar')
        self.assertIn('class="pagetext" lang="ar" dir="auto"', result['html'])
        self.assertIn('استعد للفيضانات\nEnglish source notes', result['html'])
        self.assertIn('unicode-bidi:plaintext', (ROOT / 'web/app.css').read_text())

    def test_untrusted_language_metadata_cannot_create_html_attributes(self):
        value = 'ar" onmouseover="alert(1)'
        result = self.js(READER, 'web/app.js', dict(language=value, text='Content'))
        self.assertIn('lang="ar&quot; onmouseover=&quot;alert(1)"', result['html'])
        self.assertNotIn('lang="ar" onmouseover=', result['html'])

    def test_numeric_runs_keep_digits_separators_and_signs_inside_ltr_isolates(self):
        text = 'اختبار 131 450 و 000 ثم -18 °C و 0.5 و 10:30 و ١٣١ ٤٥٠.'
        result = self.js(READER, 'web/app.js', dict(language='ar', text=text))
        for value in ['131 450', '000', '-18', '0.5', '10:30', '١٣١ ٤٥٠']:
            self.assertIn('<bdi dir="ltr">' + value + '</bdi>', result['html'])
        from html.parser import HTMLParser
        class Text(HTMLParser):
            def __init__(self): super().__init__(); self.parts = []
            def handle_data(self, value): self.parts.append(value)
        parsed = Text(); parsed.feed(result['html'])
        self.assertTrue(''.join(parsed.parts).endswith(text))

if __name__ == '__main__':
    unittest.main()
