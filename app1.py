import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from googleapiclient.discovery import build
from textblob import TextBlob
from wordcloud import WordCloud
from collections import Counter
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

# ==========================================
# 1. PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="YouTube Command Center Ultra", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    .metric-card { 
        background-color: #1E1E1E; 
        padding: 20px; 
        border-radius: 15px; 
        border-left: 5px solid #FF0000;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.5);
        margin-bottom: 20px;
    }
    .big-stat { font-size: 28px; font-weight: bold; color: #FFFFFF; }
    .small-label { font-size: 14px; color: #AAAAAA; letter-spacing: 1px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INITIALIZE SESSION STATE
# ==========================================
if 'search_done' not in st.session_state:
    st.session_state.search_done = False
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'all_tags' not in st.session_state:
    st.session_state.all_tags = []

# ==========================================
# 3. SIDEBAR & API KEY HANDLING
# ==========================================
with st.sidebar:
    st.title("⚡ Command Center")
    st.markdown("v3.2 Ultra Edition")
    
    if "YOUTUBE_API_KEY" in st.secrets:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("✅ YT Key Active")
    else:
        api_key = st.text_input("🔑 YouTube API Key", type="password")

    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        ai_enabled = True
        st.success("✅ AI Brain Active")
    else:
        gemini_key = st.text_input("✨ Gemini API Key (Optional)", type="password")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            ai_enabled = True
        else:
            ai_enabled = False
            st.info("Add Gemini Key to unlock Script Writer")
    
    st.divider()
    country_code = st.selectbox("Target Region", ["US", "IN", "GB", "CA", "AU"], index=0)
    rpm = st.slider("Est. RPM ($)", 0.5, 20.0, 3.0)

# ==========================================
# 4. CORE LOGIC FUNCTIONS
# ==========================================
def get_market_data(api_key, query, max_results=50):
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    search_req = youtube.search().list(
        part="snippet", q=query, type="video", 
        regionCode=country_code, maxResults=max_results, order="viewCount"
    )
    search_res = search_req.execute()
    
    video_ids = [item['id']['videoId'] for item in search_res.get('items', [])]
    stats_req = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids))
    stats_res = stats_req.execute()
    
    data = []
    all_tags = []
    
    for item in stats_res.get('items', []):
        stats = item['statistics']
        snippet = item['snippet']
        
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        title = snippet['title']
        video_id = item['id']
        tags = snippet.get('tags', [])
        if tags: all_tags.extend(tags)
        
        engagement = ((likes + comments) / views * 100) if views > 0 else 0
        revenue = (views / 1000) * rpm
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        raw_score = (views * 0.5) + (likes * 50) + (comments * 100)
        
        data.append({
            'Video ID': video_id,
            'Thumbnail': snippet['thumbnails']['high']['url'],
            'Title': title,
            'Views': views,
            'Likes': likes,
            'Comments': comments,
            'Engagement': round(engagement, 2),
            'Earnings': round(revenue, 2),
            'Virality Raw': raw_score,
            'Link': video_url,
            'Published': snippet['publishedAt'][:10],
            'Tags': tags
        })
    
    df = pd.DataFrame(data)
    if not df.empty:
        df['Virality Score'] = (df['Virality Raw'] / df['Virality Raw'].max()) * 100
        df['Virality Score'] = df['Virality Score'].round(0)
    
    return df, all_tags

def ai_content_engine(video_id, title, tags):
    context_source = "Full Transcript"
    transcript_text = ""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])[:5000]
    except:
        context_source = "Title & Metadata (No Captions Found)"
        transcript_text = f"Video Title: {title}. Video Tags: {tags}"

    model = genai.GenerativeModel('gemini-pro')
    prompt = f"""
    Act as a Viral Content Strategist.
    SOURCE MATERIAL ({context_source}): "{transcript_text}..."
    
    TASK: Analyze this content and generate a plan to RECREATE and OUTPERFORM it.
    
    OUTPUT FORMAT (Markdown):
    ### 🧠 1. The Psychology
    * **Why it went viral:** (Hook/Pacing)
    * **The Gap:** (What can be improved?)
    
    ### 📝 2. The Golden Script Outline
    * **Hook (0:00-0:30):** [Visual + Verbal Hook]
    * **Body:** [Key value points]
    * **CTA:** [Call to Action]
    
    ### 🎨 3. Thumbnail Studio
    * **Idea 1:** [Visual description]
    * **Idea 2:** [Visual description]
    
    ### ⚡ 4. Viral Hooks
    * Give 3 clickbait-style alternative titles.
    """
    response = model.generate_content(prompt)
    return response.text, context_source

# ==========================================
# 5. POPUP DIALOG FUNCTION (New Feature!)
# ==========================================
@st.dialog("🤖 AI Content Strategist", width="large")
def show_ai_modal(video_id, title, tags):
    st.caption(f"Analyzing Strategy for: {title}")
    
    # 1. Run AI
    with st.spinner("🧠 Reading transcript, analyzing psychology, and writing script..."):
        analysis, source = ai_content_engine(video_id, title, tags)
    
    # 2. Show Results
    st.success(f"Analysis Complete! (Source: {source})")
    st.markdown(analysis)
    st.caption("Tip: Copy this strategy to your notes.")

# ==========================================
# 6. MAIN DASHBOARD UI
# ==========================================
st.title("⚡ YouTube Command Center")

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("Enter Niche / Topic", placeholder="e.g. 'MrBeast', 'Python Roadmap'")
with col2:
    st.write("") 
    st.write("") 
    if st.button("🚀 Scan Market", use_container_width=True, type="primary"):
        if not api_key:
            st.error("⚠️ Please enter API Key first")
        else:
            with st.spinner('Scanning YouTube Database...'):
                try:
                    st.session_state.df, st.session_state.all_tags = get_market_data(api_key, query)
                    st.session_state.search_done = True
                except Exception as e:
                    st.error(f"Error: {e}")

if st.session_state.search_done:
    df = st.session_state.df
    all_tags = st.session_state.all_tags
    
    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Niche Views", f"{df['Views'].sum():,}")
    m2.metric("Est. Market Value", f"${df['Earnings'].sum():,.0f}")
    m3.metric("Avg Engagement", f"{df['Engagement'].mean()}%")
    m4.metric("Top Virality Score", f"{df['Virality Score'].max()}/100")
    
    st.divider()

    # Tabs
    tabs = st.tabs(["📂 Video Vault", "🎬 Deep Dive", "🕵️ Tag Spy", "📈 Visuals"])
    
    # TAB 1
    with tabs[0]:
        st.dataframe(
            df[['Thumbnail', 'Title', 'Views', 'Virality Score', 'Earnings', 'Link']],
            column_config={
                "Thumbnail": st.column_config.ImageColumn("Preview"),
                "Virality Score": st.column_config.ProgressColumn("Viral Score", min_value=0, max_value=100, format="%.0f"),
                "Earnings": st.column_config.NumberColumn("Est. Revenue", format="$%d"),
                "Link": st.column_config.LinkColumn("Watch")
            },
            use_container_width=True,
            height=600
        )

    # TAB 2: The New Popup Trigger
    with tabs[1]:
        st.subheader("🎬 Content Lab")
        video_list = df['Title'].tolist()
        selected_video = st.selectbox("Select a video to analyze:", video_list)
        
        row = df[df['Title'] == selected_video].iloc[0]
        
        d1, d2 = st.columns([1.5, 1])
        
        with d1:
            st.video(row['Link'])
            st.markdown("---")
            
            # THE POPUP BUTTON
            if ai_enabled:
                if st.button(f"✨ Clone & Improve: '{row['Title'][:20]}...'"):
                    show_ai_modal(row['Video ID'], row['Title'], row['Tags'])
            else:
                st.warning("🔒 Add Gemini API Key to unlock AI features.")

        with d2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="small-label">ESTIMATED EARNINGS</div>
                <div class="big-stat">${row['Earnings']:,.2f}</div>
                <br>
                <div class="small-label">TOTAL VIEWS</div>
                <div class="big-stat">{row['Views']:,}</div>
                <br>
                <div class="small-label">VIRALITY SCORE</div>
                <div class="big-stat">{row['Virality Score']}/100</div>
                <br>
                <div class="small-label">ENGAGEMENT RATE</div>
                <div class="big-stat">{row['Engagement']}%</div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("➡️ Open on YouTube", row['Link'], use_container_width=True)

    # TAB 3
    with tabs[2]:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("### 📋 Copy Top Tags")
            tag_counts = Counter(all_tags).most_common(30)
            tags_text = ", ".join([t[0] for t in tag_counts])
            st.text_area("Paste into YouTube Studio:", tags_text, height=300)
        with c2:
            if all_tags:
                wc = WordCloud(width=800, height=400, background_color='#0E1117', colormap='Reds').generate_from_frequencies(dict(tag_counts))
                fig, ax = plt.subplots()
                plt.imshow(wc, interpolation='bilinear')
                plt.axis("off")
                fig.patch.set_facecolor('#0E1117')
                st.pyplot(fig)

    # TAB 4
    with tabs[3]:
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            fig, ax = plt.subplots()
            sns.scatterplot(data=df, x='Views', y='Engagement', hue='Virality Score', palette='rocket_r', size='Earnings', sizes=(20, 200), ax=ax)
            fig.patch.set_facecolor('#0E1117')
            ax.set_facecolor('#0E1117')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.tick_params(colors='white')
            st.pyplot(fig)
        with c_chart2:
            fig2, ax2 = plt.subplots()
            sns.histplot(df['Virality Score'], kde=True, color='red', ax=ax2)
            fig2.patch.set_facecolor('#0E1117')
            ax2.set_facecolor('#0E1117')
            ax2.xaxis.label.set_color('white')
            ax2.yaxis.label.set_color('white')
            ax2.tick_params(colors='white')
            st.pyplot(fig2)
