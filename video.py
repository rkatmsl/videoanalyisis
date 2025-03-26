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

load_dotenv()

API_KEY = st.secrets["GOOGLE_API_KEY"]

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

@st.cache_resource
def initialize_agent():
    return Agent(
        name="Video AI Summarizer",
        model=Gemini(id="gemini-2.0-flash-exp"),
        tools=[DuckDuckGo()],
        markdown=True,
    )

# Initialize the agent
multimodal_Agent = initialize_agent()

# Option to either upload a video, provide a YouTube URL, or provide a YouTube Playlist URL
video_option = st.selectbox(
    "Choose how to provide the video(s) for analysis:",
    options=["Upload Video", "Provide YouTube Link", "Provide YouTube Playlist Link"]
)

if video_option == "Upload Video":
    # File uploader for direct video upload
    video_file = st.file_uploader(
        "Upload a video file", type=['mp4', 'mov', 'avi'], help="Upload a video for AI analysis"
    )

    if video_file:
        # Create a temporary file for the uploaded video
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
            temp_video.write(video_file.read())
            video_path = temp_video.name

        st.video(video_path, format="video/mp4", start_time=0)

elif video_option == "Provide YouTube Link":
    # Field to input YouTube link
    youtube_url = st.text_input(
        "Enter YouTube Video URL",
        placeholder="Paste the YouTube video link here.",
        help="Provide the link to a YouTube video for AI analysis."
    )

    if youtube_url:
        with st.spinner("Downloading video from YouTube..."):
            # Specify the project directory to save the video
            download_dir = Path(__file__).parent  # This will set the directory to your current project folder
            video_filename = download_dir / "downloaded_video.mp4"  # Save as 'downloaded_video.mp4'

            # Use yt-dlp to download the video in MP4 format directly to the project directory
            try:
                ydl_opts = {
                    'format': 'mp4',  # Specify MP4 format for download
                    'outtmpl': str(video_filename),  # Save directly to the project directory
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',  # Convert video to MP4 if it's in another format (like .webm)
                    }],
                }

                with ytdl.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(youtube_url, download=True)

                # Check if the file was downloaded with the correct extension
                if not video_filename.exists():
                    st.error("The video was not downloaded in the expected format.")
                else:
                    st.video(str(video_filename), format="video/mp4", start_time=0)
                    video_path = str(video_filename)  # Set the video path for processing

            except Exception as e:
                st.error(f"An error occurred while downloading the video: {e}")

elif video_option == "Provide YouTube Playlist Link":
    # Field to input YouTube playlist link
    playlist_url = st.text_input(
        "Enter YouTube Playlist URL",
        placeholder="Paste the YouTube playlist link here.",
        help="Provide the link to a YouTube playlist for AI analysis."
    )

    if playlist_url:
        with st.spinner("Downloading videos from the playlist..."):
            download_dir = Path(__file__).parent  # Save in the current working directory

            # Use yt-dlp to download all videos from the playlist
            try:
                ydl_opts = {
                    'format': 'mp4',  # Specify MP4 format for download
                    'outtmpl': str(download_dir / '%(title)s.%(ext)s'),  # Save with the video title
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',  # Convert to MP4 format
                    }],
                }

                with ytdl.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(playlist_url, download=True)
                
                # Get the list of downloaded video files
                video_files = list(download_dir.glob('*.mp4'))
                
                if not video_files:
                    st.error("No videos were downloaded from the playlist.")
                else:
                    # Display videos
                    for video_file in video_files:
                        st.video(str(video_file), format="video/mp4", start_time=0)

            except Exception as e:
                st.error(f"An error occurred while downloading the playlist: {e}")

# Text input for user to ask questions about the video(s)
user_query = st.text_area(
    "What insights are you seeking from the video?",
    placeholder="Ask anything about the video content. The AI agent will analyze and gather additional context if needed.",
    help="Provide specific questions or insights you want from the video."
)

if st.button("🔍 Analyze Video(s)", key="analyze_video_button"):
    if not user_query:
        st.warning("Please enter a question or insight to analyze the video.")
    else:
        try:
            with st.spinner("Processing video(s) and gathering insights..."):
                video_paths = []

                # Process single video or playlist
                if video_option == "Upload Video" and video_file:
                    video_paths.append(video_path)
                elif video_option == "Provide YouTube Link" and youtube_url:
                    video_paths.append(video_filename)
                elif video_option == "Provide YouTube Playlist Link" and playlist_url:
                    # Add all playlist videos to the video_paths list
                    video_paths.extend([str(video_file) for video_file in download_dir.glob('*.mp4')])

                # Analyze each video in the playlist
                processed_videos = []
                for video_path in video_paths:
                    processed_video = upload_file(video_path)
                    while processed_video.state.name == "PROCESSING":
                        time.sleep(1)
                        processed_video = get_file(processed_video.name)
                    processed_videos.append(processed_video)

                # Aggregate insights from all videos
                analysis_prompt = (
                    f"""
                    Analyze the uploaded videos and respond to the following query using video insights from all videos:
                    {user_query}

                    Provide a detailed, user-friendly, and actionable response based on the content of the videos.
                    """
                )

                # AI agent processing
                response = multimodal_Agent.run(analysis_prompt, videos=processed_videos)

            # Display the result
            st.subheader("Analysis Result")
            st.markdown(response.content)

        except Exception as error:
            st.error(f"An error occurred during analysis: {error}")

# Customize text area height
st.markdown(
    """
    <style>
    .stTextArea textarea {
        height: 100px;
    }
    </style>
    """,
    unsafe_allow_html=True
)
