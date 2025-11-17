"""
AI-Powered Diagnosis Engine using OpenRouter (Official API)
"""
import requests
import json
import logging

logger = logging.getLogger(__name__)

class AIDiagnosticEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    def analyze_with_all_sources(self, vehicle_info, sound_location, audio_features, youtube_data=None, enhanced_context=None):
        """
        Use GPT-4 via OpenRouter to analyze ALL collected data sources
        
        Args:
            vehicle_info: Vehicle details
            sound_location: Where sound is coming from
            audio_features: Audio analysis metrics
            youtube_data: Dict with titles, descriptions, comments, transcripts from 15 videos
            enhanced_context: User's description and context
        """
        try:
            context = self._build_comprehensive_context(
                vehicle_info, 
                sound_location, 
                audio_features, 
                youtube_data, 
                enhanced_context
            )
            
            logger.info("🤖 Sending comprehensive data to GPT-4 for analysis...")
            
            response = requests.post(
                url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://autodecx.app",
                    "X-Title": "AutoDecx",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": "openai/gpt-4o",
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are an expert automotive diagnostic technician with 20+ years experience.

You will receive data from MULTIPLE sources:
1. Audio frequency analysis (dominant frequency, vibration levels, patterns)
2. User's verbal description of the sound
3. When/where/how the issue occurs
4. YouTube video titles about similar issues (15 videos)
5. YouTube video descriptions with detailed explanations
6. YouTube comments from real users with same problem
7. YouTube video transcripts with diagnostic details

ANALYZE ALL SOURCES and find the COMMON DENOMINATOR - what issue is mentioned most frequently across all sources.

Your task:
- Read ALL the YouTube data carefully
- Identify the most commonly mentioned component/issue
- Cross-reference with audio metrics
- Consider user's description
- Provide ONE specific, actionable diagnosis

Format: [Component] failure - [Repair action]. [Additional technical context]
Example: "Brake pad wear with glazed rotors - Replace brake pads and resurface rotors. Common when pads reach wear indicators."

Be specific and actionable. Max 250 characters."""
                        },
                        {
                            "role": "user",
                            "content": context
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 150
                }),
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                diagnosis_text = result['choices'][0]['message']['content'].strip()
                
                # Calculate confidence based on data availability
                confidence = self._calculate_comprehensive_confidence(
                    audio_features, 
                    youtube_data, 
                    enhanced_context
                )
                
                sources_used = []
                if audio_features:
                    sources_used.append("Audio analysis")
                if youtube_data:
                    sources_used.append(f"{len(youtube_data.get('titles', []))} YouTube videos")
                    if youtube_data.get('comments'):
                        sources_used.append(f"{len(youtube_data['comments'])} comments")
                    if youtube_data.get('transcripts'):
                        sources_used.append(f"{len(youtube_data['transcripts'])} transcripts")
                if enhanced_context and enhanced_context.get('audio_description'):
                    sources_used.append("User description")
                
                logger.info(f"✅ AI Diagnosis (from {len(sources_used)} sources): {diagnosis_text}")
                
                return {
                    'diagnosis': diagnosis_text,
                    'confidence': confidence,
                    'ai_generated': True,
                    'sources_used': sources_used
                }
            else:
                logger.error(f"OpenRouter error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"AI diagnosis error: {str(e)}")
            return None
    
    def analyze_audio_features(self, vehicle_info, sound_location, audio_features, matched_video=None, enhanced_context=None):
        """
        Legacy method - kept for backward compatibility
        """
        # Convert to new method
        youtube_data = None
        if matched_video:
            youtube_data = {
                'titles': [matched_video.get('title', '')],
                'descriptions': [],
                'comments': [],
                'transcripts': [],
                'best_match': matched_video
            }
        
        return self.analyze_with_all_sources(
            vehicle_info, 
            sound_location, 
            audio_features, 
            youtube_data, 
            enhanced_context
        )
    
    def _build_diagnostic_context(self, vehicle_info, sound_location, audio_features, matched_video, enhanced_context=None):
        """Build diagnostic context"""
        context = f"""Vehicle: {vehicle_info.get('year')} {vehicle_info.get('manufacturer')} {vehicle_info.get('model')}
Location: {sound_location}
Frequency: {audio_features.get('dominant_frequency', 0):.0f} Hz
Vibration: {audio_features.get('rms_energy', 0):.1%}
Pattern ZCR: {audio_features.get('zero_crossing_rate', 0):.2f}
Bandwidth: {audio_features.get('spectral_bandwidth', 0):.0f} Hz"""
        
        if matched_video:
            context += f"\nReference: {matched_video.get('title', '')} ({matched_video.get('similarity', 0):.0%} match)"
        
        # Add enhanced user input context
        if enhanced_context:
            if enhanced_context.get('audio_description'):
                context += f"\nUser describes: {enhanced_context['audio_description']}"
            
            if enhanced_context.get('occurrence'):
                occurs = ', '.join(enhanced_context['occurrence'])
                context += f"\nOccurs when: {occurs}"
            
            if enhanced_context.get('issue_duration'):
                context += f"\nDuration: {enhanced_context['issue_duration']}"
            
            if enhanced_context.get('progression'):
                context += f"\nProgression: {enhanced_context['progression']}"
            
            if enhanced_context.get('recent_work'):
                context += f"\nRecent work: {enhanced_context['recent_work']}"
        
        context += "\n\nDiagnose the failing component and repair needed:"
        return context
    
    def _calculate_confidence(self, audio_features, matched_video):
        """Calculate confidence score"""
        conf = 80
        if audio_features.get('rms_energy', 0) > 0.1:
            conf += 5
        if 0.1 < audio_features.get('zero_crossing_rate', 0) < 0.3:
            conf += 5
        if matched_video and matched_video.get('similarity', 0) > 0.7:
            conf += 10
        return min(conf, 95)
    
    def _build_comprehensive_context(self, vehicle_info, sound_location, audio_features, youtube_data=None, enhanced_context=None):
        """
        Build comprehensive context from ALL data sources for AI analysis
        
        Args:
            vehicle_info: Vehicle details
            sound_location: Where sound is coming from
            audio_features: Audio analysis metrics
            youtube_data: Dict with titles, descriptions, comments, transcripts from videos
            enhanced_context: User's description and context
            
        Returns:
            String: Formatted context for AI
        """
        context_parts = []
        
        # Vehicle information
        context_parts.append(f"VEHICLE: {vehicle_info.get('year')} {vehicle_info.get('manufacturer')} {vehicle_info.get('model')}")
        context_parts.append(f"SOUND LOCATION: {sound_location}")
        
        # Audio analysis data
        context_parts.append("\nAUDIO ANALYSIS:")
        context_parts.append(f"- Dominant Frequency: {audio_features.get('dominant_frequency', 0):.0f} Hz")
        context_parts.append(f"- Vibration Level (RMS): {audio_features.get('rms_energy', 0):.3f}")
        context_parts.append(f"- Zero Crossing Rate: {audio_features.get('zero_crossing_rate', 0):.3f}")
        context_parts.append(f"- Spectral Bandwidth: {audio_features.get('spectral_bandwidth', 0):.0f} Hz")
        context_parts.append(f"- Spectral Rolloff: {audio_features.get('spectral_rolloff', 0):.0f} Hz")
        
        # User's description
        if enhanced_context:
            if enhanced_context.get('audio_description'):
                context_parts.append(f"\nUSER DESCRIPTION: {enhanced_context['audio_description']}")
            
            if enhanced_context.get('occurrence'):
                occurs = ', '.join(enhanced_context['occurrence'])
                context_parts.append(f"OCCURS WHEN: {occurs}")
            
            if enhanced_context.get('issue_duration'):
                context_parts.append(f"ISSUE DURATION: {enhanced_context['issue_duration']}")
            
            if enhanced_context.get('progression'):
                context_parts.append(f"PROGRESSION: {enhanced_context['progression']}")
            
            if enhanced_context.get('recent_work'):
                context_parts.append(f"RECENT WORK: {enhanced_context['recent_work']}")
        
        # YouTube data - THE MOST IMPORTANT PART
        if youtube_data:
            # Add video titles
            if youtube_data.get('titles'):
                context_parts.append(f"\nYOUTUBE VIDEO TITLES ({len(youtube_data['titles'])} videos):")
                for i, title in enumerate(youtube_data['titles'][:15], 1):
                    context_parts.append(f"{i}. {title}")
            
            # Add descriptions (condensed)
            if youtube_data.get('descriptions'):
                context_parts.append(f"\nYOUTUBE VIDEO DESCRIPTIONS:")
                for i, desc in enumerate(youtube_data['descriptions'][:10], 1):
                    # Take first 200 chars of each description
                    desc_excerpt = desc[:200] if desc else ""
                    if desc_excerpt:
                        context_parts.append(f"{i}. {desc_excerpt}...")
            
            # Add comments
            if youtube_data.get('comments'):
                context_parts.append(f"\nYOUTUBE COMMENTS ({len(youtube_data['comments'])} comments):")
                for i, comment in enumerate(youtube_data['comments'][:15], 1):
                    context_parts.append(f"- {comment[:150]}")
            
            # Add transcripts (condensed)
            if youtube_data.get('transcripts'):
                context_parts.append(f"\nYOUTUBE VIDEO TRANSCRIPTS ({len(youtube_data['transcripts'])} transcripts):")
                for i, transcript in enumerate(youtube_data['transcripts'][:5], 1):
                    # Take first 300 chars of each transcript
                    transcript_excerpt = transcript[:300] if transcript else ""
                    if transcript_excerpt:
                        context_parts.append(f"{i}. {transcript_excerpt}...")
            
            # Add best match info
            if youtube_data.get('best_match'):
                best_match = youtube_data['best_match']
                context_parts.append(f"\nBEST AUDIO MATCH: {best_match.get('video_title', 'Unknown')} ({best_match.get('similarity', 0)*100:.1f}% similarity)")
        
        context_parts.append("\n\nBased on ALL the data above (especially the YouTube titles, descriptions, comments, and transcripts), what is the MOST COMMON diagnosis mentioned? Provide a specific, actionable diagnosis:")
        
        return "\n".join(context_parts)
    
    def _calculate_comprehensive_confidence(self, audio_features, youtube_data, enhanced_context):
        """
        Calculate confidence score based on data availability and quality
        
        Args:
            audio_features: Audio analysis metrics
            youtube_data: YouTube data collected
            enhanced_context: User's context
            
        Returns:
            Integer: Confidence score (0-95)
        """
        confidence = 70  # Base confidence
        
        # Audio features quality
        if audio_features:
            if audio_features.get('rms_energy', 0) > 0.05:
                confidence += 5  # Good audio signal
            if 0.05 < audio_features.get('zero_crossing_rate', 0) < 0.4:
                confidence += 5  # Normal pattern
        
        # YouTube data availability
        if youtube_data:
            num_videos = len(youtube_data.get('titles', []))
            if num_videos >= 10:
                confidence += 10  # Excellent data
            elif num_videos >= 5:
                confidence += 7   # Good data
            elif num_videos >= 1:
                confidence += 3   # Some data
            
            # Bonus for comments and transcripts
            if youtube_data.get('comments'):
                confidence += 3
            if youtube_data.get('transcripts'):
                confidence += 3
            
            # Bonus for good audio match
            if youtube_data.get('best_match'):
                similarity = youtube_data['best_match'].get('similarity', 0)
                if similarity > 0.7:
                    confidence += 5
                elif similarity > 0.5:
                    confidence += 3
        
        # User context quality
        if enhanced_context:
            if enhanced_context.get('audio_description'):
                confidence += 3
            if enhanced_context.get('occurrence'):
                confidence += 2
        
        return min(confidence, 95)  # Cap at 95%




