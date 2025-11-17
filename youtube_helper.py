# youtube_helper.py
import yt_dlp
import os
from pathlib import Path
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

TEMP_DIR = Path('./temp_videos')
TEMP_DIR.mkdir(exist_ok=True)

class YouTubeAudioDownloader:
    """
    Download audio from YouTube videos for vehicle sound comparison
    """
    
    def __init__(self, max_videos=15, max_duration=180):
        """
        Args:
            max_videos: Maximum number of videos to download (increased to 15)
            max_duration: Maximum video duration in seconds (default: 3 minutes)
        """
        self.max_videos = max_videos
        self.max_duration = max_duration
        
        # yt-dlp options for audio-only download
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': str(TEMP_DIR / '%(id)s.%(ext)s'),
            'cookiefile': '/app/youtube_cookies.txt',
            'quiet': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
        }
    
    def search_videos(self, query, max_results=10):
        """
        Search YouTube for relevant videos using yt-dlp
        
        Args:
            query: Search query string
            max_results: Maximum number of search results
            
        Returns:
            List of video info dicts
        """
        logger.info(f"Searching YouTube for: '{query}'")
        
        try:
            # Use yt-dlp to search YouTube
            ydl_search_opts = {
                'quiet': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'no_warnings': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            search_url = f"ytsearch{max_results}:{query}"
            
            with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
                search_results = ydl.extract_info(search_url, download=False)
                
                if not search_results or 'entries' not in search_results:
                    logger.warning(f"No results found for query: {query}")
                    return []
                
                videos = []
                for entry in search_results['entries']:
                    if not entry:
                        continue
                    
                    # Get duration in seconds
                    duration_seconds = entry.get('duration', 0)
                    
                    # Skip videos longer than max_duration
                    if duration_seconds > self.max_duration:
                        logger.info(f"Skipping long video: {entry.get('title')} ({duration_seconds}s)")
                        continue
                    
                    video_info = {
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'url': f"https://youtube.com/watch?v={entry.get('id')}",
                        'channel': entry.get('channel', entry.get('uploader', 'Unknown')),
                        'duration': duration_seconds,
                        'views': entry.get('view_count', 0)
                    }
                    
                    videos.append(video_info)
                    
                    if len(videos) >= self.max_videos:
                        break
                
                logger.info(f"Found {len(videos)} suitable videos")
                return videos
        
        except Exception as e:
            logger.error(f"YouTube search error: {str(e)}")
            return []
    
    def download_audio(self, video_url, video_id):
        """
        Download audio from a single YouTube video
        
        Args:
            video_url: YouTube video URL
            video_id: Unique video identifier
            
        Returns:
            Path to downloaded audio file or None
        """
        try:
            logger.info(f"Downloading audio from: {video_url}")
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                
                # Find the downloaded file
                audio_file = TEMP_DIR / f"{video_id}.wav"
                
                if audio_file.exists():
                    logger.info(f"✅ Downloaded: {audio_file}")
                    return audio_file
                else:
                    # Sometimes the file has a different extension
                    for ext in ['.wav', '.m4a', '.webm', '.opus']:
                        alt_file = TEMP_DIR / f"{video_id}{ext}"
                        if alt_file.exists():
                            logger.info(f"✅ Downloaded: {alt_file}")
                            return alt_file
                    
                    logger.error(f"Audio file not found after download: {video_id}")
                    return None
        
        except Exception as e:
            logger.error(f"Download error for {video_url}: {str(e)}")
            return None
    

    def download_audio_with_metadata(self, video_url, video_id):
        """
        Download audio AND extract comprehensive metadata from YouTube video
        
        Args:
            video_url: YouTube video URL
            video_id: Unique video identifier
            
        Returns:
            Tuple: (audio_file_path, metadata_dict) or (None, None)
        """
        try:
            logger.info(f"Downloading audio and metadata from: {video_url}")
            
            # Extract info without downloading first to get metadata
            # Enable comment extraction explicitly
            metadata_opts = {
                'quiet': True, 
                'cookiefile': '/app/youtube_cookies.txt',
                'getcomments': True,  # CRITICAL: Enable comment extraction
                'extractor_args': {'youtube': {'comment_sort': ['top'], 'max_comments': ['15,all,15,0']}},
            }
            with yt_dlp.YoutubeDL(metadata_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                # Extract metadata
                metadata = {
                    'title': info.get('title', 'Unknown'),
                    'description': info.get('description', ''),
                    'channel': info.get('uploader', info.get('channel', 'Unknown')),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'tags': info.get('tags', []),
                    'categories': info.get('categories', []),
                    'subtitles': [],
                    'comments': []
                }
                
                # Extract automatic captions (subtitles)
                if 'automatic_captions' in info and info['automatic_captions']:
                    # Try to get English captions
                    if 'en' in info['automatic_captions']:
                        caption_url = None
                        for caption in info['automatic_captions']['en']:
                            if caption.get('ext') == 'json3':
                                caption_url = caption.get('url')
                                break
                        
                        if caption_url:
                            try:
                                import requests
                                import json
                                response = requests.get(caption_url, timeout=10)
                                if response.ok:
                                    caption_data = response.json()
                                    # Extract text from caption events
                                    caption_text = []
                                    if 'events' in caption_data:
                                        for event in caption_data['events']:
                                            if 'segs' in event:
                                                for seg in event['segs']:
                                                    if 'utf8' in seg:
                                                        caption_text.append(seg['utf8'])
                                    metadata['subtitles'] = caption_text
                                    logger.info(f"✅ Extracted {len(caption_text)} caption segments")
                            except Exception as e:
                                logger.warning(f"Could not extract captions: {e}")
                
                # Extract top comments (if available) - FIRST 15 COMMENTS
                if 'comments' in info and info['comments']:
                    top_comments = []
                    for comment in info['comments'][:15]:  # Top 15 comments as requested
                        comment_text = comment.get('text', '')
                        author = comment.get('author', 'Unknown')
                        likes = comment.get('like_count', 0)
                        if comment_text:
                            top_comments.append({
                                'author': author,
                                'text': comment_text,
                                'likes': likes
                            })
                    metadata['comments'] = top_comments
                    logger.info(f"✅ Extracted {len(top_comments)} comments")
                else:
                    logger.warning("⚠️  No comments available for this video")
            
            # Now download audio with original options
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([video_url])
                
                # Find the downloaded file
                audio_file = TEMP_DIR / f"{video_id}.wav"
                
                if audio_file.exists():
                    logger.info(f"✅ Downloaded audio: {audio_file}")
                    return audio_file, metadata
                else:
                    # Check alternative extensions
                    for ext in ['.wav', '.m4a', '.webm', '.opus']:
                        alt_file = TEMP_DIR / f"{video_id}{ext}"
                        if alt_file.exists():
                            logger.info(f"✅ Downloaded audio: {alt_file}")
                            return alt_file, metadata
                    
                    logger.error(f"Audio file not found after download: {video_id}")
                    return None, None
        
        except Exception as e:
            logger.error(f"Download error for {video_url}: {str(e)}")
            return None, None


    def download_multiple(self, videos):
        """
        Download audio from multiple videos in parallel WITH metadata
        
        Args:
            videos: List of video info dicts
            
        Returns:
            List of tuples: (video_info, audio_file_path, metadata_dict)
        """
        logger.info(f"Starting parallel download of {len(videos)} videos with metadata")
        
        results = []
        start_time = time.time()
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_video = {
                executor.submit(self.download_audio_with_metadata, video['url'], video['id']): video
                for video in videos
            }
            
            for future in as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    result = future.result()
                    if result and result[0]:  # If audio_path exists
                        audio_path, metadata = result
                        results.append((video, audio_path, metadata))
                        logger.info(f"✅ Downloaded {len(results)}/{len(videos)} (with metadata)")
                except Exception as e:
                    logger.error(f"Failed to download {video['title']}: {str(e)}")
        
        elapsed = time.time() - start_time
        logger.info(f"Downloaded {len(results)} videos with metadata in {elapsed:.2f}s")
        
        return results
    
    def cleanup_temp_files(self):
        """Delete all temporary downloaded files"""
        try:
            for file in TEMP_DIR.glob('*'):
                file.unlink()
            logger.info("🧹 Cleaned up temporary video files")
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")


def search_vehicle_issue_videos(manufacturer, year, model, location, max_videos=15, audio_description=None, occurrence=None):
    """
    Search for YouTube videos matching vehicle issue
    
    Args:
        manufacturer: Vehicle manufacturer (e.g., "BMW")
        year: Vehicle year (e.g., "2024")
        model: Vehicle model (e.g., "3 Series")
        location: Sound location (e.g., "engine")
        max_videos: Maximum number of videos to download
        
    Returns:
        List of tuples: (video_info, audio_file_path)
    """
    # Build highly specific search query with all context
    query_parts = [manufacturer, str(year), model]
    
    if location and location != 'unknown':
        query_parts.append(location)
    
    if occurrence:
        query_parts.append(occurrence)
    
    if audio_description:
        query_parts.append(audio_description)
    
    query_parts.extend(["noise", "problem", "sound", "diagnosis"])
    
    query = " ".join(filter(None, query_parts))
    
    logger.info(f"🔍 Enhanced search query: {query}")
    
    downloader = YouTubeAudioDownloader(max_videos=max_videos)
    
    # Search for videos
    videos = downloader.search_videos(query, max_results=15)
    
    if not videos:
        logger.warning("No videos found, trying broader search")
        # Try broader query
        query = f"{manufacturer} {model} {location} noise"
        videos = downloader.search_videos(query, max_results=15)
    
    if not videos:
        logger.error("No videos found even with broader search")
        return []
    
    # Download audio from top videos
    results = downloader.download_multiple(videos[:max_videos])
    
    return results


# Test function
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("🧪 Testing YouTube Audio Downloader")
    print("="*60)
    
    # Test with BMW example
    results = search_vehicle_issue_videos(
        manufacturer="BMW",
        year="2024",
        model="3 Series",
        location="engine",
        max_videos=2
    )
    
    print(f"\n✅ Downloaded {len(results)} videos")
    for video, audio_path in results:
        print(f"\n📹 {video['title']}")
        print(f"   URL: {video['url']}")
        print(f"   Audio: {audio_path}")
    
    # Cleanup
    downloader = YouTubeAudioDownloader()
    downloader.cleanup_temp_files()
    
    print("\n" + "="*60)
    print("✅ Test complete!")
    print("="*60)





