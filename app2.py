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
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="YouTube Command Center Pro", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. PROFESSIONAL UI STYLING (CSS)
# ==========================================
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #0E1117;
    }
    
    /* Glassmorphism Metric Cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border: 1px solid rgba(255, 0, 0, 0.5);
    }
    
    /* Typography */
    .big-stat { 
        font-size: 32px; 
        font-weight: 700; 
        background: -webkit-linear-gradient(45deg, #FF0000, #FF8E53);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .small-label { 
        font-size: 12px; 
        text-transform: uppercase; 
        letter-spacing: 1.5px; 
        color: #888; 
        margin-bottom: 5px;
    }
    
    /* AI Output Box */
    .ai-box {
        background-color: #151515;
        border-left: 4px solid #FF4B4B;
        padding: 20px;
        border-radius: 5px;
        margin-top: 15px;
    }
    
    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. SESSION STATE MANAGEMENT
# ==========================================
if 'search_done' not in st.session_state:
    st.session_state.search_done = False
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'all_tags' not in st.session_state:
    st.session_state.all_tags = []

# ==========================================
# 4. SIDEBAR & API KEYS
# ==========================================
with st.sidebar:
    st.title("⚡ Command Center")
    st.caption("v4.0 Enterprise Edition")
    st.divider()
    
    # Keys
    if "YOUTUBE_API_KEY" in st.secrets:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("✅ YouTube Connected")
    else:
        api_key = st.text_input("YouTube API Key", type="password")

    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        ai_enabled = True
        st.success("✅ Gemini AI Connected")
    else:
        gemini_key = st.text_input("Gemini API Key", type="password")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            ai_enabled = True
        else:
            ai_enabled = False
            st.warning("AI Features Locked")
    
    st.divider()
    
    # Parameters
    with st.expander("⚙️ Search Parameters", expanded=True):
        country_code = st.selectbox("Target Region", ["US", "IN", "GB", "CA", "AU"], index=0)
        rpm = st.slider("Est. RPM ($)", 0.5, 20.0, 3.0)
        max_res = st.number_input("Max Results", 10, 100, 50)

# ==========================================
# 5. CORE LOGIC
# ==========================================
@st.cache_data(show_spinner=False)
def get_market_data(api_key, query, max_results):
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
    """Uses Gemini 1.5 Flash for speed and reliability."""
    context_source = "Full Transcript"
    transcript_text = ""
    
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])[:8000]
    except:
        context_source = "Title & Metadata (No Captions Found)"
        transcript_text = f"Video Title: {title}. Video Tags: {tags}"

    try:
        # UPDATED MODEL TO 1.5 FLASH
        model = genai.GenerativeModel('gemini-1.5-flash')
        
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
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}", "Error"

# ==========================================
# 6. DIALOG / MODAL (New Feature)
# ==========================================
@st.dialog("🤖 AI Strategy Lab", width="large")
def show_ai_modal(video_id, title, tags):
    st.markdown(f"### Strategy for: _{title}_")
    
    with st.spinner("🧠 AI is watching video & writing strategy..."):
        analysis, source = ai_content_engine(video_id, title, tags)
    
    if source == "Error":
        st.error(analysis)
    else:
        st.success(f"Analysis Generated from {source}")
        st.markdown(analysis)
        st.caption("Tip: Copy this text to your Notion/Notes app.")

# ==========================================
# 7. MAIN DASHBOARD
# ==========================================
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ YouTube Command Center")
with col2:
    # Spacer
    st.write("")

# Search Bar
with st.container():
    c1, c2 = st.columns([4, 1])
    with c1:
        query = st.text_input("Search Market", placeholder="e.g. 'MrBeast', 'AI News', 'Meditation'", label_visibility="collapsed")
    with c2:
        if st.button("🚀 Scan Market", type="primary"):
            if not api_key:
                st.toast("⚠️ Please enter API Key first", icon="🚫")
            else:
                with st.spinner('🛰️ Scanning YouTube Database...'):
                    try:
                        st.session_state.df, st.session_state.all_tags = get_market_data(api_key, query, max_res)
                        st.session_state.search_done = True
                    except Exception as e:
                        st.error(f"Error: {e}")

# Results Area
if st.session_state.search_done:
    df = st.session_state.df
    all_tags = st.session_state.all_tags
    
    st.write("") # Spacer
    
    # --- Metric Cards ---
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.markdown(f"""<div class="metric-card">
        <div class="small-label">Total Views</div>
        <div class="big-stat">{df['Views'].sum():,}</div>
        </div>""", unsafe_allow_html=True)
        
    with m2:
        st.markdown(f"""<div class="metric-card">
        <div class="small-label">Market Value</div>
        <div class="big-stat">${df['Earnings'].sum():,.0f}</div>
        </div>""", unsafe_allow_html=True)

    with m3:
        st.markdown(f"""<div class="metric-card">
        <div class="small-label">Avg Engagement</div>
        <div class="big-stat">{df['Engagement'].mean()}%</div>
        </div>""", unsafe_allow_html=True)

    with m4:
        st.markdown(f"""<div class="metric-card">
        <div class="small-label">Top Virality</div>
        <div class="big-stat">{df['Virality Score'].max()}/100</div>
        </div>""", unsafe_allow_html=True)
    
    # --- Tabs ---
    st.write("")
    tabs = st.tabs(["📂 Video Vault", "🎬 Content Lab (Deep Dive)", "🕵️ Tag Spy", "📈 Visuals"])
    
    # TAB 1: Vault
    with tabs[0]:
        st.dataframe(
            df[['Thumbnail', 'Title', 'Views', 'Virality Score', 'Earnings', 'Link']],
            column_config={
                "Thumbnail": st.column_config.ImageColumn("Preview"),
                "Virality Score": st.column_config.ProgressColumn("Viral Score", min_value=0, max_value=100, format="%.0f"),
                "Earnings": st.column_config.NumberColumn("Est. Revenue", format="$%d"),
                "Link": st.column_config.LinkColumn("Link")
            },
            use_container_width=True,
            height=600
        )

    # TAB 2: Deep Dive
    with tabs[1]:
        c_list, c_detail = st.columns([1, 2])
        
        with c_list:
            st.markdown("### Select Video")
            video_list = df['Title'].tolist()
            selected_video = st.radio("List", video_list, label_visibility="collapsed")
            
        with c_detail:
            row = df[df['Title'] == selected_video].iloc[0]
            
            # Video Embed
            st.video(row['Link'])
            
            # AI Trigger Button
            c_btn, c_stat = st.columns([1, 1])
            with c_btn:
                st.write("")
                if ai_enabled:
                    if st.button(f"✨ Generate AI Strategy", use_container_width=True, type="primary"):
                        show_ai_modal(row['Video ID'], row['Title'], row['Tags'])
                else:
                    st.warning("🔒 Add Gemini Key")
            
            with c_stat:
                st.info(f"**Est. Earnings:** ${row['Earnings']:,.2f}")

            # Stats Grid
            s1, s2, s3 = st.columns(3)
            s1.metric("Views", f"{row['Views']:,}")
            s2.metric("Likes", f"{row['Likes']:,}")
            s3.metric("Virality", f"{row['Virality Score']}/100")

    # TAB 3: Tag Spy
    with tabs[2]:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("### 📋 Copy Top Tags")
            tag_counts = Counter(all_tags).most_common(30)
            tags_text = ", ".join([t[0] for t in tag_counts])
            st.text_area("Tags", tags_text, height=300, label_visibility="collapsed")
        with c2:
            if all_tags:
                wc = WordCloud(width=800, height=400, background_color='#0E1117', colormap='Reds').generate_from_frequencies(dict(tag_counts))
                fig, ax = plt.subplots()
                plt.imshow(wc, interpolation='bilinear')
                plt.axis("off")
                fig.patch.set_facecolor('#0E1117')
                st.pyplot(fig)

    # TAB 4: Visuals
    with tabs[3]:
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.caption("Views vs. Engagement")
            fig, ax = plt.subplots()
            sns.scatterplot(data=df, x='Views', y='Engagement', hue='Virality Score', palette='rocket_r', size='Earnings', sizes=(20, 200), ax=ax)
            fig.patch.set_facecolor('#0E1117')
            ax.set_facecolor('#0E1117')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.tick_params(colors='white')
            st.pyplot(fig)
        with c_chart2:
            st.caption("Virality Score Distribution")
            fig2, ax2 = plt.subplots()
            sns.histplot(df['Virality Score'], kde=True, color='red', ax=ax2)
            fig2.patch.set_facecolor('#0E1117')
            ax2.set_facecolor('#0E1117')
            ax2.xaxis.label.set_color('white')
            ax2.yaxis.label.set_color('white')
            ax2.tick_params(colors='white')
            st.pyplot(fig2)
