# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
import subprocess
import os
from pathlib import Path
import uuid
from datetime import datetime
import logging
import traceback
import requests
from vehicle_api import vehicle_bp
from youtube_helper import search_vehicle_issue_videos, YouTubeAudioDownloader
from audio_matcher import find_best_audio_match
import json

app = Flask(__name__)

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

log_dir = Path('./logs')
log_dir.mkdir(exist_ok=True)

file_handler = logging.FileHandler(log_dir / f'autodecx_{datetime.now().strftime("%Y%m%d")}.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
logger.addHandler(console_handler)

logger.info("="*60)
logger.info("AutoDecX Audio Analysis Backend Initialized")
logger.info("="*60)

# ============================================================
# FLASK CONFIGURATION
# ============================================================

# UPDATED: Allow Vercel frontend domain
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173", 
            "http://127.0.0.1:5173",
            "https://*.vercel.app",  # Allow all Vercel deployments
            "https://autodecx-test.vercel.app"  # Your specific domain (update this after deployment)
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

UPLOAD_FOLDER = Path('./uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(vehicle_bp)
logger.info("✅ Vehicle API blueprint registered")

# ============================================================
# REQUEST LOGGING MIDDLEWARE
# ============================================================

@app.before_request
def log_request_info():
    """Log incoming request details"""
    logger.info(f"Incoming request: {request.method} {request.path}")
    logger.info(f"Remote address: {request.remote_addr}")
    logger.info(f"User agent: {request.headers.get('User-Agent', 'Unknown')}")
    if request.method == 'POST':
        logger.info(f"Content type: {request.content_type}")
        logger.info(f"Content length: {request.content_length} bytes")

@app.after_request
def log_response_info(response):
    """Log response details"""
    logger.info(f"Response status: {response.status_code}")
    logger.info(f"Response size: {response.content_length} bytes")
    return response

# ============================================================
# ROUTES
# ============================================================

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint accessed")
    return jsonify({
        'status': 'running',
        'service': 'AutoDecX Audio Analysis API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_audio():
    """Main audio upload and analysis endpoint"""
    
    if request.method == 'OPTIONS':
        logger.info("CORS preflight request handled")
        return '', 204
    
    request_id = str(uuid.uuid4())[:8]
    logger.info("="*60)
    logger.info(f"[{request_id}] NEW AUDIO UPLOAD REQUEST")
    logger.info("="*60)
    
    print("\n" + "="*60)
    print("🎵 AUDIO UPLOAD RECEIVED")
    print("="*60)
    
    try:
        if 'audio' not in request.files:
            logger.error(f"[{request_id}] No audio field in request.files")
            logger.error(f"[{request_id}] Available fields: {list(request.files.keys())}")
            print("❌ No 'audio' field found")
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio']
        
        if file.filename == '':
            logger.error(f"[{request_id}] Empty filename received")
            return jsonify({'error': 'Empty filename'}), 400
        
        # Get vehicle info (if provided)
        vehicle_info = None
        if 'vehicle_info' in request.form:
            vehicle_info = json.loads(request.form['vehicle_info'])
            logger.info(f"[{request_id}] Vehicle info received: {vehicle_info}")
        
        logger.info(f"[{request_id}] File received: {file.filename}")
        logger.info(f"[{request_id}] Content type: {file.content_type}")
        
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        original_path = UPLOAD_FOLDER / f"original_{timestamp}_{unique_id}.webm"
        converted_path = UPLOAD_FOLDER / f"converted_{timestamp}_{unique_id}.wav"
        
        logger.info(f"[{request_id}] Saving to: {original_path}")
        print(f"📁 Saving to: {original_path}")
        
        file.save(original_path)
        file_size = original_path.stat().st_size
        
        logger.info(f"[{request_id}] File saved successfully: {file_size:,} bytes")
        print(f"📊 File size: {file_size:,} bytes")
        
        ffmpeg_command = [
            "ffmpeg", "-y",
            "-i", str(original_path),
            "-ac", "1",
            "-ar", "44100",
            "-acodec", "pcm_s16le",
            str(converted_path)
        ]
        
        logger.info(f"[{request_id}] Starting FFmpeg conversion...")
        print("🔄 Running FFmpeg conversion...")
        
        conversion_start = datetime.now()
        result = subprocess.run(
            ffmpeg_command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        conversion_time = (datetime.now() - conversion_start).total_seconds()
        
        logger.info(f"[{request_id}] FFmpeg conversion complete in {conversion_time:.2f}s")
        print("✅ Conversion complete")
        
        logger.info(f"[{request_id}] Starting audio analysis with librosa...")
        print("🔬 Analyzing audio with librosa...")
        
        analysis_start = datetime.now()
        y, sr = librosa.load(str(converted_path), sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
        
        logger.info(f"[{request_id}] Audio loaded: duration={duration:.2f}s, sr={sr}Hz, samples={len(y)}")
        
        rms = float(np.mean(librosa.feature.rms(y=y)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        
        logger.info(f"[{request_id}] Basic features extracted: RMS={rms:.4f}, ZCR={zcr:.4f}")
        
        try:
            tempo_result, _ = librosa.beat.beat_track(y=y, sr=sr)
            if isinstance(tempo_result, np.ndarray):
                tempo = float(tempo_result.item()) if tempo_result.size > 0 else 0.0
            else:
                tempo = float(tempo_result) if tempo_result else 0.0
            logger.info(f"[{request_id}] Tempo detected: {tempo:.1f} BPM")
        except Exception as e:
            logger.warning(f"[{request_id}] Tempo detection failed: {e}")
            print(f"⚠️ Tempo detection failed: {e}")
            tempo = 0.0
        
        spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        spectral_rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
        spectral_bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
        
        logger.info(f"[{request_id}] Spectral features: centroid={spectral_centroid:.1f}Hz, rolloff={spectral_rolloff:.1f}Hz, bandwidth={spectral_bandwidth:.1f}Hz")
        
        analysis_time = (datetime.now() - analysis_start).total_seconds()
        logger.info(f"[{request_id}] Analysis complete in {analysis_time:.2f}s")
        
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"🎯 RMS: {rms:.4f}")
        print(f"〰️  ZCR: {zcr:.4f}")
        print(f"🎵 Tempo: {tempo:.1f} BPM")
        print(f"📊 Spectral Centroid: {spectral_centroid:.1f} Hz")
        print(f"📈 Spectral Rolloff: {spectral_rolloff:.1f} Hz")
        print(f"📏 Spectral Bandwidth: {spectral_bandwidth:.1f} Hz")
        
        # Build initial response
        response = {
            'success': True,
            'metrics': {
                'duration': round(duration, 2),
                'sample_rate': int(sr),
                'rms': round(rms, 4),
                'zero_crossing_rate': round(zcr, 4),
                'tempo': round(tempo, 1),
                'dominant_frequency': round(spectral_centroid, 2),
                'spectral_rolloff': round(spectral_rolloff, 2),
                'spectral_bandwidth': round(spectral_bandwidth, 2),
                'vibration_level': round(rms, 4)
            },
            'issues': [],
            'predicted_issue': 'No significant issues detected',
            'confidence': 0.85
        }
        
        # ENHANCED: YouTube-based diagnosis (SILENT - runs in background)
        if vehicle_info:
            try:
                logger.info(f"[{request_id}] Starting YouTube analysis (background)...")
                print("🎥 Searching YouTube for similar issues (background)...")
                
                # Search and download (background)
                youtube_results = search_vehicle_issue_videos(
                    manufacturer=vehicle_info['manufacturer'],
                    year=vehicle_info['year'],
                    model=vehicle_info['model'],
                    location=vehicle_info['soundLocation'],
                    max_videos=3
                )
                
                if youtube_results:
                    logger.info(f"[{request_id}] Found {len(youtube_results)} YouTube matches")
                    print(f"✅ Found {len(youtube_results)} reference videos")
                    
                    # Compare audio (background)
                    best_match = find_best_audio_match(str(converted_path), youtube_results)
                    
                    logger.info(f"[{request_id}] Best match similarity: {best_match['similarity']*100:.1f}%")
                    
                    # Use YouTube match to enhance diagnosis (if confidence high)
                    if best_match['similarity'] > 0.70:
                        response['predicted_issue'] = best_match['issue_type']
                        response['confidence'] = round(best_match['similarity'], 2)
                        logger.info(f"[{request_id}] Using YouTube-matched diagnosis")
                        print(f"✅ High confidence match found ({best_match['similarity']*100:.0f}%)")
                    
                    # Cleanup downloaded videos (background)
                    downloader = YouTubeAudioDownloader()
                    downloader.cleanup_temp_files()
                else:
                    logger.warning(f"[{request_id}] No YouTube results found, using rule-based")
                    print("⚠️  No YouTube matches, using rule-based analysis")
            
            except Exception as e:
                logger.error(f"[{request_id}] YouTube analysis failed: {str(e)}")
                print(f"⚠️  YouTube analysis failed, using rule-based fallback")
                # Continue with rule-based diagnostics
        
        # Existing rule-based diagnostics (as fallback)
        logger.info(f"[{request_id}] Running rule-based diagnostics...")
        print("\n🔍 Running diagnostic analysis...")
        
        issue_count = 0
        
        if rms > 0.20:
            response['issues'].append({
                'type': 'critical_vibration',
                'severity': 'error',
                'message': 'Critical vibration levels detected - immediate inspection recommended'
            })
            logger.warning(f"[{request_id}] CRITICAL: Very high vibration (RMS={rms:.4f})")
            print("❌ CRITICAL: Very high vibration")
            issue_count += 1
        elif rms > 0.15:
            response['issues'].append({
                'type': 'high_vibration',
                'severity': 'warning',
                'message': 'Elevated vibration levels - check engine mounts or bearings'
            })
            logger.warning(f"[{request_id}] WARNING: High vibration (RMS={rms:.4f})")
            print("⚠️  WARNING: High vibration")
            issue_count += 1
        elif rms < 0.01:
            response['issues'].append({
                'type': 'low_signal',
                'severity': 'info',
                'message': 'Very low signal - move microphone closer to sound source'
            })
            logger.info(f"[{request_id}] INFO: Low signal (RMS={rms:.4f})")
            print("ℹ️  INFO: Low signal strength")
            issue_count += 1
        else:
            logger.info(f"[{request_id}] Vibration level: Normal (RMS={rms:.4f})")
            print("✅ Vibration level: Normal")
        
        if spectral_centroid > 6000:
            response['issues'].append({
                'type': 'critical_high_frequency',
                'severity': 'error',
                'message': 'Critical high-frequency noise - likely bearing failure or severe wear'
            })
            logger.warning(f"[{request_id}] CRITICAL: Extremely high frequency ({spectral_centroid:.1f}Hz)")
            print("❌ CRITICAL: Extremely high frequency")
            issue_count += 1
        elif spectral_centroid > 5000:
            response['issues'].append({
                'type': 'very_high_frequency',
                'severity': 'warning',
                'message': 'Very high-frequency noise - possible bearing wear or air leak'
            })
            logger.warning(f"[{request_id}] WARNING: Very high frequency ({spectral_centroid:.1f}Hz)")
            print("⚠️  WARNING: Very high frequency")
            issue_count += 1
        elif spectral_centroid > 3000:
            response['issues'].append({
                'type': 'high_frequency_noise',
                'severity': 'info',
                'message': 'High-frequency noise - possible belt squeal or pulley issue'
            })
            logger.info(f"[{request_id}] INFO: High frequency ({spectral_centroid:.1f}Hz)")
            print("ℹ️  INFO: High frequency detected")
            issue_count += 1
        elif spectral_centroid < 500:
            response['issues'].append({
                'type': 'low_frequency_rumble',
                'severity': 'info',
                'message': 'Low-frequency rumble - possible exhaust or suspension issue'
            })
            logger.info(f"[{request_id}] INFO: Low frequency rumble ({spectral_centroid:.1f}Hz)")
            print("ℹ️  INFO: Low frequency rumble")
            issue_count += 1
        elif spectral_centroid < 300:
            response['issues'].append({
                'type': 'very_low_frequency',
                'severity': 'warning',
                'message': 'Very low-frequency noise - possible structural or mounting issue'
            })
            logger.warning(f"[{request_id}] WARNING: Very low frequency ({spectral_centroid:.1f}Hz)")
            print("⚠️  WARNING: Very low frequency")
            issue_count += 1
        else:
            logger.info(f"[{request_id}] Frequency range: Normal ({spectral_centroid:.1f}Hz)")
            print("✅ Frequency range: Normal")
        
        if zcr > 0.30:
            response['issues'].append({
                'type': 'critical_irregular',
                'severity': 'error',
                'message': 'Critical irregular pattern - possible severe misfire or mechanical failure'
            })
            logger.warning(f"[{request_id}] CRITICAL: Highly irregular pattern (ZCR={zcr:.4f})")
            print("❌ CRITICAL: Highly irregular pattern")
            issue_count += 1
        elif zcr > 0.25:
            response['issues'].append({
                'type': 'highly_irregular',
                'severity': 'warning',
                'message': 'Highly irregular pattern - possible misfire or timing issue'
            })
            logger.warning(f"[{request_id}] WARNING: Irregular pattern (ZCR={zcr:.4f})")
            print("⚠️  WARNING: Irregular pattern")
            issue_count += 1
        elif zcr > 0.20:
            response['issues'].append({
                'type': 'irregular_pattern',
                'severity': 'info',
                'message': 'Irregular acoustic pattern - monitor for changes'
            })
            logger.info(f"[{request_id}] INFO: Slight irregularity (ZCR={zcr:.4f})")
            print("ℹ️  INFO: Slight irregularity")
            issue_count += 1
        elif zcr < 0.05:
            response['issues'].append({
                'type': 'very_smooth_pattern',
                'severity': 'info',
                'message': 'Very smooth pattern - consider if this is expected for the test'
            })
            logger.info(f"[{request_id}] INFO: Very smooth pattern (ZCR={zcr:.4f})")
            print("ℹ️  INFO: Very smooth pattern")
            issue_count += 1
        else:
            logger.info(f"[{request_id}] Pattern regularity: Normal (ZCR={zcr:.4f})")
            print("✅ Pattern regularity: Normal")
        
        if spectral_bandwidth > 3000:
            response['issues'].append({
                'type': 'wide_frequency_spread',
                'severity': 'warning',
                'message': 'Wide frequency spread - possible multiple simultaneous issues'
            })
            logger.warning(f"[{request_id}] WARNING: Wide frequency spread ({spectral_bandwidth:.1f}Hz)")
            print("⚠️  WARNING: Wide frequency spread")
            issue_count += 1
        elif spectral_bandwidth < 500:
            response['issues'].append({
                'type': 'narrow_frequency',
                'severity': 'info',
                'message': 'Narrow frequency band - single dominant sound source'
            })
            logger.info(f"[{request_id}] INFO: Narrow frequency band ({spectral_bandwidth:.1f}Hz)")
            print("ℹ️  INFO: Narrow frequency band")
            issue_count += 1
        else:
            logger.info(f"[{request_id}] Frequency spread: Normal ({spectral_bandwidth:.1f}Hz)")
            print("✅ Frequency spread: Normal")
        
        if rms > 0.15 and spectral_centroid > 4000:
            response['issues'].append({
                'type': 'vibration_and_high_freq',
                'severity': 'error',
                'message': 'High vibration with high-frequency noise - critical bearing or pulley wear'
            })
            logger.warning(f"[{request_id}] CRITICAL: Combined vibration and frequency issue")
            print("❌ CRITICAL: Combined vibration and frequency issue")
            issue_count += 1
        
        if rms > 0.15 and zcr > 0.20:
            response['issues'].append({
                'type': 'vibration_and_irregular',
                'severity': 'warning',
                'message': 'High vibration with irregular pattern - possible engine mount or timing issue'
            })
            logger.warning(f"[{request_id}] WARNING: Combined vibration and irregularity")
            print("⚠️  WARNING: Combined vibration and irregularity")
            issue_count += 1
        
        if spectral_centroid < 800 and rms > 0.10:
            response['issues'].append({
                'type': 'low_freq_high_energy',
                'severity': 'warning',
                'message': 'Low-frequency high-energy noise - possible exhaust or structural issue'
            })
            logger.warning(f"[{request_id}] WARNING: Low-frequency high-energy")
            print("⚠️  WARNING: Low-frequency high-energy")
            issue_count += 1
        
        if duration < 3:
            response['issues'].append({
                'type': 'short_recording',
                'severity': 'info',
                'message': 'Recording too short for reliable analysis - recommend 5-10 seconds'
            })
            logger.info(f"[{request_id}] INFO: Short recording ({duration:.2f}s)")
            print("ℹ️  INFO: Short recording duration")
            issue_count += 1
        elif duration > 15:
            response['issues'].append({
                'type': 'long_recording',
                'severity': 'info',
                'message': 'Long recording detected - using average values'
            })
            logger.info(f"[{request_id}] INFO: Long recording ({duration:.2f}s)")
            print("ℹ️  INFO: Long recording")
            issue_count += 1
        
        # Only update if YouTube didn't already provide better diagnosis
        if len(response['issues']) > 0 and response['confidence'] < 0.90:
            severity_order = {'error': 0, 'warning': 1, 'info': 2}
            sorted_issues = sorted(response['issues'], key=lambda x: severity_order[x['severity']])
            
            # Only override if YouTube diagnosis wasn't confident
            if response['predicted_issue'] == 'No significant issues detected':
                response['predicted_issue'] = sorted_issues[0]['message']
            
            critical_count = sum(1 for i in response['issues'] if i['severity'] == 'error')
            warning_count = sum(1 for i in response['issues'] if i['severity'] == 'warning')
            
            if critical_count > 0:
                if response['confidence'] < 0.95:
                    response['confidence'] = 0.95
                logger.warning(f"[{request_id}] Overall assessment: CRITICAL ({critical_count} critical issues)")
                print("\n❌ Overall assessment: CRITICAL")
            elif warning_count > 2:
                if response['confidence'] < 0.85:
                    response['confidence'] = 0.85
                logger.warning(f"[{request_id}] Overall assessment: WARNING ({warning_count} warnings)")
                print("\n⚠️  Overall assessment: WARNING (Multiple issues)")
            elif warning_count > 0:
                if response['confidence'] < 0.80:
                    response['confidence'] = 0.80
                logger.warning(f"[{request_id}] Overall assessment: WARNING")
                print("\n⚠️  Overall assessment: WARNING")
            else:
                if response['confidence'] < 0.75:
                    response['confidence'] = 0.75
                logger.info(f"[{request_id}] Overall assessment: INFORMATIONAL")
                print("\nℹ️  Overall assessment: INFORMATIONAL")
        elif len(response['issues']) == 0:
            logger.info(f"[{request_id}] Overall assessment: NORMAL")
            print("\n✅ Overall assessment: NORMAL")
        
        # Cleanup user's audio files
        os.remove(original_path)
        os.remove(converted_path)
        logger.info(f"[{request_id}] User audio files cleaned up")
        print("🧹 Temporary files cleaned up")
        
        total_time = conversion_time + analysis_time
        
        print("="*60)
        print("✅ ANALYSIS COMPLETE")
        print(f"📋 Primary Issue: {response['predicted_issue']}")
        print(f"🎯 Confidence: {response['confidence']*100:.0f}%")
        print(f"🔍 Total Issues Found: {len(response['issues'])}")
        print(f"⏱️  Processing Time: {total_time:.2f}s")
        print("="*60 + "\n")
        
        logger.info("="*60)
        logger.info(f"[{request_id}] ANALYSIS COMPLETE")
        logger.info(f"[{request_id}] Primary Issue: {response['predicted_issue']}")
        logger.info(f"[{request_id}] Confidence: {response['confidence']*100:.0f}%")
        logger.info(f"[{request_id}] Total Issues: {len(response['issues'])}")
        logger.info(f"[{request_id}] Processing Time: {total_time:.2f}s (conversion: {conversion_time:.2f}s, analysis: {analysis_time:.2f}s)")
        logger.info("="*60)
        
        return jsonify(response)
    
    except subprocess.TimeoutExpired:
        logger.error(f"[{request_id}] FFmpeg conversion timeout")
        print("❌ FFmpeg timeout")
        return jsonify({'error': 'Audio conversion timeout'}), 500
    
    except Exception as e:
        logger.error(f"[{request_id}] Upload processing error: {str(e)}")
        logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    logger.error(f"File upload too large: {request.content_length} bytes")
    return jsonify({'error': 'File too large. Maximum size is 10 MB.'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================
# APPLICATION STARTUP
# ============================================================

if __name__ == '__main__':
    logger.info("\n" + "="*60)
    logger.info("🚀 Starting AutoDecX Audio Analysis Backend")
    logger.info("="*60)
    logger.info("📡 Server: http://127.0.0.1:5000")
    logger.info("🔧 Endpoints:")
    logger.info("   GET  /       → Health check")
    logger.info("   POST /upload → Audio analysis")
    logger.info("   GET  /api/vehicle-models → Vehicle model lookup")
    logger.info("📁 Upload folder: " + str(UPLOAD_FOLDER.absolute()))
    logger.info("📄 Log folder: " + str(log_dir.absolute()))
    logger.info("="*60)
    
    print("\n" + "="*60)
    print("🚀 AutoDecX Audio Analysis Backend")
    print("="*60)
    print("📡 Running on http://127.0.0.1:5000")
    print("🔧 Endpoints:")
    print("   GET  /       → Health check")
    print("   POST /upload → Audio analysis")
    print("   GET  /api/vehicle-models → Vehicle model lookup")
    print("="*60 + "\n")
    
    # UPDATED FOR PRODUCTION: Railway deployment
    port = int(os.environ.get('PORT', 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )