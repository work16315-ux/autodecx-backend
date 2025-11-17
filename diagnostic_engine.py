"""
Comprehensive Diagnostic Engine
Combines multiple data sources for accurate vehicle diagnosis
"""

import logging
from collections import Counter
import re

logger = logging.getLogger(__name__)


class VehicleSpecificationChecker:
    """Check vehicle specifications to filter impossible diagnoses"""
    
    # Common vehicle features by manufacturer
    TURBO_MODELS = {
        'BMW': ['335i', '535i', 'M235i', 'M135i', '340i', '440i', 'X3 28i', 'X5 35i'],
        'Audi': ['A3', 'A4', 'A6', 'Q5', 'TT', 'S3', 'S4', 'S5'],
        'Mercedes-Benz': ['C250', 'C300', 'E250', 'GLC250', 'CLA250', 'AMG'],
        'Volkswagen': ['GTI', 'Golf R', 'Jetta GLI', 'Tiguan', 'Passat'],
        'Ford': ['EcoBoost', 'Mustang', 'F-150', 'Explorer'],
        'Toyota': [],  # Most Toyotas non-turbo (except recent models)
        'Honda': ['Civic Type R', 'Accord 2.0T'],
        'Mazda': ['CX-7', 'CX-9', 'MazdaSpeed'],
        'Hyundai': ['Veloster N', 'Sonata 2.0T', 'Santa Fe'],
        'Nissan': ['Juke', 'Sentra', 'Altima']
    }
    
    @staticmethod
    def has_turbo(manufacturer, model, year):
        """Check if vehicle likely has turbocharger"""
        # After 2016, many manufacturers added turbos
        if year >= 2016:
            if manufacturer in ['BMW', 'Audi', 'Mercedes-Benz', 'Volkswagen']:
                return True
        
        # Check specific models
        if manufacturer in VehicleSpecificationChecker.TURBO_MODELS:
            model_list = VehicleSpecificationChecker.TURBO_MODELS[manufacturer]
            model_lower = model.lower()
            
            for turbo_model in model_list:
                if turbo_model.lower() in model_lower:
                    return True
        
        # Keywords in model name
        turbo_keywords = ['turbo', 'tsi', 'tfsi', 'ecoboost', 'tdi', 'gti']
        model_lower = model.lower()
        for keyword in turbo_keywords:
            if keyword in model_lower:
                return True
        
        return False
    
    @staticmethod
    def has_diesel(manufacturer, model, year):
        """Check if vehicle is diesel"""
        diesel_keywords = ['diesel', 'tdi', 'd', 'dci', 'hdi', 'crdi']
        model_lower = model.lower()
        
        for keyword in diesel_keywords:
            if keyword in model_lower:
                return True
        
        return False
    
    @staticmethod
    def filter_diagnosis(diagnosis, manufacturer, model, year):
        """Filter out impossible diagnoses based on vehicle specs"""
        diagnosis_lower = diagnosis.lower()
        
        # Check turbo-related issues
        turbo_keywords = ['turbo', 'wastegate', 'boost', 'supercharger']
        has_turbo_issue = any(keyword in diagnosis_lower for keyword in turbo_keywords)
        
        if has_turbo_issue and not VehicleSpecificationChecker.has_turbo(manufacturer, model, year):
            logger.info(f"Filtered out turbo-related diagnosis for non-turbo vehicle: {manufacturer} {model} {year}")
            return False
        
        # Check diesel-related issues
        diesel_keywords = ['diesel', 'dpf', 'def', 'egr']
        has_diesel_issue = any(keyword in diagnosis_lower for keyword in diesel_keywords)
        
        if has_diesel_issue and not VehicleSpecificationChecker.has_diesel(manufacturer, model, year):
            logger.info(f"Filtered out diesel-related diagnosis for non-diesel vehicle")
            return False
        
        return True


class DiagnosisAggregator:
    """Aggregate diagnoses from multiple sources and find common denominator"""
    
    @staticmethod
    def extract_keywords(text):
        """Extract diagnostic keywords from text"""
        if not text:
            return []
        
        text_lower = text.lower()
        
        # Common diagnostic keywords (expanded with more specific components)
        keywords = [
            'brake', 'brakes', 'pad', 'pads', 'rotor', 'rotors', 'caliper',
            'bearing', 'bearings', 'wheel bearing', 'hub bearing',
            'belt', 'serpentine', 'serpentine belt', 'timing belt', 'timing chain',
            'exhaust', 'muffler', 'catalytic converter', 'manifold',
            'suspension', 'shock', 'shocks', 'strut', 'struts', 'strut mount',
            'engine', 'motor', 'piston', 'cylinder',
            'transmission', 'gearbox', 'clutch',
            'turbo', 'turbocharger', 'wastegate', 'boost',
            'alternator', 'starter', 'battery',
            'pulley', 'idler', 'tensioner', 'timing chain tensioner',
            'mount', 'engine mount', 'motor mount', 'transmission mount',
            'cv joint', 'cv axle', 'axle', 'driveshaft',
            'tire', 'tires', 'wheel',
            'leak', 'leaking', 'fluid',
            'worn', 'wear', 'damage', 'damaged',
            'loose', 'broken', 'cracked',
            'misfire', 'ignition', 'spark plug', 'coil',
            'sway bar', 'ball joint', 'tie rod', 'control arm',
            'power steering', 'rack and pinion', 'steering',
            'vanos', 'variable valve timing', 'vvt'
        ]
        
        found_keywords = []
        for keyword in keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    @staticmethod
    def normalize_diagnosis(diagnosis):
        """Normalize diagnosis text for comparison"""
        if not diagnosis:
            return ""
        
        # Convert to lowercase
        normalized = diagnosis.lower()
        
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    @staticmethod
    def aggregate_diagnoses(
        youtube_titles=None,
        youtube_descriptions=None,
        youtube_comments=None,
        youtube_transcripts=None,
        spectrogram_match=None,
        ai_diagnosis=None,
        vehicle_info=None
    ):
        """
        Aggregate all diagnosis sources and find common denominator
        
        Returns:
            dict with diagnosis, confidence, and sources
        """
        all_keywords = []
        all_diagnoses = []
        sources = []
        
        # Extract from YouTube video titles
        if youtube_titles:
            for title in youtube_titles:
                keywords = DiagnosisAggregator.extract_keywords(title)
                all_keywords.extend(keywords)
                all_diagnoses.append(DiagnosisAggregator.normalize_diagnosis(title))
            sources.append(f"YouTube titles ({len(youtube_titles)})")
            logger.info(f"Processed {len(youtube_titles)} YouTube titles")
        
        # Extract from YouTube descriptions
        if youtube_descriptions:
            for desc in youtube_descriptions:
                keywords = DiagnosisAggregator.extract_keywords(desc)
                all_keywords.extend(keywords)
                all_diagnoses.append(DiagnosisAggregator.normalize_diagnosis(desc))
            sources.append(f"YouTube descriptions ({len(youtube_descriptions)})")
            logger.info(f"Processed {len(youtube_descriptions)} YouTube descriptions")
        
        # Extract from YouTube comments
        if youtube_comments:
            for comment in youtube_comments:
                keywords = DiagnosisAggregator.extract_keywords(comment)
                all_keywords.extend(keywords)
            sources.append(f"YouTube comments ({len(youtube_comments)})")
            logger.info(f"Processed {len(youtube_comments)} YouTube comments")
        
        # Extract from YouTube transcripts
        if youtube_transcripts:
            for transcript in youtube_transcripts:
                keywords = DiagnosisAggregator.extract_keywords(transcript)
                all_keywords.extend(keywords)
            sources.append(f"YouTube transcripts ({len(youtube_transcripts)})")
            logger.info(f"Processed {len(youtube_transcripts)} YouTube transcripts")
        
        # Add spectrogram match result
        if spectrogram_match:
            keywords = DiagnosisAggregator.extract_keywords(spectrogram_match)
            all_keywords.extend(keywords * 2)  # Weight spectrogram higher
            all_diagnoses.append(DiagnosisAggregator.normalize_diagnosis(spectrogram_match))
            sources.append("Spectrogram match")
            logger.info("Added spectrogram match result")
        
        # Add AI diagnosis
        if ai_diagnosis:
            keywords = DiagnosisAggregator.extract_keywords(ai_diagnosis)
            all_keywords.extend(keywords * 2)  # Weight AI higher
            all_diagnoses.append(DiagnosisAggregator.normalize_diagnosis(ai_diagnosis))
            sources.append("AI analysis")
            logger.info("Added AI diagnosis")
        
        if not all_keywords:
            logger.warning("No diagnostic keywords found from any source")
            return {
                'diagnosis': 'Unable to determine issue - insufficient data',
                'confidence': 0.3,
                'sources': sources,
                'keywords': []
            }
        
        # Count keyword frequency
        keyword_counter = Counter(all_keywords)
        most_common_keywords = keyword_counter.most_common(5)
        
        logger.info(f"Most common keywords: {most_common_keywords}")
        
        # Filter by vehicle specifications
        if vehicle_info:
            manufacturer = vehicle_info.get('manufacturer', '')
            model = vehicle_info.get('model', '')
            year = vehicle_info.get('year', 2020)
            
            filtered_keywords = []
            for keyword, count in most_common_keywords:
                diagnosis_text = f"{keyword} issue"
                if VehicleSpecificationChecker.filter_diagnosis(diagnosis_text, manufacturer, model, year):
                    filtered_keywords.append((keyword, count))
            
            if filtered_keywords:
                most_common_keywords = filtered_keywords
                logger.info(f"Filtered keywords: {most_common_keywords}")
        
        # Build diagnosis from most common keywords
        top_keyword = most_common_keywords[0][0]
        top_count = most_common_keywords[0][1]
        total_mentions = sum(count for _, count in keyword_counter.items())
        
        # Calculate confidence based on consensus
        confidence = min(0.95, (top_count / total_mentions) * 1.2)
        
        # Build diagnosis sentence
        diagnosis = f"Likely {top_keyword} issue detected"
        
        # Add secondary issues if they're also common
        if len(most_common_keywords) > 1:
            second_keyword = most_common_keywords[1][0]
            second_count = most_common_keywords[1][1]
            
            if second_count >= top_count * 0.6:  # If second issue is at least 60% as common
                diagnosis = f"Likely {top_keyword} or {second_keyword} issue detected"
        
        logger.info(f"Common denominator diagnosis: {diagnosis} (confidence: {confidence:.2f})")
        
        return {
            'diagnosis': diagnosis,
            'confidence': round(confidence, 2),
            'sources': sources,
            'keywords': [k for k, _ in most_common_keywords],
            'keyword_counts': dict(most_common_keywords)
        }
