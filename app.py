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

# Custom CSS for "Hacker/Pro" Dashboard Look
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    
    /* Custom Metric Card */
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
    
    /* AI Output Box */
    .ai-box { 
        border: 1px solid #333; 
        padding: 25px; 
        border-radius: 10px; 
        background-color: #262730; 
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR & API KEY HANDLING
# ==========================================
with st.sidebar:
    st.title("⚡ Command Center")
    st.markdown("v3.0 Ultimate Edition")
    
    # --- YouTube Key ---
    if "YOUTUBE_API_KEY" in st.secrets:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("✅ YT Key Active")
    else:
        api_key = st.text_input("🔑 YouTube API Key", type="password")
        if not api_key:
            st.warning("⚠️ API Key Required")

    # --- Gemini AI Key ---
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
    
    # --- Settings ---
    st.subheader("⚙️ Parameters")
    country_code = st.selectbox("Target Region", ["US", "IN", "GB", "CA", "AU"], index=0)
    rpm = st.slider("Est. RPM ($)", 0.5, 20.0, 3.0, help="Estimated earnings per 1,000 views")

# ==========================================
# 3. CORE LOGIC FUNCTIONS
# ==========================================

@st.cache_data(show_spinner=False) # Cache results to save API quota
def get_market_data(api_key, query, max_results=50):
    """Fetches video data, channel stats, and calculates metrics."""
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    # 1. Search Query
    search_req = youtube.search().list(
        part="snippet", q=query, type="video", 
        regionCode=country_code, maxResults=max_results, order="viewCount"
    )
    search_res = search_req.execute()
    
    video_ids = [item['id']['videoId'] for item in search_res.get('items', [])]
    
    # 2. Get Video Details
    stats_req = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids))
    stats_res = stats_req.execute()
    
    data = []
    all_tags = []
    
    for item in stats_res.get('items', []):
        stats = item['statistics']
        snippet = item['snippet']
        
        # Stats Extraction
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        title = snippet['title']
        video_id = item['id']
        tags = snippet.get('tags', [])
        if tags: all_tags.extend(tags)
        
        # Calculated Metrics
        engagement = ((likes + comments) / views * 100) if views > 0 else 0
        revenue = (views / 1000) * rpm
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Custom Virality Algorithm
        # High weight on Comments/Likes vs Views
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
        # Normalize Virality Score (0-100 scale)
        df['Virality Score'] = (df['Virality Raw'] / df['Virality Raw'].max()) * 100
        df['Virality Score'] = df['Virality Score'].round(0)
    
    return df, all_tags

def ai_content_engine(video_id, title, tags):
    """
    Uses Gemini to analyze Transcript. Falls back to Title/Tags if no transcript.
    """
    context_source = "Full Transcript"
    transcript_text = ""
    
    # 1. Try to get Transcript
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])[:5000] # Limit chars
    except:
        context_source = "Title & Metadata (No Captions Found)"
        transcript_text = f"Video Title: {title}. Video Tags: {tags}"

    # 2. Send to Gemini
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    Act as a Viral Content Strategist (MrBeast Style).
    
    SOURCE MATERIAL ({context_source}):
    "{transcript_text}..."
    
    TASK:
    Analyze this content and generate a plan to RECREATE and OUTPERFORM it.
    
    OUTPUT FORMAT (Markdown):
    ### 🧠 1. The Psychology
    * **Why it went viral:** (Analyze the hook/pacing)
    * **The Gap:** (What was missing? How can we improve?)
    
    ### 📝 2. The Golden Script Outline
    * **Hook (0:00-0:30):** [Visual + Verbal Hook]
    * **Body:** [3 Key value points]
    * **Retention Hack:** [Mid-video pattern interrupt]
    * **CTA:** [Specific Call to Action]
    
    ### 🎨 3. Thumbnail Studio
    * **Idea 1:** [Visual description]
    * **Idea 2:** [Visual description]
    
    ### ⚡ 4. Viral Hooks (Titles)
    * Give 3 clickbait-style alternative titles.
    """
    
    response = model.generate_content(prompt)
    return response.text, context_source

# ==========================================
# 4. MAIN DASHBOARD UI
# ==========================================
st.title("⚡ YouTube Command Center")
st.caption("Market Analysis • Revenue Estimation • AI Content Cloning")

# --- Search Area ---
col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("Enter Niche / Topic / Channel", placeholder="e.g. 'Personal Finance', 'Coding Tutorials', 'Gaming'")
with col2:
    st.write("") 
    st.write("") 
    search_btn = st.button("🚀 Scan Market", use_container_width=True, type="primary")

# --- Execution ---
if search_btn and api_key:
    with st.spinner('🛰️ Scanning YouTube Database...'):
        try:
            df, all_tags = get_market_data(api_key, query)
            
            # --- High-Level Metrics ---
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Niche Views", f"{df['Views'].sum():,}")
            m2.metric("Est. Market Value", f"${df['Earnings'].sum():,.0f}")
            m3.metric("Avg Engagement", f"{df['Engagement'].mean()}%")
            m4.metric("Top Virality Score", f"{df['Virality Score'].max()}/100")
            
            st.divider()

            # --- TABS ---
            tabs = st.tabs(["📂 Video Vault", "🎬 AI Deep Dive", "🕵️ Tag Spy", "📈 Visuals"])
            
            # TAB 1: The Database
            with tabs[0]:
                st.markdown("### 📂 Market Database")
                st.dataframe(
                    df[['Thumbnail', 'Title', 'Views', 'Virality Score', 'Earnings', 'Link']],
                    column_config={
                        "Thumbnail": st.column_config.ImageColumn("Preview"),
                        "Virality Score": st.column_config.ProgressColumn("Viral Score", min_value=0, max_value=100, format="%.0f"),
                        "Earnings": st.column_config.NumberColumn("Est. Revenue", format="$%d"),
                        "Link": st.column_config.LinkColumn("Watch") # Clickable!
                    },
                    use_container_width=True,
                    height=600
                )

            # TAB 2: The Deep Dive (Player + AI)
            with tabs[1]:
                st.subheader("🎬 Content Lab & AI Cloner")
                
                # Dropdown Selection
                video_list = df['Title'].tolist()
                selected_video = st.selectbox("Select a video to analyze:", video_list)
                
                # Get Row Data
                row = df[df['Title'] == selected_video].iloc[0]
                
                d1, d2 = st.columns([1.5, 1])
                
                with d1:
                    # Video Player
                    st.video(row['Link'])
                    
                    # AI Action
                    st.markdown("---")
                    st.markdown("### 🤖 AI Strategy Generator")
                    if ai_enabled:
                        if st.button(f"✨ Clone & Improve: '{row['Title'][:20]}...'"):
                            with st.spinner("🧠 AI is analyzing transcript & generating strategy..."):
                                analysis, source = ai_content_engine(row['Video ID'], row['Title'], row['Tags'])
                                st.success(f"Analysis Complete! (Based on: {source})")
                                st.markdown(f'<div class="ai-box">{analysis}</div>', unsafe_allow_html=True)
                    else:
                        st.warning("🔒 Add Gemini API Key in sidebar to unlock AI features.")

                with d2:
                    # Custom Performance Card
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
                    
                    st.caption(f"**Published:** {row['Published']}")
                    st.caption(f"**Video ID:** {row['Video ID']}")
                    st.link_button("➡️ Open on YouTube", row['Link'], use_container_width=True)

            # TAB 3: Tag Spy
            with tabs[2]:
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown("### 📋 Copy Top Tags")
                    tag_counts = Counter(all_tags).most_common(30)
                    tags_text = ", ".join([t[0] for t in tag_counts])
                    st.text_area("Paste into YouTube Studio:", tags_text, height=300)
                with c2:
                    st.markdown("### ☁️ Keyword Cloud")
                    if all_tags:
                        wc = WordCloud(width=800, height=400, background_color='#0E1117', colormap='Reds').generate_from_frequencies(dict(tag_counts))
                        fig, ax = plt.subplots()
                        plt.imshow(wc, interpolation='bilinear')
                        plt.axis("off")
                        fig.patch.set_facecolor('#0E1117')
                        st.pyplot(fig)
                    else:
                        st.warning("No tags found for this search.")

            # TAB 4: Visuals
            with tabs[3]:
                st.markdown("### 📈 Market Trends")
                c_chart1, c_chart2 = st.columns(2)
                
                with c_chart1:
                    st.caption("Views vs. Engagement (Hotter = More Viral)")
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

        except Exception as e:
            st.error(f"An error occurred: {e}")

elif search_btn and not api_key:
    st.error("⚠️ Please enter your YouTube API Key in the sidebar.")
