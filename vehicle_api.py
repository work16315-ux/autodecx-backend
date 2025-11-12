# vehicle_api.py
import requests
from flask import Blueprint, jsonify, request
import logging

vehicle_bp = Blueprint('vehicle', __name__)
logger = logging.getLogger(__name__)

# NHTSA API base URL
NHTSA_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"

@vehicle_bp.route('/api/vehicle-models', methods=['GET'])
def get_vehicle_models():
    """
    Get vehicle models for a specific manufacturer and year
    Query params: manufacturer, year
    """
    manufacturer = request.args.get('manufacturer')
    year = request.args.get('year')
    
    if not manufacturer or not year:
        return jsonify({'error': 'Manufacturer and year are required'}), 400
    
    logger.info(f"Fetching models for {manufacturer} {year}")
    
    try:
        # NHTSA API endpoint for models by make and year
        url = f"{NHTSA_BASE_URL}/GetModelsForMakeYear/make/{manufacturer}/modelyear/{year}?format=json"
        
        logger.info(f"Calling NHTSA API: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract model names from results
            results = data.get('Results', [])
            models = []
            
            for item in results:
                model_name = item.get('Model_Name')
                if model_name and model_name not in models:
                    models.append(model_name)
            
            # Sort alphabetically
            models.sort()
            
            logger.info(f"Found {len(models)} models for {manufacturer} {year}")
            
            if not models:
                # Fallback: common models for popular brands
                models = get_fallback_models(manufacturer, year)
            
            return jsonify({
                'success': True,
                'manufacturer': manufacturer,
                'year': year,
                'models': models,
                'count': len(models)
            })
        else:
            logger.error(f"NHTSA API error: {response.status_code}")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch models',
                'models': get_fallback_models(manufacturer, year)
            }), 200
    
    except requests.Timeout:
        logger.error("NHTSA API timeout")
        return jsonify({
            'success': False,
            'error': 'API timeout',
            'models': get_fallback_models(manufacturer, year)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'models': get_fallback_models(manufacturer, year)
        }), 200


def get_fallback_models(manufacturer, year):
    """
    Fallback models for popular South African brands
    Based on common models sold in SA market
    """
    fallback_data = {
        'BMW': [
            '1 Series', '2 Series', '3 Series', '4 Series', '5 Series', '6 Series', '7 Series', '8 Series',
            'X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'X7',
            'Z4', 'M2', 'M3', 'M4', 'M5', 'M8', 'i3', 'i4', 'iX', 'iX3'
        ],
        'Mercedes-Benz': [
            'A-Class', 'B-Class', 'C-Class', 'E-Class', 'S-Class',
            'CLA', 'CLS', 'GLA', 'GLB', 'GLC', 'GLE', 'GLS',
            'AMG GT', 'EQA', 'EQB', 'EQC', 'EQE', 'EQS', 'G-Class', 'V-Class'
        ],
        'Audi': [
            'A1', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8',
            'Q2', 'Q3', 'Q4 e-tron', 'Q5', 'Q7', 'Q8',
            'TT', 'R8', 'e-tron GT', 'RS3', 'RS4', 'RS5', 'RS6', 'RS7'
        ],
        'Toyota': [
            'Agya', 'Starlet', 'Corolla', 'Corolla Cross', 'Camry', 'Prius',
            'Hilux', 'Fortuner', 'Land Cruiser', 'Prado', 'RAV4',
            'Urban Cruiser', 'C-HR', 'Avanza', 'Quantum', 'HiAce'
        ],
        'Volkswagen': [
            'Polo', 'Polo Vivo', 'Golf', 'Jetta', 'Passat', 'Arteon',
            'T-Cross', 'T-Roc', 'Tiguan', 'Tiguan Allspace', 'Touareg',
            'Amarok', 'Caddy', 'Transporter', 'ID.4'
        ],
        'Ford': [
            'Figo', 'Fiesta', 'Focus', 'Mustang',
            'EcoSport', 'Puma', 'Kuga', 'Everest',
            'Ranger', 'Ranger Raptor', 'Transit', 'Transit Custom'
        ],
        'Nissan': [
            'Micra', 'Almera', 'Sentra',
            'Magnite', 'Qashqai', 'X-Trail', 'Patrol',
            'Navara', 'NP200', 'NP300'
        ],
        'Hyundai': [
            'Grand i10', 'i20', 'Accent', 'Elantra', 'Sonata',
            'Venue', 'Creta', 'Tucson', 'Santa Fe', 'Palisade',
            'H-100', 'Staria', 'Kona', 'Ioniq 5'
        ],
        'Kia': [
            'Picanto', 'Rio', 'Cerato', 'K5',
            'Seltos', 'Sportage', 'Sorento', 'Carnival',
            'EV6', 'Stinger'
        ],
        'Mazda': [
            'Mazda2', 'Mazda3', 'Mazda6',
            'CX-3', 'CX-30', 'CX-5', 'CX-60', 'CX-9',
            'BT-50', 'MX-5'
        ],
        'Honda': [
            'Brio', 'Ballade', 'Civic', 'Accord',
            'HR-V', 'CR-V', 'ZR-V'
        ],
        'Renault': [
            'Kwid', 'Sandero', 'Clio', 'Megane',
            'Kiger', 'Captur', 'Duster', 'Koleos',
            'Triber', 'Kangoo'
        ],
        'Suzuki': [
            'S-Presso', 'Swift', 'Baleno', 'Ciaz',
            'Dzire', 'Fronx', 'Brezza', 'Ertiga', 'XL6',
            'Jimny', 'Vitara', 'Grand Vitara'
        ],
        'Isuzu': [
            'D-Max', 'MU-X'
        ],
        'Mitsubishi': [
            'Mirage', 'Attrage',
            'ASX', 'Eclipse Cross', 'Outlander', 'Pajero Sport',
            'Triton', 'Xpander'
        ],
        'Jeep': [
            'Avenger', 'Renegade', 'Compass', 'Cherokee',
            'Grand Cherokee', 'Wrangler', 'Gladiator'
        ],
        'Land Rover': [
            'Defender', 'Discovery', 'Discovery Sport',
            'Range Rover Evoque', 'Range Rover Velar',
            'Range Rover Sport', 'Range Rover'
        ],
        'Volvo': [
            'XC40', 'XC60', 'XC90',
            'S60', 'S90', 'V60', 'V90',
            'C40 Recharge', 'XC40 Recharge'
        ],
        'Peugeot': [
            '108', '208', '2008', '3008', '5008',
            'Partner', 'Expert', 'Boxer'
        ],
        'Opel': [
            'Corsa', 'Astra', 'Grandland',
            'Combo', 'Movano'
        ],
        'Chevrolet': [
            'Spark', 'Aveo', 'Cruze',
            'Trailblazer', 'Captiva',
            'Utility'
        ],
        'GWM': [
            'P Series', 'Steed', 'Poer',
            'Haval H2', 'Haval Jolion', 'Haval H6', 'Haval H9'
        ],
        'Haval': [
            'H2', 'Jolion', 'H6', 'H9'
        ],
        'Chery': [
            'QQ', 'Tiggo 4 Pro', 'Tiggo 7 Pro', 'Tiggo 8 Pro'
        ],
        'Mahindra': [
            'KUV100', 'XUV300', 'XUV500', 'XUV700',
            'Scorpio', 'Bolero', 'Pik Up'
        ],
        'Fiat': [
            '500', 'Panda', 'Tipo', 'Ducato'
        ],
        'Jaguar': [
            'XE', 'XF', 'F-Pace', 'E-Pace', 'I-Pace', 'F-Type'
        ]
    }
    
    # Get models for the manufacturer (case-insensitive)
    for brand, models in fallback_data.items():
        if brand.lower() == manufacturer.lower():
            logger.info(f"Using fallback models for {manufacturer}")
            return models
    
    # Generic fallback
    logger.info(f"No fallback data for {manufacturer}, returning generic message")
    return ["Please type model name manually"]