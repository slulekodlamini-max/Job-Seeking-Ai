import os, io, json, re, sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
try:
    from openai import OpenAI
except Exception: OpenAI=None
try:
    from ddgs import DDGS
except Exception: DDGS=None
try:
    from pypdf import PdfReader
except Exception: PdfReader=None
try:
    from docx import Document
except Exception: Document=None

st.set_page_config(page_title='Job-Seeking AI',page_icon='🤖',layout='wide')
DB=Path('job_agent.db')
DEFAULT={
'name':'Your Name','email':'','phone':'','location':'Cape Town, Western Cape, South Africa',
'qualification':'Diploma in Civil Engineering, CPUT, completed 2025',
'experience':'Work Integrated Learning at WBHO, June–December 2025',
'registration':'ECSA Candidate',
'roles':'Graduate Civil Engineer, Candidate Civil Engineer, Junior Civil Engineer, Graduate Site Engineer, Site Engineer, Junior Project Engineer, Civil Engineering Technician',
'skills':'Excel, Microsoft Project, PowerPoint, PROKON, surveying, teamwork, communication, problem solving, civil engineering',
'preferred_locations':'Cape Town, Western Cape; Johannesburg/Gauteng; KwaZulu-Natal; South Africa'}

def conn():
 c=sqlite3.connect(DB); c.execute('CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY AUTOINCREMENT,created TEXT,company TEXT,title TEXT,location TEXT,url TEXT,match INTEGER,status TEXT,notes TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,scanned TEXT,title TEXT,company TEXT,location TEXT,url TEXT,snippet TEXT,match INTEGER)'); c.commit(); return c

def profile_load():
 c=conn(); r=c.execute('SELECT data FROM profile WHERE id=1').fetchone()
 if r:return json.loads(r[0])
 c.execute('INSERT INTO profile VALUES(1,?)',(json.dumps(DEFAULT),));c.commit();return DEFAULT.copy()

def profile_save(p):
 c=conn();c.execute('INSERT OR REPLACE INTO profile VALUES(1,?)',(json.dumps(p),));c.commit()

def extract(upload):
 if not upload:return ''
 b=upload.getvalue(); n=upload.name.lower()
 if n.endswith('.pdf') and PdfReader:return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages)
 if n.endswith('.docx') and Document:return '\n'.join(p.text for p in Document(io.BytesIO(b)).paragraphs)
 return b.decode('utf-8',errors='ignore')

def ask(prompt,system='You are a careful South African career assistant. Never invent qualifications, employers, dates, registrations, skills or achievements.'):
 key=st.secrets.get('OPENAI_API_KEY',os.getenv('OPENAI_API_KEY',''))
 if not key or OpenAI is None:return 'AI is not connected yet. Add OPENAI_API_KEY in Streamlit App Settings → Secrets.'
 client=OpenAI(api_key=key); model=st.secrets.get('OPENAI_MODEL','gpt-5-mini')
 return client.responses.create(model=model,instructions=system,input=prompt).output_text

def search(q,n=20):
 if DDGS is None:return []
 try:return list(DDGS().text(q,max_results=n))
 except Exception:return []

def score(title,body,p):
 t=(title+' '+body).lower(); s=35
 if any(x in t for x in ['graduate','junior','entry level','trainee']):s+=20
 s+=min(20,sum(1 for r in p['roles'].split(',') if r.strip() and any(w in t for w in r.lower().split() if len(w)>3))*4)
 s+=min(20,sum(1 for x in p['skills'].split(',') if x.strip().lower() in t)*3)
 if 'civil' in t or 'construction' in t or 'infrastructure' in t:s+=5
 return min(100,s)

def scan(p,loc,role):
 out=[]; seen=set(); q=f'"{role}" "{loc}" civil engineering jobs South Africa'
 for x in search(q,25):
  title=x.get('title','').strip(); url=x.get('href','').strip(); body=x.get('body','').strip()
  if not title or not url or url in seen:continue
  seen.add(url); out.append({'scanned':datetime.now().isoformat(timespec='minutes'),'title':title,'company':'','location':loc,'url':url,'snippet':body[:600],'match':score(title,body,p)})
 return out

def save_jobs(rows):
 c=conn()
 for r in rows:c.execute('INSERT INTO jobs(scanned,title,company,location,url,snippet,match) VALUES(?,?,?,?,?,?,?)',tuple(r.values()))
 c.commit()

p=profile_load()
st.title('🤖 Job-Seeking AI');st.caption('Find → evaluate → prepare → track → interview')
with st.sidebar:
 st.header('🎯 Search settings'); locs=st.text_area('Locations',p['preferred_locations']); roles=st.text_area('Target roles',p['roles']); minimum=st.slider('Minimum match',0,100,75)
 if st.button('💾 Save settings'):p['preferred_locations']=locs;p['roles']=roles;profile_save(p);st.success('Saved')

tabs=st.tabs(['🏠 Dashboard','🔎 Job Agent','📄 Application Builder','📋 Tracker','🎤 Interview AI','👤 Profile'])
with tabs[0]:
 c=conn();jobs=pd.read_sql_query('SELECT * FROM jobs ORDER BY match DESC,id DESC LIMIT 100',c);apps=pd.read_sql_query('SELECT * FROM applications ORDER BY id DESC',c)
 a,b,d,e=st.columns(4);a.metric('Jobs',len(jobs));b.metric('Applications',len(apps));d.metric('Interviews',int((apps.status=='Interview').sum()) if not apps.empty else 0);e.metric('Offers',int((apps.status=='Offer').sum()) if not apps.empty else 0)
 st.subheader('⭐ Best matches')
 st.dataframe(jobs[jobs.match>=minimum][['match','title','company','location','url']].head(15),hide_index=True,use_container_width=True)
with tabs[1]:
 st.subheader('🔎 Job Agent'); st.write('Searches public web results and ranks them against your profile.')
 L=[x.strip() for x in locs.split(';') if x.strip()] or ['South Africa'];R=[x.strip() for x in roles.split(',') if x.strip()] or ['Civil Engineer']
 loc=st.selectbox('Location',L);role=st.selectbox('Role',R)
 if st.button('🚀 Scan for jobs',type='primary'):
  with st.spinner('Searching and ranking...'):rows=scan(p,loc,role);save_jobs(rows)
  st.success(f'Found {len(rows)} results.');st.rerun()
 jobs=pd.read_sql_query('SELECT * FROM jobs ORDER BY match DESC,id DESC LIMIT 100',conn())
 for _,j in jobs[jobs.match>=minimum].iterrows():
  with st.container(border=True):st.markdown(f"### {int(j.match)}% — {j.title}");st.write(f"**{j.company or 'Employer not identified'} · {j.location}**");st.write(j.snippet);st.link_button('Open vacancy',j.url)
with tabs[2]:
 st.subheader('📄 Application Builder'); upload=st.file_uploader('Upload master CV',type=['pdf','docx','txt']);cv=extract(upload)
 jobs=pd.read_sql_query('SELECT * FROM jobs ORDER BY match DESC,id DESC LIMIT 100',conn())
 if not jobs.empty:
  row=st.selectbox('Vacancy',jobs.index);j=jobs.loc[row]
  if st.button('✨ Build application pack'):
   prompt=f"PROFILE:\n{json.dumps(p,indent=2)}\nCV:\n{cv[:18000]}\nJOB:\n{j.title}\n{j.company}\n{j.snippet}\n{j.url}\n\nCreate a truthful ATS CV tailoring plan, tailored cover letter, recruiter message, and five likely application answers. Do not invent facts. Label missing items."
   with st.spinner('Writing application pack...'):res=ask(prompt)
   st.markdown(res);st.download_button('Download pack',res,file_name='application_pack.txt')
with tabs[3]:
 st.subheader('📋 Application Tracker')
 with st.form('add'):
  company=st.text_input('Company');title=st.text_input('Position');url=st.text_input('URL');status=st.selectbox('Status',['Prepared','Applied','Interview','Rejected','Offer','Withdrawn']);notes=st.text_area('Notes')
  if st.form_submit_button('Add application'):
   c=conn();c.execute('INSERT INTO applications(created,company,title,location,url,match,status,notes) VALUES(?,?,?,?,?,?,?,?)',(datetime.now().isoformat(timespec='minutes'),company,title,'',url,0,status,notes));c.commit();st.success('Saved')
 apps=pd.read_sql_query('SELECT * FROM applications ORDER BY id DESC',conn());st.dataframe(apps,hide_index=True,use_container_width=True)
 if not apps.empty:st.download_button('Export CSV',apps.to_csv(index=False),file_name='job_applications.csv')
with tabs[4]:
 st.subheader('🎤 Interview AI');role=st.text_input('Role','Graduate Civil Engineer');company=st.text_input('Company','');jd=st.text_area('Job description',height=160)
 if st.button('Generate interview pack'):st.markdown(ask(f"Candidate:\n{json.dumps(p,indent=2)}\nRole:{role}\nCompany:{company}\nJD:{jd}\nCreate 10 likely questions, truthful STAR answer frameworks, 5 technical questions, 5 questions to ask the employer, and a 60-second introduction."))
with tabs[5]:
 st.subheader('👤 Profile')
 with st.form('pf'):
  new={k:st.text_area(k.replace('_',' ').title(),v) for k,v in p.items()}
  if st.form_submit_button('Save profile'):profile_save(new);p=new;st.success('Profile saved')
 st.info('Put OPENAI_API_KEY in Streamlit App Settings → Secrets, never in GitHub.')
st.divider();st.caption('The agent prepares applications but does not invent candidate facts, bypass CAPTCHAs, or falsely claim that an application was submitted.')
