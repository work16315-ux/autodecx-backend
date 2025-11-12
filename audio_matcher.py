# audio_matcher.py
import librosa
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def extract_audio_features(audio_path, sr=22050, duration=10):
    """
    Extract comprehensive audio features for comparison
    (This runs in background - user never sees this)
    """
    try:
        # Load audio
        y, sr = librosa.load(audio_path, sr=sr, duration=duration)
        
        # MFCC features (voice/sound fingerprint)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        mfcc_mean = np.mean(mfccs, axis=1)
        
        # Spectral features
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr))
        spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))
        zero_crossing_rate = np.mean(librosa.feature.zero_crossing_rate(y))
        
        # Combine all features
        features = np.concatenate([
            mfcc_mean,
            [spectral_centroid, spectral_rolloff, spectral_bandwidth, zero_crossing_rate]
        ])
        
        return features
    
    except Exception as e:
        logger.error(f"Feature extraction error: {str(e)}")
        return None


def compare_audio_similarity(user_audio_path, reference_audio_path):
    """
    Compare two audio files and return similarity score
    (This runs in background - user never sees this)
    
    Returns:
        Similarity score (0.0 to 1.0)
    """
    # Extract features from both
    user_features = extract_audio_features(user_audio_path)
    ref_features = extract_audio_features(reference_audio_path)
    
    if user_features is None or ref_features is None:
        return 0.0
    
    # Calculate cosine similarity
    user_features = user_features.reshape(1, -1)
    ref_features = ref_features.reshape(1, -1)
    
    similarity = cosine_similarity(user_features, ref_features)[0][0]
    
    # Convert to 0-100 scale
    similarity_percent = max(0, min(100, similarity * 100))
    
    return similarity_percent


def find_best_audio_match(user_audio_path, youtube_results):
    """
    Find the best matching YouTube video based on audio similarity
    (This runs in background - user never sees this)
    
    Args:
        user_audio_path: Path to user's recorded audio
        youtube_results: List of (video_info, audio_path) tuples
        
    Returns:
        Dict with best match info and inferred diagnosis
    """
    best_match = {
        'similarity': 0.0,
        'video_title': 'Unknown',
        'issue_type': 'Unable to determine issue',
        'confidence': 0.5
    }
    
    for video_info, ref_audio_path in youtube_results:
        similarity = compare_audio_similarity(user_audio_path, ref_audio_path)
        
        if similarity > best_match['similarity']:
            best_match['similarity'] = similarity / 100  # Convert to 0-1
            best_match['video_title'] = video_info['title']
            
            # Infer issue type from video title (background analysis)
            title_lower = video_info['title'].lower()
            
            if 'belt' in title_lower or 'squeal' in title_lower:
                best_match['issue_type'] = 'Belt squeal detected - serpentine belt replacement recommended'
            elif 'bearing' in title_lower or 'wheel bearing' in title_lower:
                best_match['issue_type'] = 'Bearing wear detected - inspect wheel bearings'
            elif 'misfire' in title_lower or 'cylinder' in title_lower:
                best_match['issue_type'] = 'Engine misfire detected - check spark plugs and ignition'
            elif 'exhaust' in title_lower or 'leak' in title_lower:
                best_match['issue_type'] = 'Exhaust leak detected - inspect exhaust system'
            elif 'brake' in title_lower or 'brakes' in title_lower:
                best_match['issue_type'] = 'Brake noise detected - inspect brake pads and rotors'
            elif 'timing' in title_lower or 'chain' in title_lower:
                best_match['issue_type'] = 'Timing chain/belt issue detected - immediate inspection needed'
            else:
                best_match['issue_type'] = f'Mechanical issue detected - similar to common {video_info["channel"]} diagnosis'
            
            best_match['confidence'] = best_match['similarity']
    
    logger.info(f"Best match: {best_match['video_title']} (similarity: {best_match['similarity']*100:.1f}%)")
    
    return best_match