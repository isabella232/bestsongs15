#!/usr/bin/env python
"""
Example application views.

Note that `render_template` is wrapped with `make_response` in all application
routes. While not necessary for most Flask apps, it is required in the
App Template for static publishing.
"""

import app_config
import json
import oauth
import static

from collections import OrderedDict
from flask import Flask, make_response, render_template
from math import ceil
from render_utils import make_context, smarty_filter, urlencode_filter, format_time_filter
from werkzeug.debug import DebuggedApplication

app = Flask(__name__)
app.debug = app_config.DEBUG

app.add_template_filter(smarty_filter, name='smarty')
app.add_template_filter(urlencode_filter, name='urlencode')
app.add_template_filter(format_time_filter, name='format_time')

@app.route('/')
@oauth.oauth_required
def index():
    """
    Example view demonstrating rendering a simple HTML page.
    """
    context = make_context()

    with open('data/featured.json') as f:
        context['featured'] = json.load(f)

    with open('data/songs.json') as f:
        context['song_data'] = f.read()
        context['total_songs'] = len(json.loads(context['song_data']))

    tags = context['COPY']['tags']._serialize()
    for key, tag in tags.items():
        tag['key'] = key
    tags = tags.values()
    context['genre_tags'] = [tag for tag in tags if tag['genre'] == 'True']
    context['playlist_tags'] = [tag for tag in tags if tag['genre'] != 'True']

    return make_response(render_template('index.html', **context))

@app.route('/covers.html')
def covers():
    """
    Preview for Seamus page
    """
    context = make_context()

    # Read the songs JSON into the page.
    with open('data/songs.json', 'rb') as readfile:
        songs_data = json.load(readfile)
        songs = sorted(songs_data, key=lambda k: (k['artist'].lower()[4:] if k['artist'].lower().startswith('the ') else k['artist'].lower()))

    context['songs'] = songs
    return make_response(render_template('covers.html', **context))

@app.route('/seamus.html')
def seamus():
    """
    Preview for Seamus page
    """
    context = make_context()

    # Read the songs JSON into the page.
    with open('data/songs.json', 'rb') as readfile:
        songs_data = json.load(readfile)
        songs = sorted(songs_data, key=lambda k: (k['artist'].lower()[4:] if k['artist'].lower().startswith('the ') else k['artist'].lower()))

    tags = context['COPY']['tags']._serialize() #.values(), key=lambda k: k['displayname'])
    context['songs'] = _group_by_genre(songs, tags)
    context['tags'] = tags

    return make_response(render_template('seamus-preview.html', **context))


def _group_by_genre(songs, tags):
    grouped = OrderedDict()
    for key, tag in tags.items():
        #import ipdb; ipdb.set_trace();
        grouped[key] = []
    for song in songs:
        tag = song['genre_tags'][0]
        grouped[tag].append(song)

    return grouped


app.register_blueprint(static.static)
app.register_blueprint(oauth.oauth)

# Enable Werkzeug debug pages
if app_config.DEBUG:
    wsgi_app = DebuggedApplication(app, evalex=False)
else:
    wsgi_app = app

# Catch attempts to run the app directly
if __name__ == '__main__':
    print 'This command has been removed! Please run "fab app" instead!'
