# coding: utf8
import logging
import threading
from email.parser import BytesHeaderParser
import appletv

import lib.biplist

from flask import Flask, make_response, request

log = logging.getLogger('airplayer')


app = Flask(__name__)


def airplay_protocol(port, media_backend):
    app._media_backend = media_backend
    from werkzeug.serving import run_simple

    return threading.Thread(target=lambda: run_simple('0.0.0.0', port, app, use_debugger=True, use_reloader=False))


@app.route('/reverse', methods=('POST',))
def reverse():
    """
    Handler for /reverse requests.

    The reverse command is the first command sent by Airplay,
    it's a handshake.
    """
    resp = make_response('')
    resp.status_code = 101
    resp.headers['Upgrade'] = 'PTTH/1.0'
    resp.headers['Connection'] = 'Upgrade'
    return resp


@app.route('/play', methods=('POST',))
def play():
    """
    Handler for /play requests.

    Contains a header like format in the request body which should contain a
    Content-Location and optionally a Start-Position.

    Immediately finish this request, no need for the client to wait for
    backend communication.
    """

    def _play():
        if request.headers.get('Content-Type', None) == 'application/x-apple-binary-plist':
            body = lib.biplist.readPlistFromString(request.data)
        else:
            body = BytesHeaderParser().parsebytes(request.data)

        if 'Content-Location' in body:
            url = body['Content-Location']
            log.debug('Playing %s', url)

            app._media_backend.play_movie(url)

            if 'Start-Position' in body:
                """
                Airplay sends start-position in percentage from 0 to 1.
                Media backends expect a percentage from 0 to 100.
                """
                try:
                    str_pos = body['Start-Position']
                except ValueError:
                    log.warning('Invalid start-position supplied: ', str_pos)
                else:
                    position_percentage = float(str_pos) * 100
                    app._media_backend.set_start_position(position_percentage)
    _play()
    return ''


@app.route('/scrub', methods=('GET', 'POST'))
def scrub():
    """
    Handler for /scrub requests.

    Used to perform seeking (POST request) and to retrieve current player position (GET request).
    """

    if request.method == 'GET':
        """
        Will return None, None if no media is playing or an error occures.
        """
        position, duration = app._media_backend.get_player_position()

        """
        Should None values be returned just default to 0 values.
        """
        if not position:
            duration = position = 0

        body = 'duration: %f\r\nposition: %f\r\n' % (duration, position)
        return body

    elif request.method == 'POST':
        """
        Immediately finish this request, no need for the client to wait for
        backend communication.
        """

        def set_position():
            if 'position' in request.args:
                try:
                    str_pos = request.args['position'][0]
                    position = int(float(str_pos))
                except ValueError:
                    log.warn('Invalid scrub value supplied: ', str_pos)
                else:
                    app._media_backend.set_player_position(position)

    set_position()
    return ''


@app.route('/rate', methods=("POST",))
def rate():
    """
    Handler for /rate requests.

    The rate command is used to play/pause media.
    A value argument should be supplied which indicates media should be played or paused.

    0.000000 => pause
    1.000000 => play

    Immediately finish this request, no need for the client to wait for
    backend communication.
    """

    def _rate():
        if 'value' in request.args:
            play = bool(float(request.args['value'][0]))

            if play:
                app._media_backend.play()
            else:
                app._media_backend.pause()

    _rate()
    return ''


@app.route('/photo', methods=("PUT",))
def photo():
    """
    Handler for /photo requests.

    RAW JPEG data is contained in the request body.
    """

    def put():
        """
        Immediately finish this request, no need for the client to wait for
        backend communication.
        """

        if request.data:
            app._media_backend.show_picture(request.data)

    put()
    return ''


@app.route('/authorize', methods=('GET', 'POST'))
def authorize():
    """
    Handler for /authorize requests.

    This is used to handle DRM authorization.
    We currently don't support DRM protected media.
    """

    log.warning('Trying to play DRM protected, this is currently unsupported.')
    log.debug('Got an authorize %s request', request.method)
    log.debug('Authorize request info: %s %s %s', request.headers, request.args, request.data)

    if request.method == 'GET':
        pass

    elif request.method == 'POST':
        pass

    return ''


@app.route('/stop', methods=('POST',))
def stop():
    """
    Handler for /stop requests.

    Sent when media playback should be stopped.
    """

    app._media_backend.stop_playing()
    return ''


@app.route('/server-info', methods=('GET',))
def server_info():
    """
    Handler for /server-info requests.

    Usage currently unknown.
    Available from IOS 4.3.
    """

    resp = make_response(appletv.SERVER_INFO)
    resp.headers['Content-Type'] = 'text/x-apple-plist+xml'
    return resp


@app.route('/slideshow-features', methods=('GET',))
def slideshow_features():
    """
    Handler for /slideshow-features requests.

    Usage currently unknown.
    Available from IOS 4.3.

    I think slideshow effects should be implemented by the Airplay device.
    The currently supported media backends do not support this.

    We'll just ignore this request, that'll enable the simple slideshow without effects.
    """
    return ''


@app.route('/playback-info', methods=("GET",))
def playback_info():
    """
    Handler for /playback-info requests.
    """
    playing = app._media_backend.is_playing()
    position, duration = app._media_backend.get_player_position()

    if not position:
        position = duration = 0
    else:
        position = float(position)
        duration = float(duration)

    body = appletv.PLAYBACK_INFO % (duration, duration, position, int(playing), duration)

    resp = make_response(body)
    resp.headers['Content-Type'] = 'text/x-apple-plist+xml'
    return resp
