import tempfile
import time
import yt_dlp as ytdl
import os
from pathlib import Path
import streamlit as st
from phi.agent import Agent
from phi.model.google import Gemini
from phi.tools.duckduckgo import DuckDuckGo
from google.generativeai import upload_file, get_file
import google.generativeai as genai
from dotenv import load_dotenv
import requests

load_dotenv()

API_KEY = st.secrets["GOOGLE_API_KEY"]

# API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    st.error("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")
    st.stop()

if API_KEY:
    genai.configure(api_key=API_KEY)

# Page configuration
st.set_page_config(
    page_title="Multimodal AI Agent - Video Summarizer",
    page_icon="🎥",
    layout="wide"
)

st.title("Phidata Video AI Summarizer Agent 🎥🎤🖬")
st.header("Powered by Gemini 2.0 Flash Exp")

# Initialize session state
if "video_paths" not in st.session_state:
    st.session_state.video_paths = []
if "current_input" not in st.session_state:
    st.session_state.current_input = None
if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None

@st.cache_resource
def initialize_agent():
    return Agent(
        name="Video AI Summarizer",
        model=Gemini(id="gemini-2.5-flash"),
        tools=[DuckDuckGo()],
        markdown=True,
    )

multimodal_Agent = initialize_agent()

# Choose input method
video_option = st.selectbox(
    "Choose how to provide the video(s) for analysis:",
    options=[
        "Upload Video",
        "Provide YouTube Link",
        "Provide YouTube Playlist Link",
        "Provide direct video URL (.mp4)"
    ]
)

# ────────────────────────────────────────────────
# INPUT HANDLING (only download/process when needed)
# ────────────────────────────────────────────────

if video_option == "Upload Video":
    video_file = st.file_uploader(
        "Upload a video file",
        type=['mp4', 'mov', 'avi', 'mkv'],
        key="video_uploader"
    )
    if video_file:
        # Only re-process if it's a new file
        if (st.session_state.last_uploaded_name != video_file.name or
                not st.session_state.video_paths):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
                temp_video.write(video_file.read())
                st.session_state.video_paths = [temp_video.name]
                st.session_state.last_uploaded_name = video_file.name
            st.success("Video uploaded successfully!")
        if st.session_state.video_paths:
            st.video(st.session_state.video_paths[0], format="video/mp4")

elif video_option == "Provide YouTube Link":
    youtube_url = st.text_input(
        "Enter YouTube Video URL",
        placeholder="https://youtu.be/...",
        key="youtube_single"
    )
    if youtube_url:
        # Download only if URL changed or no valid file exists
        if (st.session_state.current_input != youtube_url or
                not st.session_state.video_paths or
                not Path(st.session_state.video_paths[0]).exists()):

            with st.spinner("Downloading YouTube video..."):
                try:
                    temp_dir = tempfile.mkdtemp()
                    video_filename = Path(temp_dir) / "youtube_video.mp4"

                    ydl_opts = {
                        'format': 'mp4',
                        'outtmpl': str(video_filename),
                        'postprocessors': [{
                            'key': 'FFmpegVideoConvertor',
                            'preferedformat': 'mp4',
                        }],
                    }
                    with ytdl.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(youtube_url, download=True)

                    if video_filename.exists() and video_filename.stat().st_size > 10000:
                        st.session_state.video_paths = [str(video_filename)]
                        st.session_state.current_input = youtube_url
                        st.success("Video downloaded!")
                    else:
                        st.error("Downloaded file is invalid or empty.")
                        st.session_state.video_paths = []
                except Exception as e:
                    st.error(f"Download failed: {e}")
                    st.session_state.video_paths = []

        # Show video
        if st.session_state.video_paths and Path(st.session_state.video_paths[0]).exists():
            st.video(st.session_state.video_paths[0], format="video/mp4")

elif video_option == "Provide YouTube Playlist Link":
    playlist_url = st.text_input(
        "Enter YouTube Playlist URL",
        placeholder="https://www.youtube.com/playlist?list=...",
        key="youtube_playlist"
    )
    if playlist_url:
        if (st.session_state.current_input != playlist_url or
                not st.session_state.video_paths):

            with st.spinner("Downloading playlist videos..."):
                try:
                    temp_dir = tempfile.mkdtemp()
                    ydl_opts = {
                        'format': 'mp4',
                        'outtmpl': str(Path(temp_dir) / '%(title)s.%(ext)s'),
                        'postprocessors': [{
                            'key': 'FFmpegVideoConvertor',
                            'preferedformat': 'mp4',
                        }],
                    }
                    with ytdl.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(playlist_url, download=True)

                    files = list(Path(temp_dir).glob('*.mp4'))
                    if files:
                        st.session_state.video_paths = [str(f) for f in files]
                        st.session_state.current_input = playlist_url
                        st.success(f"Downloaded {len(files)} video(s)")
                    else:
                        st.error("No .mp4 files were downloaded.")
                        st.session_state.video_paths = []
                except Exception as e:
                    st.error(f"Playlist download failed: {e}")
                    st.session_state.video_paths = []

        # Show all videos
        for path in st.session_state.video_paths:
            if Path(path).exists():
                st.video(path, format="video/mp4")

elif video_option == "Provide direct video URL (.mp4)":
    direct_url = st.text_input(
        "Enter direct video URL",
        placeholder="https://example.com/video.mp4",
        key="direct_url"
    )
    if direct_url:
        if (st.session_state.current_input != direct_url or
                not st.session_state.video_paths or
                not Path(st.session_state.video_paths[0]).exists()):

            with st.spinner("Downloading video from URL..."):
                try:
                    temp_dir = tempfile.mkdtemp()
                    video_filename = Path(temp_dir) / "direct_video.mp4"

                    response = requests.get(direct_url, stream=True, timeout=45)
                    response.raise_for_status()

                    with open(video_filename, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    if video_filename.exists() and video_filename.stat().st_size > 10000:
                        st.session_state.video_paths = [str(video_filename)]
                        st.session_state.current_input = direct_url
                        st.success("Video downloaded!")
                    else:
                        st.error("Downloaded file is invalid or empty.")
                        st.session_state.video_paths = []
                except Exception as e:
                    st.error(f"Download failed: {e}")
                    st.session_state.video_paths = []

        if st.session_state.video_paths and Path(st.session_state.video_paths[0]).exists():
            st.video(st.session_state.video_paths[0], format="video/mp4")

# ────────────────────────────────────────────────
# ANALYSIS SECTION
# ────────────────────────────────────────────────

user_query = st.text_area(
    "What insights are you seeking from the video?",
    placeholder="Ask anything about the video content...",
    height=120
)

if st.button("🔍 Analyze Video(s)", key="analyze_button"):
    if not user_query.strip():
        st.warning("Please enter a question or insight to analyze.")
    elif not st.session_state.video_paths:
        st.warning("No video(s) loaded yet. Please provide a video first.")
    else:
        try:
            with st.spinner("Processing video(s) and generating insights..."):
                processed_videos = []
                for path in st.session_state.video_paths:
                    if not Path(path).exists():
                        st.warning(f"Video file no longer exists: {path}")
                        continue
                    uploaded = upload_file(path)
                    while uploaded.state.name == "PROCESSING":
                        time.sleep(1)
                        uploaded = get_file(uploaded.name)
                    processed_videos.append(uploaded)

                if not processed_videos:
                    st.error("No valid videos could be uploaded for analysis.")
                else:
                    analysis_prompt = f"""
Analyze the uploaded videos and respond to the following query using insights from all videos:
{user_query}

Provide a detailed, user-friendly, and actionable response based on the content of the videos.
"""

                    response = multimodal_Agent.run(analysis_prompt, videos=processed_videos)

                    st.subheader("Analysis Result")
                    st.markdown(response.content)

        except Exception as error:
            st.error(f"An error occurred during analysis: {error}")

# Optional: Reset button
if st.button("Clear current video(s) and start over"):
    st.session_state.video_paths = []
    st.session_state.current_input = None
    st.session_state.last_uploaded_name = None
    st.rerun()

# Custom styling
st.markdown(
    """
    <style>
    .stTextArea textarea {
        height: 120px;
    }
    </style>
    """,
    unsafe_allow_html=True
)