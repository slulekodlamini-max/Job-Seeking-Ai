import os, io, json, re, sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    from ddgs import DDGS
except Exception:
    DDGS = None
try:
    import requests
except Exception:
    requests = None
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
try:
    from docx import Document
except Exception:
    Document = None

st.set_page_config(page_title='Job-Seeking AI', page_icon='🤖', layout='wide')
DB = Path('job_agent.db')
WBHO_FILE = Path('WBHO_Experience_Master.txt')

DEFAULT = {
    'name': 'S’luleko Gcinani Dlamini',
    'email': 'slulekogcinani@gmail.com',
    'phone': '+27 71 299 4578',
    'location': 'Cape Town, Western Cape, South Africa',
    'qualification': 'Diploma in Civil Engineering, CPUT, awarded effective 1 January 2026',
    'experience': 'WBHO Engineer; Student Engineer/WIL June–December 2025 at Park Place Apartments; Engineer January–12 June 2026 at Park Place Apartments; Engineer from 15 June 2026 at Later Living',
    'registration': 'ECSA Candidate Engineer',
    'roles': 'Graduate Civil Engineer, Candidate Civil Engineer, Junior Civil Engineer, Graduate Site Engineer, Site Engineer, Junior Project Engineer, Civil Engineering Technician',
    'skills': 'Construction supervision, structural construction, building-core works, quality control, inspections, site administration, drawings, site instructions, store requisitions, JSA, surveying, Excel, Microsoft Project, PowerPoint, PROKON, Autodesk Construction Cloud, Synergy, teamwork, communication, problem solving, time management',
    'preferred_locations': 'Cape Town, Western Cape; Johannesburg/Gauteng; KwaZulu-Natal; South Africa'
}


def conn():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS applications(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, company TEXT, title TEXT,
        location TEXT, url TEXT, match INTEGER, status TEXT, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, scanned TEXT, title TEXT, company TEXT,
        location TEXT, url TEXT UNIQUE, snippet TEXT, description TEXT, match INTEGER,
        gaps TEXT DEFAULT '', source TEXT DEFAULT '')''')
    c.commit()
    return c


def profile_load():
    c = conn(); r = c.execute('SELECT data FROM profile WHERE id=1').fetchone()
    if r:
        p = json.loads(r[0])
        changed = False
        for k, v in DEFAULT.items():
            if k not in p or not p[k]: p[k] = v; changed = True
        if changed: profile_save(p)
        return p
    profile_save(DEFAULT.copy()); return DEFAULT.copy()


def profile_save(p):
    c = conn(); c.execute('INSERT OR REPLACE INTO profile VALUES(1,?)', (json.dumps(p),)); c.commit()


def extract_bytes(name, b):
    n = name.lower()
    if n.endswith('.pdf') and PdfReader:
        return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)
    if n.endswith('.docx') and Document:
        doc = Document(io.BytesIO(b))
        return '\n'.join([p.text for p in doc.paragraphs] + [cell.text for t in doc.tables for row in t.rows for cell in row.cells])
    return b.decode('utf-8', errors='ignore')


def extract(upload):
    if not upload: return ''
    return extract_bytes(upload.name, upload.getvalue())


def ask(prompt, system='You are a careful South African career assistant. Never invent qualifications, employers, dates, registrations, software, responsibilities, achievements or application facts. Use only verified candidate information supplied in the prompt. Clearly label missing information.'):
    key = st.secrets.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))
    if not key or OpenAI is None:
        return ''
    try:
        client = OpenAI(api_key=key)
        model = st.secrets.get('OPENAI_MODEL', 'gpt-5-mini')
        return client.responses.create(model=model, instructions=system, input=prompt).output_text
    except Exception as e:
        return f'AI_ERROR: {e}'


def ai_available():
    return bool(st.secrets.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))) and OpenAI is not None


def search(q, n=20):
    if DDGS is None: return []
    try:
        return list(DDGS().text(q, max_results=n))
    except Exception:
        return []


def fetch_page(url):
    if not requests or not BeautifulSoup or not url.startswith(('http://','https://')): return ''
    try:
        r = requests.get(url, timeout=12, headers={'User-Agent':'Mozilla/5.0 Job-Seeking-AI'})
        if r.status_code >= 400: return ''
        soup = BeautifulSoup(r.text, 'html.parser')
        for x in soup(['script','style','noscript']): x.decompose()
        text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
        return text[:30000]
    except Exception:
        return ''


def company_from_result(x):
    title = x.get('title','')
    # Search result titles often use "Job - Company" or "Company | Job".
    parts = re.split(r'\s+[|–—-]\s+', title)
    return parts[-1].strip() if len(parts) > 1 else ''


def score(title, body, p):
    t = (title + ' ' + body).lower()
    s = 30
    if any(x in t for x in ['graduate','junior','entry level','trainee','candidate engineer']): s += 18
    role_hits = sum(1 for r in p['roles'].split(',') if r.strip() and any(w in t for w in r.lower().split() if len(w) > 3))
    skill_hits = sum(1 for x in p['skills'].split(',') if x.strip() and x.strip().lower() in t)
    s += min(25, role_hits * 5) + min(20, skill_hits * 3)
    if any(x in t for x in ['civil','construction','infrastructure','structural','site engineer']): s += 7
    return min(100, s)


def scan_one(p, loc, role, n=12):
    out=[]; seen=set()
    queries = [f'"{role}" jobs "{loc}" civil engineering', f'{role} vacancies {loc} construction']
    for q in queries:
        for x in search(q, n):
            title=x.get('title','').strip(); url=x.get('href','').strip(); snippet=x.get('body','').strip()
            if not title or not url or url in seen: continue
            seen.add(url)
            desc = fetch_page(url)
            body = (snippet + ' ' + desc[:12000]).strip()
            out.append({'scanned':datetime.now().isoformat(timespec='minutes'),'title':title,'company':company_from_result(x),'location':loc,'url':url,'snippet':snippet[:700],'description':desc[:20000],'match':score(title,body,p),'gaps':'','source':urlparse(url).netloc})
    return out


def autonomous_scan(p, locations, roles, minimum):
    rows=[]
    for loc in locations:
        for role in roles:
            rows.extend(scan_one(p, loc, role, 8))
    # deduplicate and rank
    best={}
    for r in rows:
        if r['match'] < minimum: continue
        u=r['url']; best[u]=r if u not in best or r['match']>best[u]['match'] else best[u]
    ranked=sorted(best.values(), key=lambda x:(x['match'], x['scanned']), reverse=True)
    c=conn()
    for r in ranked:
        try:
            c.execute('''INSERT INTO jobs(scanned,title,company,location,url,snippet,description,match,gaps,source)
                         VALUES(?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(url) DO UPDATE SET scanned=excluded.scanned,title=excluded.title,
                         company=excluded.company,location=excluded.location,snippet=excluded.snippet,
                         description=excluded.description,match=excluded.match,source=excluded.source''', tuple(r.values()))
        except Exception: pass
    c.commit(); return ranked


def job_df():
    return pd.read_sql_query('SELECT * FROM jobs ORDER BY match DESC,id DESC LIMIT 250', conn())


def add_application(j, status='Prepared', notes=''):
    c=conn(); c.execute('INSERT INTO applications(created,company,title,location,url,match,status,notes) VALUES(?,?,?,?,?,?,?,?)',
        (datetime.now().isoformat(timespec='minutes'),j.get('company',''),j.get('title',''),j.get('location',''),j.get('url',''),int(j.get('match',0)),status,notes)); c.commit()

p=profile_load()

st.title('🤖 Job-Seeking AI')
st.caption('Autonomous job discovery → vacancy reading → matching → application preparation → tracking')

with st.sidebar:
    st.header('⚙️ Agent settings')
    locs = st.text_area('Locations', p['preferred_locations'])
    roles = st.text_area('Target roles', p['roles'])
    minimum = st.slider('Minimum match', 0, 100, 65)
    if st.button('💾 Save settings'):
        p['preferred_locations']=locs; p['roles']=roles; profile_save(p); st.success('Saved')
    st.divider()
    st.write('AI connection:', '🟢 Connected' if ai_available() else '🔴 Add OPENAI_API_KEY')
    st.caption('The agent never bypasses CAPTCHAs, login controls or site protections, and never falsely marks an application as submitted.')

locations=[x.strip() for x in locs.split(';') if x.strip()] or ['South Africa']
roles_list=[x.strip() for x in roles.split(',') if x.strip()] or ['Civil Engineer']

tabs=st.tabs(['🏠 Dashboard','🤖 Autonomous Agent','📄 Application Builder','📋 Tracker','🎤 Interview AI','👤 Master Profile'])

with tabs[0]:
    jobs=job_df(); apps=pd.read_sql_query('SELECT * FROM applications ORDER BY id DESC',conn())
    a,b,c,d=st.columns(4); a.metric('Vacancies found',len(jobs)); b.metric('Prepared/Applied',len(apps)); c.metric('Interviews',int((apps.status=='Interview').sum()) if not apps.empty else 0); d.metric('Offers',int((apps.status=='Offer').sum()) if not apps.empty else 0)
    st.subheader('⭐ Best matches')
    if jobs.empty: st.info('Run the Autonomous Agent to find jobs.')
    else:
        view=jobs[jobs.match>=minimum][['match','title','company','location','url']].head(20)
        st.dataframe(view, hide_index=True, use_container_width=True)

with tabs[1]:
    st.subheader('🤖 Autonomous Job Agent')
    st.write('One action searches across your selected roles and locations, opens public vacancy pages where possible, reads the available text, scores the vacancy against your profile, and saves the best matches.')
    if st.button('🚀 RUN FULL JOB AGENT', type='primary', use_container_width=True):
        with st.spinner('Searching vacancies, opening public pages and ranking matches...'):
            rows=autonomous_scan(p, locations, roles_list, minimum)
        st.success(f'Agent finished. {len(rows)} strong matches saved.')
        st.rerun()
    jobs=job_df()
    if not jobs.empty:
        for _,j in jobs[jobs.match>=minimum].head(30).iterrows():
            with st.container(border=True):
                st.markdown(f"### {int(j.match)}% — {j.title}")
                st.write(f"**{j.company or 'Employer not identified'} · {j.location} · {j.source}**")
                st.write(j.snippet)
                cols=st.columns([1,1,2])
                cols[0].link_button('Open vacancy',j.url)
                if cols[1].button('📌 Prepare', key=f"prep{j.id}"):
                    add_application(j.to_dict(), 'Prepared', 'Found by Autonomous Job Agent')
                    st.success('Added to tracker as Prepared.')
                if j.description:
                    with st.expander('Vacancy text read by agent'):
                        st.write(j.description[:10000])

with tabs[2]:
    st.subheader('📄 Application Builder')
    st.write('Upload one or more candidate documents. The agent combines them with the verified Master Profile and tailors the application without inventing facts.')
    uploads=st.file_uploader('Candidate documents (CV, qualification, certificates, experience notes)', type=['pdf','docx','txt'], accept_multiple_files=True)
    docs='\n\n'.join(f'--- {u.name} ---\n{extract(u)[:20000]}' for u in uploads) if uploads else ''
    jobs=job_df()
    if jobs.empty: st.info('Find vacancies first.')
    else:
        choices={f"{int(r.match)}% — {r.title} — {r.company or 'Unknown'}":r.id for _,r in jobs.iterrows()}
        selected=st.selectbox('Vacancy',list(choices))
        j=jobs[jobs.id==choices[selected]].iloc[0]
        if st.button('✨ Build complete application pack',type='primary'):
            prompt=f'''MASTER PROFILE:\n{json.dumps(p,indent=2)}\n\nSOURCE DOCUMENTS:\n{docs[:50000]}\n\nVACANCY:\nTitle: {j.title}\nCompany: {j.company}\nLocation: {j.location}\nURL: {j.url}\nSearch snippet: {j.snippet}\nVacancy page text: {j.description[:25000]}\n\nCreate a complete truthful application pack with:\n1. Match score and reasons.\n2. Genuine experience/skills to emphasise.\n3. Gaps or requirements not verified.\n4. ATS-friendly tailored CV content (profile, key skills, employment bullets, education).\n5. Tailored cover letter.\n6. Short recruiter/LinkedIn message.\n7. Five application-form answers likely to be useful.\n8. Interview preparation points.\nNever create fake project values, quantities, design responsibility, professional sign-off, qualifications, software or achievements. If something is not verified, say so.'''
            with st.spinner('AI is tailoring the application...'): res=ask(prompt)
            if not res: st.error('Connect OPENAI_API_KEY first.');
            else:
                st.markdown(res); st.download_button('⬇️ Download application pack',res,file_name='tailored_application_pack.txt')

with tabs[3]:
    st.subheader('📋 Application Tracker')
    with st.form('add'):
        company=st.text_input('Company'); title=st.text_input('Position'); url=st.text_input('URL'); status=st.selectbox('Status',['Prepared','Applied','Interview','Rejected','Offer','Withdrawn']); notes=st.text_area('Notes')
        if st.form_submit_button('Add application'):
            add_application({'company':company,'title':title,'location':'','url':url,'match':0},status,notes); st.success('Saved')
    apps=pd.read_sql_query('SELECT * FROM applications ORDER BY id DESC',conn())
    st.dataframe(apps,hide_index=True,use_container_width=True)
    if not apps.empty: st.download_button('Export CSV',apps.to_csv(index=False),file_name='job_applications.csv')

with tabs[4]:
    st.subheader('🎤 Interview AI')
    role=st.text_input('Role','Graduate Civil Engineer'); company=st.text_input('Company',''); jd=st.text_area('Job description',height=180)
    if st.button('Generate interview pack'):
        res=ask(f'''Candidate:\n{json.dumps(p,indent=2)}\nRole: {role}\nCompany: {company}\nJD: {jd}\nCreate 10 likely questions, truthful STAR answer frameworks using only the candidate's verified experience, 5 technical questions, 5 questions to ask the employer, and a 60-second introduction.''')
        if res: st.markdown(res)
        else: st.error('Connect OPENAI_API_KEY first.')

with tabs[5]:
    st.subheader('👤 Master Candidate Profile')
    st.write('This profile is the source of truth used by the agent. New verified information should replace outdated information rather than being mixed with it.')
    with st.form('pf'):
        new={k:st.text_area(k.replace('_',' ').title(),v) for k,v in p.items()}
        if st.form_submit_button('Save Master Profile'):
            profile_save(new); p=new; st.success('Profile saved')
    st.divider()
    if WBHO_FILE.exists():
        st.success('WBHO Experience Master loaded automatically.')
        with st.expander('View WBHO source'):
            st.text(WBHO_FILE.read_text(encoding='utf-8'))
    st.info('Keep API keys and private candidate documents out of GitHub. Use Streamlit Secrets for OPENAI_API_KEY.')

st.divider(); st.caption('Autonomy note: the agent can automate public-web discovery, vacancy reading, ranking and application preparation. Final submission remains a user-controlled step unless an employer provides an approved application API/workflow.')
