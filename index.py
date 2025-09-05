from flask import Flask, request, jsonify
import requests
import json
app = Flask(__name__)
DEEZER_API_GATEWAY = 'https://api.deezer.com/1.0/gateway.php'
DEEZER_LEGACY_API = 'https://www.deezer.com/ajax/gw-light.php'
DEEZER_MEDIA_URL = 'https://media.deezer.com/v1/get_url'
DEEZER_SESSION_ID = None
_session = requests.Session()
_session_initialized = False
@app.before_request
def setup_session():
    global _session_initialized
    if not _session_initialized:
        initialize_deezer_session()
        _session_initialized = True
def initialize_deezer_session():
    global DEEZER_SESSION_ID
    try:
        headers = {'User-Agent': 'Deezer/7.17.0.2 CFNetwork/1098.6 Darwin/19.0.0'}
        response = _session.get(f"{DEEZER_LEGACY_API}?method=deezer.ping&api_version=1.0&api_token", headers=headers)
        response.raise_for_status()
        data = response.json()
        sid = data.get('results', {}).get('SESSION')
        if not sid:
            raise Exception("Failed to get session ID from deezer.ping")
        DEEZER_SESSION_ID = sid
    except Exception as e:
        pass
def call_deezer_api(method, body={}):
    if not DEEZER_SESSION_ID:
        raise Exception("Deezer session is not initialized.")
    api_key = 'ZAIVAHCEISOHWAICUQUEXAEPICENGUAFAEZAIPHAELEEVAHPHUCUFONGUAPASUAY'
    params = {'method': method, 'api_version': '1.0', 'api_key': api_key, 'input': 3, 'output': 3, 'sid': DEEZER_SESSION_ID}
    headers = {'User-Agent': 'Deezer/7.17.0.2 CFNetwork/1098.6 Darwin/19.0.0', 'Content-Type': 'application/json'}
    response = _session.post(DEEZER_API_GATEWAY, params=params, data=json.dumps(body), headers=headers)
    response.raise_for_status()
    return response.json()
def get_track_download_url(track_token, format_id):
    try:
        payload = { 'license_token': DEEZER_SESSION_ID, 'media': [{'type': 'track', 'id': track_token}], 'formats': [{'cipher': 'BF_CBC_STRIPE', 'format': format_id}]}
        response = _session.post(DEEZER_MEDIA_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return data['data'][0].get('media_url')
    except Exception:
        return None
def format_track_data(track_data):
    if not track_data: return None
    track_token = track_data.get('TRACK_TOKEN')
    return {
        'id': track_data.get('SNG_ID'),
        'title': track_data.get('SNG_TITLE'),
        'isrc': track_data.get('ISRC'),
        'link': f"https://www.deezer.com/track/{track_data.get('SNG_ID')}",
        'duration': int(track_data.get('DURATION', 0)),
        'explicit': track_data.get('EXPLICIT_LYRICS'),
        'bpm': track_data.get('BPM'),
        'gain': track_data.get('GAIN'),
        'release_date': track_data.get('PHYSICAL_RELEASE_DATE'),
        'track_token': track_token,
        'artist': {'id': track_data.get('ART_ID'), 'name': track_data.get('ART_NAME')},
        'album': {'id': track_data.get('ALB_ID'), 'title': track_data.get('ALB_TITLE')},
        'cover': {
            'small': f"https://e-cdns-images.dzcdn.net/images/cover/{track_data.get('ALB_PICTURE')}/56x56-000000-80-0-0.jpg",
            'medium': f"https://e-cdns-images.dzcdn.net/images/cover/{track_data.get('ALB_PICTURE')}/250x250-000000-80-0-0.jpg",
            'large': f"https://e-cdns-images.dzcdn.net/images/cover/{track_data.get('ALB_PICTURE')}/500x500-000000-80-0-0.jpg"
        },
        'downloads': {
            'FLAC': get_track_download_url(track_token, 'FLAC'),
            'MP3_320': get_track_download_url(track_token, 'MP3_320'),
            'MP3_128': get_track_download_url(track_token, 'MP3_128'),
        }
    }
@app.route('/api/track', methods=['GET'])
def get_track():
    track_id = request.args.get('id') or (request.args.get('url', '').split('/')[-1].split('?')[0] if request.args.get('url') else None)
    if not track_id: return jsonify({'error': 'Track ID or URL is required.'}), 400
    try:
        data = call_deezer_api('song.getData', {'sng_id': track_id})
        return jsonify(format_track_data(data.get('results')))
    except Exception as e:
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500
@app.route('/api/album', methods=['GET'])
def get_album():
    album_id = request.args.get('id') or (request.args.get('url', '').split('/')[-1].split('?')[0] if request.args.get('url') else None)
    if not album_id: return jsonify({'error': 'Album ID or URL is required.'}), 400
    try:
        data = call_deezer_api('album.getData', {'alb_id': album_id})
        album_data = data.get('results', {})
        tracks_data = album_data.get('SONGS', {}).get('data', [])
        return jsonify({
            'id': album_data.get('ALB_ID'),
            'title': album_data.get('ALB_TITLE'),
            'upc': album_data.get('UPC'),
            'link': f"https://www.deezer.com/album/{album_data.get('ALB_ID')}",
            'artist': {'id': album_data.get('ART_ID'), 'name': album_data.get('ART_NAME')},
            'label': album_data.get('LABEL_NAME'),
            'release_date': album_data.get('PHYSICAL_RELEASE_DATE'),
            'track_count': int(album_data.get('NUMBER_TRACK', 0)),
            'genres': album_data.get('GENRES', {}).get('data', []),
            'cover': {
                'small': f"https://e-cdns-images.dzcdn.net/images/cover/{album_data.get('ALB_PICTURE')}/56x56-000000-80-0-0.jpg",
                'medium': f"https://e-cdns-images.dzcdn.net/images/cover/{album_data.get('ALB_PICTURE')}/250x250-000000-80-0-0.jpg",
                'large': f"https://e-cdns-images.dzcdn.net/images/cover/{album_data.get('ALB_PICTURE')}/500x500-000000-80-0-0.jpg"
            },
            'tracks': [{'id': track.get('SNG_ID'),'title': track.get('SNG_TITLE'),'artist': {'id': track.get('ART_ID'), 'name': track.get('ART_NAME')},'album': {'id': track.get('ALB_ID'), 'title': track.get('ALB_TITLE')},'duration': int(track.get('DURATION', 0)),'track_number': track.get('TRACK_POSITION'),'disk_number': track.get('DISK_NUMBER')} for track in tracks_data]
        })
    except Exception as e:
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500
@app.route('/api/artist', methods=['GET'])
def get_artist():
    artist_id = request.args.get('id') or (request.args.get('url', '').split('/')[-1].split('?')[0] if request.args.get('url') else None)
    if not artist_id: return jsonify({'error': 'Artist ID or URL is required.'}), 400
    try:
        artist_data = call_deezer_api('artist.getData', {'art_id': artist_id}).get('results', {})
        top_tracks_data = call_deezer_api('artist.getTopTrack', {'art_id': artist_id}).get('results', {}).get('data', [])
        return jsonify({
            'id': artist_data.get('ART_ID'),
            'name': artist_data.get('ART_NAME'),
            'link': f"https://www.deezer.com/artist/{artist_data.get('ART_ID')}",
            'nb_fan': int(artist_data.get('NB_FAN', 0)),
            'nb_albums': int(artist_data.get('NB_ALBUM', 0)),
            'picture': {
                'small': f"https://e-cdns-images.dzcdn.net/images/artist/{artist_data.get('ART_PICTURE')}/56x56-000000-80-0-0.jpg",
                'medium': f"https://e-cdns-images.dzcdn.net/images/artist/{artist_data.get('ART_PICTURE')}/250x250-000000-80-0-0.jpg",
                'large': f"https://e-cdns-images.dzcdn.net/images/artist/{artist_data.get('ART_PICTURE')}/500x500-000000-80-0-0.jpg"
            },
            'top_tracks': [format_track_data(track) for track in top_tracks_data]
        })
    except Exception as e:
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500
@app.route('/api/playlist', methods=['GET'])
def get_playlist():
    playlist_id = request.args.get('id') or (request.args.get('url', '').split('/')[-1].split('?')[0] if request.args.get('url') else None)
    if not playlist_id: return jsonify({'error': 'Playlist ID or URL is required.'}), 400
    try:
        data = call_deezer_api('playlist.getData', {'playlist_id': playlist_id})
        playlist_data = data.get('results', {})
        tracks_data = playlist_data.get('SONGS', {}).get('data', [])
        return jsonify({
            'id': playlist_data.get('PLAYLIST_ID'),
            'title': playlist_data.get('TITLE'),
            'description': playlist_data.get('DESCRIPTION'),
            'link': f"https://www.deezer.com/playlist/{playlist_data.get('PLAYLIST_ID')}",
            'creator': {'name': playlist_data.get('PARENT_USERNAME')},
            'track_count': int(playlist_data.get('NB_SONG', 0)),
            'fans': int(playlist_data.get('NB_FAN', 0)),
            'picture': {
                'small': f"https://e-cdns-images.dzcdn.net/images/playlist/{playlist_data.get('PLAYLIST_PICTURE')}/56x56-000000-80-0-0.jpg",
                'medium': f"https://e-cdns-images.dzcdn.net/images/playlist/{playlist_data.get('PLAYLIST_PICTURE')}/250x250-000000-80-0-0.jpg",
                'large': f"https://e-cdns-images.dzcdn.net/images/playlist/{playlist_data.get('PLAYLIST_PICTURE')}/500x500-000000-80-0-0.jpg"
            },
            'tracks': [format_track_data(track) for track in tracks_data]
        })
    except Exception as e:
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500
@app.route('/api/artist/discography', methods=['GET'])
def get_artist_discography():
    artist_id = request.args.get('id') or (request.args.get('url', '').split('/')[-1].split('?')[0] if request.args.get('url') else None)
    if not artist_id: return jsonify({'error': 'Artist ID or URL is required.'}), 400
    try:
        data = call_deezer_api('album.getDiscography', {'art_id': artist_id, 'nb': 500})
        albums_data = data.get('results', {}).get('data', [])
        return jsonify({'artist_id': artist_id,'albums': [{'id': album.get('ALB_ID'),'title': album.get('ALB_TITLE'),'release_date': album.get('PHYSICAL_RELEASE_DATE')} for album in albums_data]})
    except Exception as e:
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500
@app.route('/api/lyrics', methods=['GET'])
def get_lyrics():
    track_id = request.args.get('id')
    if not track_id: return jsonify({'error': 'Track ID is required.'}), 400
    try:
        data = call_deezer_api('song.getLyrics', {'sng_id': track_id})
        lyrics_data = data.get('results', {})
        return jsonify({
            'track_id': track_id,
            'plain_lyrics': lyrics_data.get('LYRICS_TEXT'),
            'synced_lyrics': lyrics_data.get('LYRICS_SYNC_JSON')
        })
    except Exception as e:
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500

if __name__ == '__main__':
    app.run(port=0.0.0.0, debug=True)


