from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import os
from functools import wraps
import time

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.environ.get('ENVIRONMENT') == 'production' else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Security headers middleware
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Error handler
@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"An error occurred: {str(error)}", exc_info=True)
    return jsonify({
        'error': str(error),
        'status': 'error'
    }), 500

@app.route('/')
@limiter.limit("10 per minute")
def home():
    return jsonify({
        'status': 'Server is running',
        'endpoints': {
            'transcript': '/api/transcript',
            'health': '/health'
        },
        'version': '1.0.0'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'environment': os.environ.get('ENVIRONMENT', 'development'),
        'service': 'youtube-transcript-api'
    })

def get_video_transcript(url):
    try:
        parsed_url = urlparse(url)
        if 'youtube.com' in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            video_id = query_params.get('v', [None])[0]
        else:
            video_id = parsed_url.path.split('/')[-1]

        if not video_id:
            raise ValueError("Invalid YouTube URL")

        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        logger.error(f"Error fetching transcript: {str(e)}", exc_info=True)
        raise

@app.route('/api/transcript', methods=['POST'])
@limiter.limit("100 per hour")
def get_transcript():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400

        url = data['url']
        transcript = get_video_transcript(url)
        return jsonify({'transcript': transcript})

    except Exception as e:
        logger.error(f"Error in transcript endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('ENVIRONMENT') != 'production'
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )